"""Générateur d'épisodes seedés de l'environnement Entrepôt.

@spec docs/BACKLOG.md U29a1 — environnement Entrepôt du banc a
@spec docs/SPEC_BANCS.md §S1.4 (déterminisme), §S2.2 (paramètres d'un épisode),
      §S3.3 (générateur, types faisables), §S3.4 (résolution nominale : les
      événements référencent l'état d'un jeu parfait, jamais l'état réel de
      l'agent), §S3.6 (bruit de condition 1, seedé, sans effet sur l'état)

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
class Episode:
    """Un épisode entier, figé à la génération (§S1.4).

    `telemetrie[i]` porte les lignes de bruit accompagnant `evenements[i]`.
    """

    seed: int
    horizon: int
    bruit: int
    evenements: tuple[EvenementEntrepot, ...]
    telemetrie: tuple[tuple[str, ...], ...]


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


def generer_episode(seed: int, horizon: int, bruit: int = 0) -> Episode:
    """Engendre l'épisode complet sur l'état nominal (§S3.3, §S3.4).

    L'état nominal est celui qu'aurait produit un agent parfait : rangement sur la
    plus petite étagère vide, obligations honorées à chaque pas. Les tirages
    (type d'événement, article commandé, étagère en maintenance) viennent du seul
    `random.Random(seed)`, dans un ordre d'appel fixe.
    """
    if horizon < 0:
        raise ValueError(f"horizon négatif : {horizon}")
    if bruit < 0:
        raise ValueError(f"bruit négatif : {bruit}")
    rng = random.Random(seed)
    #: Flux séparé pour la télémétrie (§S3.6) : le niveau de bruit ne change
    #: jamais la suite d'événements — même tâche, distracteurs ajoutés.
    rng_bruit = random.Random(f"bruit-{seed}")
    nominal: list[str | None] = [None] * NB_ETAGERES
    prochain_article = 0
    evenements: list[EvenementEntrepot] = []
    telemetrie: list[tuple[str, ...]] = []
    for _ in range(horizon):
        occupees = [i for i, article in enumerate(nominal) if article is not None]
        vides = [i for i, article in enumerate(nominal) if article is None]
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
    return Episode(
        seed=seed,
        horizon=horizon,
        bruit=bruit,
        evenements=tuple(evenements),
        telemetrie=tuple(telemetrie),
    )
