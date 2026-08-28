"""RHAE — efficacité d'action relative à l'humain.

@spec docs/BACKLOG.md U20 — RHAE
@spec docs/SPEC_ARCAGI3.md §A6.1 (définition Tycho §3.1), §A6.1 bis (la somme porte
      sur tous les niveaux du jeu), §A6.2 (baselines), §A6.4 (contrat d'implémentation)
@spec docs/SPEC_ARCAGI3.md §A2.2 (historique typé, source des actions et du score),
      §A1.2 (protocole de score : RESET initial gratuit)

Module **pur** : aucune entrée-sortie, aucun réseau, aucune dépendance à l'état d'un
run. Il reçoit des nombres et rend des nombres, ce qui le rend éprouvable exactement —
la baseline du jeu de rejeu étant connue en forme fermée, le RHAE d'une partie
parfaite se vérifie au chiffre près, sans jouer.

Principe de refus : une donnée impossible **lève**. Rendre 0 ferait passer un défaut
de protocole — une baseline absente, un niveau hors bornes — pour une mauvaise
performance de l'agent, et le rapport serait faux sans que rien ne le signale.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Protocol

#: Plafond de l'efficacité d'un niveau (Tycho §3.1). Un agent très supérieur à
#: l'humain ne peut pas compenser indéfiniment un niveau raté.
EFFICACITE_MAX: Final = 115.0

#: Commande qui crée la partie. Sa première occurrence est gratuite (§A1.2).
RESET: Final = "RESET"


class RhaeInvalide(ValueError):
    """Donnée impossible : elle est nommée, jamais absorbée en un score de 0."""


class EntreeJouee(Protocol):
    """Ce que le RHAE lit d'une entrée d'historique typé (§A2.2).

    Un protocole plutôt que le type concret : le calcul ne dépend ainsi d'aucun
    client, et s'éprouve sur des entrées fabriquées à la main.
    """

    commande: str
    niveau: int
    score: int


@dataclass(frozen=True)
class NiveauJoue:
    """Les trois entrées de la formule pour un niveau, plus son numéro (§A6.4)."""

    niveau: int
    baseline: int
    actions: int
    complete: bool

    def __post_init__(self) -> None:
        if self.niveau < 1:
            raise RhaeInvalide(f"niveau {self.niveau} : les niveaux sont 1-indexés")
        if self.baseline <= 0:
            raise RhaeInvalide(
                f"niveau {self.niveau} : baseline {self.baseline} ≤ 0 — le rapport "
                "hₗ/aₗ n'a pas de sens, c'est un défaut de protocole, pas un score"
            )
        if self.actions < 0:
            raise RhaeInvalide(f"niveau {self.niveau} : {self.actions} actions négatives")

    @property
    def poids(self) -> int:
        """wₗ = ℓ (§A6.1) : les niveaux tardifs pèsent plus que les premiers."""
        return self.niveau


@dataclass(frozen=True)
class ResultatRhae:
    """RHAE d'un jeu et les deux termes dont il est le minimum (§A6.4)."""

    valeur: float
    efficacite_ponderee: float
    plafond_completion: float
    plafonne: bool
    niveaux: tuple[NiveauJoue, ...] = field(default_factory=tuple)

    def resume(self) -> dict[str, Any]:
        """Résumé journalisable : des nombres, aucune grille (§H11)."""
        return {
            "rhae": self.valeur,
            "efficacite_ponderee": self.efficacite_ponderee,
            "plafond_completion": self.plafond_completion,
            "plafonne": self.plafonne,
            "niveaux": len(self.niveaux),
            "niveaux_completes": sum(1 for niveau in self.niveaux if niveau.complete),
            "actions": sum(niveau.actions for niveau in self.niveaux),
        }


def efficacite_niveau(niveau: NiveauJoue) -> float:
    """eₗ = min(115, 100·(hₗ/aₗ)²) si cₗ=1 et aₗ>0, sinon 0 (§A6.1).

    Le cas `aₗ = 0` avec `cₗ = 1` n'est pas atteignable par le protocole — compléter
    un niveau coûte au moins une action — mais la définition le nomme, donc la garde
    est écrite plutôt que supposée.
    """
    if not niveau.complete or niveau.actions <= 0:
        return 0.0
    return min(EFFICACITE_MAX, 100.0 * (niveau.baseline / niveau.actions) ** 2)


