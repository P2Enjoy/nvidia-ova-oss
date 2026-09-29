"""Mesure du préfixe commun entre deux messages de pas consécutifs (§H11.2).

@spec docs/BACKLOG.md U31 — métrique `prefixe_pas` : lecture hors ligne du froid
      de préremplissage que `prefill_ms` ne rend pas sous coupure du pont
@spec docs/SPEC_HARNAIS.md §H11.2 (métrique `prefixe_pas` : `caracteres`,
      `prefixe_commun`, `divergence`), §H15.11 (le cache de préfixe ne sert que
      jusqu'au premier token modifié ; ordre notes → observation → Σ → protocole)

Fonctions pures : aucune lecture de fichier, aucun contenu conservé au-delà de
l'appel, aucune connaissance de l'environnement (§A5.1). Le message système
étant constant d'un pas à l'autre, le préfixe commun du message UTILISATEUR est
la part servie par le cache de l'endpoint ; la partie où tombe la première
divergence est la première part repayée à froid.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

#: Partie nommée quand la divergence précède tout repère : un message
#: exceptionnel en tête (erreur nommée, rappel, superviseur, amorce, idéation).
TETE: Final = "tete"
#: Aucun message précédent : première composition du jeu.
PREMIER: Final = "premier"
#: Message identique au précédent, octet pour octet.
AUCUNE: Final = "aucune"


def longueur_prefixe_commun(a: str, b: str) -> int:
    """Nombre de caractères identiques en tête de `a` et `b`."""
    borne = min(len(a), len(b))
    i = 0
    while i < borne and a[i] == b[i]:
        i += 1
    return i


def partie_de(offset: int, reperes: Mapping[str, int]) -> str:
    """Nom de la partie qui contient `offset`.

    `reperes` associe chaque nom de partie à l'offset de son premier caractère
    dans le message courant ; la partie d'un offset est celle dont le repère est
    le plus grand parmi ceux inférieurs ou égaux à l'offset. Un offset qui
    précède tous les repères tombe dans la tête (`tete`).
    """
    candidats = [(debut, nom) for nom, debut in reperes.items() if debut <= offset]
    if not candidats:
        return TETE
    return max(candidats)[1]


def mesurer_prefixe(
    precedent: str | None, courant: str, reperes: Mapping[str, int]
) -> dict[str, Any]:
    """Champs de la métrique `prefixe_pas` (§H11.2) pour le message `courant`."""
    if precedent is None:
        return {"caracteres": len(courant), "prefixe_commun": 0, "divergence": PREMIER}
    commun = longueur_prefixe_commun(precedent, courant)
    if commun == len(courant) == len(precedent):
        divergence = AUCUNE
    else:
        divergence = partie_de(commun, reperes)
    return {"caracteres": len(courant), "prefixe_commun": commun, "divergence": divergence}
