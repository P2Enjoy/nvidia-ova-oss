"""Générateur d'épisodes seedés de l'environnement Entrepôt.

@spec docs/BACKLOG.md U29a1 — environnement Entrepôt du banc a ; U29a4 — dérive
      d'état de la condition 3
@spec docs/SPEC_BANCS.md §S1.4 (déterminisme), §S2.2 (paramètres d'un épisode),
      §S3.3 (générateur, types faisables), §S3.4 (résolution nominale : les
      événements référencent l'état d'un jeu parfait, jamais l'état réel de
      l'agent), §S3.6 (bruit de condition 1, seedé, sans effet sur l'état),
      §S3.8 (dérive d'état : une seule, rng séparé, pas forcé, alerte non
      structurée, génération inchangée à `derive` inactif)

L'épisode est engendré EN ENTIER avant le jeu : à seed et paramètres identiques,
la suite d'événements et la télémétrie sont identiques octet pour octet, quel que
soit le comportement de l'agent. C'est l'exigence de comparaison équitable de la
source (annexe B.2) : tous les runtimes comparés rencontrent le même épisode.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Final

#: Nombre d'étagères de l'entrepôt (§S3.1).
NB_ETAGERES: Final = 500

#: En-tête des lignes de télémétrie (§S3.6).
ENTETE_TELEMETRIE: Final = "--- TELEMETRIE DE FOND ---"

#: En-tête de l'alerte non structurée de la dérive d'état (§S3.8).
ENTETE_ALERTE: Final = "--- ALERTE EXTERNE ---"

#: Types d'événements actionnables (§S3.3).
RECEPTION: Final = "reception"
COMMANDE: Final = "commande"
MAINTENANCE: Final = "maintenance"

#: Gabarits d'OCR caméra (§S3.6, gabarits C.2 de la source) : hors sujet, fixes.
_OCR: Final = (
    "[Caméra OCR] Chariot élévateur à l'arrêt.",
    "[Caméra OCR] Opérateur entré en zone A.",
    "[Caméra OCR] Gilet de sécurité détecté.",
)


def nom_etagere(indice: int) -> str:
    """Nom public d'une étagère (§S3.1)."""
    return f"etagere_{indice}"


def nom_article(numero: int) -> str:
    """Nom public d'un article, identifiant croissant (§S3.3)."""
    return f"article_{numero}"


@dataclass(frozen=True)
class EvenementEntrepot:
    """Un événement actionnable, tel que l'agent l'observe (§S3.3, §S3.5).

    `etagere` n'est renseignée que pour une maintenance ; elle référence l'étagère
    NOMINALE (§S3.4) — celle du jeu parfait, pas nécessairement celle de l'agent.
    """

    type: str
    article: str
    etagere: str | None
    observation: str


@dataclass(frozen=True)
class DeriveEntrepot:
    """La dérive d'état de la condition 3, figée à la génération (§S3.8).

    `source` et `destination` sont les étagères NOMINALES du déplacement externe ;
    l'application à l'état réel appartient à l'environnement.
    """

    evenement: int
    article: str
    source: str
    destination: str
    alerte: str


@dataclass(frozen=True)
class Episode:
    """Un épisode entier, figé à la génération (§S1.4).

    `telemetrie[i]` porte les lignes de bruit accompagnant `evenements[i]` ;
    `derive` porte l'unique dérive de la condition 3 (§S3.8), None sans elle.
    """

    seed: int
    horizon: int
    bruit: int
    evenements: tuple[EvenementEntrepot, ...]
    telemetrie: tuple[tuple[str, ...], ...]
    derive: DeriveEntrepot | None = None


def _ligne_telemetrie(rng: random.Random) -> str:
    """Une ligne de bruit strictement hors sujet (§S3.6, annexe C.2 de la source)."""
    famille = rng.randrange(3)
    if famille == 0:
        return (
            f"[Robot] Batterie : {rng.randint(5, 100)} %, "
            f"Température : {rng.randint(20, 80)} C, "
            f"Charge CPU : {rng.randint(1, 100)} %, "
            f"Vitesse : {rng.randint(0, 30) / 10} m/s"
        )
    if famille == 1:
        return (
            f"[Capteur] Humidité : {rng.randint(20, 90)} %, "
            f"Temp : {rng.randint(150, 350) / 10} C, "
            f"Lumière : {rng.randint(100, 900)} lux, "
            f"CO2 : {rng.randint(350, 1200)} ppm"
        )
    return rng.choice(_OCR)