def rhae_jeu(niveaux: Sequence[NiveauJoue]) -> ResultatRhae:
    """RHAE d'un jeu : `min(Σwₗeₗ/Σwₗ, 100·Σwₗcₗ/Σwₗ)` (§A6.1).

    La suite doit couvrir **tous** les niveaux du jeu, de 1 à L, sans trou ni doublon
    (§A6.1 bis) : c'est ce qui donne son sens au plafond par complétion.
    """
    _valider_suite(niveaux)
    somme_poids = sum(niveau.poids for niveau in niveaux)
    efficacite = sum(niveau.poids * efficacite_niveau(niveau) for niveau in niveaux) / somme_poids
    plafond = 100.0 * sum(niveau.poids for niveau in niveaux if niveau.complete) / somme_poids
    return ResultatRhae(
        valeur=min(efficacite, plafond),
        efficacite_ponderee=efficacite,
        plafond_completion=plafond,
        plafonne=plafond < efficacite,
        niveaux=tuple(niveaux),
    )


def rhae_global(valeurs: Sequence[float]) -> float:
    """Moyenne arithmétique des RHAE de jeu sur le périmètre (§A6.1)."""
    if not valeurs:
        raise RhaeInvalide(
            "aucun jeu dans le périmètre : une moyenne sur rien n'est pas 0, elle n'existe pas"
        )
    return sum(valeurs) / len(valeurs)


def niveaux_joues(entrees: Sequence[EntreeJouee], baselines: Sequence[int]) -> list[NiveauJoue]:
    """Pont entre une partie réellement jouée et les entrées de la formule (§A6.4).

    Deux règles font toute la justesse du résultat :

    - **une entrée compte pour le niveau depuis lequel elle a été jouée**, pas pour
      celui qu'elle produit. L'API renvoie l'action qui complète le niveau 1 avec
      `level = 2` ; l'imputer au niveau 2 volerait une action au niveau 1 et en
      ajouterait une au suivant — deux RHAE faux, et de façon compensée, donc
      invisible sur le total des actions ;
    - **la complétion vient du score du serveur**, pas de notre lecture des frames :
      cₗ = 1 si et seulement si le score atteint ℓ à un moment de la partie.

    Les niveaux que l'historique ne mentionne pas figurent quand même au résultat,
    avec aₗ = 0 et cₗ = 0 (§A6.1 bis).
    """
    if not baselines:
        raise RhaeInvalide("aucune baseline : le jeu ne déclare aucun niveau")
    if not entrees:
        raise RhaeInvalide("historique vide : aucune partie n'a été jouée")
    if entrees[0].commande != RESET:
        raise RhaeInvalide(
            f"la première entrée est « {entrees[0].commande} » et non {RESET} : "
            "un historique de partie commence par le RESET de création (§A1.2)"
        )

    actions: dict[int, int] = {}
    origine = entrees[0].niveau
    score_atteint = entrees[0].score
    for entree in entrees[1:]:
        # Le RESET initial est gratuit ; tout ce qui suit coûte une action, RESET
        # en cours de partie compris (§A1.2).
        actions[origine] = actions.get(origine, 0) + 1
        origine = entree.niveau
        score_atteint = max(score_atteint, entree.score)

    for numero in sorted(actions):
        if not 1 <= numero <= len(baselines):
            raise RhaeInvalide(
                f"actions imputées au niveau {numero}, hors des {len(baselines)} "
                "niveaux que le jeu déclare"
            )
    return [
        NiveauJoue(
            niveau=numero,
            baseline=baselines[numero - 1],
            actions=actions.get(numero, 0),
            complete=score_atteint >= numero,
        )
        for numero in range(1, len(baselines) + 1)
    ]


def _valider_suite(niveaux: Sequence[NiveauJoue]) -> None:
    """La suite couvre 1..L exactement : ni trou, ni doublon, ni vide."""
    if not niveaux:
        raise RhaeInvalide("aucun niveau : le RHAE d'un jeu sans niveau n'existe pas")
    numeros = [niveau.niveau for niveau in niveaux]
    attendus = list(range(1, len(numeros) + 1))
    if sorted(numeros) != attendus:
        raise RhaeInvalide(
            f"la suite des niveaux doit couvrir {attendus} exactement ; reçue : {numeros} "
            "— un trou ou un doublon fausserait la somme des poids (§A6.1 bis)"
        )
