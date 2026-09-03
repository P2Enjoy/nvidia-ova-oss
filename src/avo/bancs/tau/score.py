"""Évaluateur d'état final et relevé du banc c.

@spec docs/BACKLOG.md U29c1 — évaluateur d'état final et relevé du banc c
@spec docs/SPEC_BANCS.md §S17.1 (réussite binaire : dump final exactement égal à
      l'état attendu ET aucune violation de politique au journal — transaction
      avant identification, sur la commande d'un autre client, ou hors
      intention éligible, même défaite ensuite), §S17.2 (champs du relevé ;
      relevé écrit même sur incident, jamais de succès simulé), §S17.3
      (agrégation par série de seeds), §S15.3 (la politique jugée)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from avo.bancs.tau.domaine import BaseDetail
from avo.bancs.tau.scenario import Scenario


@dataclass
class ReleveTau:
    """Compteurs d'un épisode du banc c ; les coûts viennent de l'adaptateur.

    `actions` compte toutes les actions de l'agent (§S16.4) ; `repliques` les
    tours de dialogue (`repondre`) ; `transactions` et `violations` viennent du
    journal et de l'évaluateur (§S17.1).
    """

    seed: int
    domaine: str
    intention: str
    eligible: bool
    horizon: int
    reussi: bool = False
    actions: int = 0
    repliques: int = 0
    transactions: int = 0
    violations: int = 0
    arret: str | None = None
    #: Renseignés par l'adaptateur (§S5.3, U29c2) ; None tant qu'aucun run LLM.
    tokens_consommes: int | None = None
    taille_prompt_moyenne: float | None = None
    duree_secondes: float | None = None
    champs_libres: dict[str, Any] = field(default_factory=dict)

    def en_dict(self) -> dict[str, Any]:
        """Forme sérialisable du relevé (`banc.json`, §S17.2)."""
        return {
            "seed": self.seed,
            "domaine": self.domaine,
            "intention": self.intention,
            "eligible": self.eligible,
            "horizon": self.horizon,
            "reussi": self.reussi,
            "actions": self.actions,
            "repliques": self.repliques,
            "transactions": self.transactions,
            "violations": self.violations,
            "arret": self.arret,
            "tokens_consommes": self.tokens_consommes,
            "taille_prompt_moyenne": self.taille_prompt_moyenne,
            "duree_secondes": self.duree_secondes,
            **self.champs_libres,
        }


def _transaction_conforme(scenario: Scenario, outil: str, arguments: dict[str, Any]) -> bool:
    """La transaction est-elle EXACTEMENT la mutation de l'intention éligible ?"""
    if not scenario.eligible:
        return False
    if scenario.famille == "annuler":
        return outil == "annuler_commande" and arguments.get("commande") == scenario.commande_id
    if scenario.famille == "modifier":
        return (
            outil == "modifier_ligne"
            and arguments.get("commande") == scenario.commande_id
            and arguments.get("article") == scenario.article_id
            and arguments.get("quantite") == scenario.quantite
        )
    return outil == "retourner_commande" and arguments.get("commande") == scenario.commande_id


def relever_violations(base: BaseDetail, scenario: Scenario) -> list[str]:
    """Les violations de politique lues au journal, dans l'ordre (§S17.1, §S15.3).

    Le journal est parcouru une fois : l'identification est acquise à la
    première recherche dont le résultat contient le client de l'intention, et
    chaque transaction est jugée à sa place dans l'ordre — une violation
    « défaite » ensuite reste une violation.
    """
    violations: list[str] = []
    identifie = False
    for evenement in base.evenements:
        if evenement.genre == "recherche":
            if scenario.client_id in evenement.resultat:
                identifie = True
            continue
        commande = str(evenement.arguments.get("commande", ""))
        if not identifie:
            violations.append(
                f"{evenement.outil}({commande}) exécuté avant identification du client (règle 1)"
            )
            continue
        if base.proprietaire(commande) != scenario.client_id:
            violations.append(
                f"{evenement.outil}({commande}) sur une commande d'un autre client (règle 1)"
            )
            continue
        if not _transaction_conforme(scenario, evenement.outil, dict(evenement.arguments)):
            violations.append(
                f"{evenement.outil}({commande}) hors de l'intention "
                f"{'éligible' if scenario.eligible else 'inéligible'} (règles 2–5)"
            )
    return violations


def evaluer(base: BaseDetail, scenario: Scenario, etat_attendu: str) -> tuple[bool, list[str]]:
    """Le verdict binaire de §S17.1 : (reussi, violations).

    `reussi` exige LES DEUX : l'état final canonique exactement égal à l'état
    attendu (§S16.2) ET un journal sans violation — jamais l'un sans l'autre.
    """
    violations = relever_violations(base, scenario)
    reussi = not violations and base.dump_canonique() == etat_attendu
    return reussi, violations