def generer_episode(seed: int, horizon: int, bruit: int = 0, derive: bool = False) -> Episode:
    """Engendre l'épisode complet sur l'état nominal (§S3.3, §S3.4).

    L'état nominal est celui qu'aurait produit un agent parfait : rangement sur la
    plus petite étagère vide, obligations honorées à chaque pas. Les tirages
    (type d'événement, article commandé, étagère en maintenance) viennent du seul
    `random.Random(seed)`, dans un ordre d'appel fixe. Avec `derive`, une unique
    dérive d'état (§S3.8) se place au premier pas `d ≥ horizon // 2` offrant un
    candidat, sur un rng séparé : le rng principal n'est pas consommé à ce pas,
    et la génération à `derive` inactif reste inchangée octet pour octet.
    """
    if horizon < 0:
        raise ValueError(f"horizon négatif : {horizon}")
    if bruit < 0:
        raise ValueError(f"bruit négatif : {bruit}")
    rng = random.Random(seed)
    #: Flux séparé pour la télémétrie (§S3.6) : le niveau de bruit ne change
    #: jamais la suite d'événements — même tâche, distracteurs ajoutés.
    rng_bruit = random.Random(f"bruit-{seed}")
    rng_derive = random.Random(f"derive-{seed}")
    derive_posee: DeriveEntrepot | None = None
    nominal: list[str | None] = [None] * NB_ETAGERES
    prochain_article = 0
    evenements: list[EvenementEntrepot] = []
    telemetrie: list[tuple[str, ...]] = []
    for pas in range(horizon):
        occupees = [i for i, article in enumerate(nominal) if article is not None]
        vides = [i for i, article in enumerate(nominal) if article is None]
        if derive and derive_posee is None and pas >= horizon // 2 and occupees and vides:
            #: Dérive (§S3.8) : un opérateur externe déplace un article nominal,
            #: et l'événement forcé `commande` teste la prise en compte de
            #: l'alerte — seule elle dit où l'article se trouve désormais.
            indice_source = rng_derive.choice(occupees)
            article = nominal[indice_source] or ""
            destination = min(vides)
            nominal[indice_source] = None
            nominal[destination] = article
            derive_posee = DeriveEntrepot(
                evenement=pas,
                article=article,
                source=nom_etagere(indice_source),
                destination=nom_etagere(destination),
                alerte=f"[Audit externe] {article} déplacé de {nom_etagere(indice_source)} "
                f"vers {nom_etagere(destination)} par un opérateur externe.",
            )
            #: Résolution nominale du pas forcé : l'agent parfait lit l'alerte et
            #: expédie depuis la destination (§S3.4).
            nominal[destination] = None
            evenements.append(
                EvenementEntrepot(COMMANDE, article, None, f"Commande client : {article}.")
            )
            telemetrie.append(tuple(_ligne_telemetrie(rng_bruit) for _ in range(bruit)))
            continue
        types = [RECEPTION] if vides else []
        if occupees:
            types.extend((COMMANDE, MAINTENANCE))
        type_evenement = rng.choice(types)
        if type_evenement == RECEPTION:
            article = nom_article(prochain_article)
            prochain_article += 1
            nominal[min(vides)] = article
            evenement = EvenementEntrepot(RECEPTION, article, None, f"Livraison reçue : {article}.")
        elif type_evenement == COMMANDE:
            indice = rng.choice(occupees)
            article = nominal[indice] or ""
            nominal[indice] = None
            evenement = EvenementEntrepot(COMMANDE, article, None, f"Commande client : {article}.")
        else:
            indice = rng.choice(occupees)
            article = nominal[indice] or ""
            destination = min(vides)
            nominal[indice] = None
            nominal[destination] = article
            evenement = EvenementEntrepot(
                MAINTENANCE,
                article,
                nom_etagere(indice),
                f"Maintenance requise sur {nom_etagere(indice)}.",
            )
        evenements.append(evenement)
        telemetrie.append(tuple(_ligne_telemetrie(rng_bruit) for _ in range(bruit)))
    if derive and derive_posee is None:
        raise ValueError(
            f"aucun candidat de dérive au seed {seed} (horizon {horizon}) : "
            "aucun pas ≥ horizon // 2 n'offre une étagère occupée — "
            "prendre un autre seed (§S3.8)."
        )
    return Episode(
        seed=seed,
        horizon=horizon,
        bruit=bruit,
        evenements=tuple(evenements),
        telemetrie=tuple(telemetrie),
        derive=derive_posee,
    )
