"""Scénario du banc c : intention seedée, état attendu, simulateur d'utilisateur.

@spec docs/BACKLOG.md U29c1 — intention + état attendu + simulateur `scripte`
@spec docs/SPEC_BANCS.md §S16.1 (une intention par épisode : famille
      équiprobable, éligibilité 2/3–1/3, candidat tiré dans la base, erreur
      nommée sans candidat), §S16.2 (état attendu : mutation exacte si
      éligible, base inchangée sinon ; jamais montré à l'agent), §S16.3
      (utilisateur `scripte` : déterministe, révèle son nom quand on le lui
      demande, accepte tout refus motivé, dit au revoir quand l'issue est
      annoncée — sans lui, aucune preuve n'est rejouable §S1.4)

L'utilisateur `llm` du mode live appartient à U29c2 (§S16.3) : ce module ne
porte que le simulateur déterministe des preuves et du rejeu.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

from avo.bancs.tau.domaine import (
    STATUT_EN_ATTENTE,
    STATUT_EXPEDIEE,
    STATUT_LIVREE,
    BaseDetail,
)

#: Familles d'intention (§S16.1), équiprobables.
FAMILLES_INTENTION = ("annuler", "modifier", "retourner")

#: Domaines du banc (§S14.3) ; `detail` seul livré.
DOMAINES = ("detail",)

#: Statuts qui rendent l'intention ÉLIGIBLE (politique §S15.3) et INÉLIGIBLE
#: (§S16.1) — par famille.
_STATUTS_ELIGIBLES = {
    "annuler": (STATUT_EN_ATTENTE,),
    "modifier": (STATUT_EN_ATTENTE,),
    "retourner": (STATUT_LIVREE,),
}
_STATUTS_INELIGIBLES = {
    "annuler": (STATUT_EXPEDIEE, STATUT_LIVREE),
    "modifier": (STATUT_EXPEDIEE, STATUT_LIVREE),
    "retourner": (STATUT_EN_ATTENTE, STATUT_EXPEDIEE),
}


class ScenarioImpossible(RuntimeError):
    """La base tirée n'offre aucun candidat à l'intention (§S16.1) : le message
    nomme famille et éligibilité — le point de mesure prend un autre seed."""


@dataclass(frozen=True)
class Scenario:
    """L'intention d'un épisode (§S16.1) ; jamais montrée à l'agent (§S14.4)."""

    seed: int
    domaine: str
    famille: str
    eligible: bool
    client_id: str
    client_nom: str
    commande_id: str
    article_id: str = ""
    quantite: int = 0


def generer_episode_tau(seed: int, domaine: str = "detail") -> tuple[BaseDetail, Scenario, str]:
    """Engendre (base, scénario, état attendu) du seed (§S15.1, §S16.1, §S16.2).

    À seed égal, le dump initial, le scénario et l'état attendu sont identiques
    octet pour octet (§S1.4) : le rng est unique et son ordre d'appel fixe.
    """
    if domaine not in DOMAINES:
        raise ScenarioImpossible(
            f"domaine inconnu : « {domaine} ». Disponibles : {', '.join(DOMAINES)}."
        )
    rng = Random(seed)
    base = BaseDetail.creer(rng)
    famille = rng.choice(FAMILLES_INTENTION)
    eligible = rng.random() < 2 / 3
    scenario = _tirer_scenario(base, seed, domaine, famille, eligible, rng)
    return base, scenario, _etat_attendu(base, scenario)


def _tirer_scenario(
    base: BaseDetail,
    seed: int,
    domaine: str,
    famille: str,
    eligible: bool,
    rng: Random,
) -> Scenario:
    """Choisit la commande qui réalise (famille, éligibilité) — §S16.1."""
    statuts = _STATUTS_ELIGIBLES[famille] if eligible else _STATUTS_INELIGIBLES[famille]
    candidates = base.commandes_par_statut(statuts)
    if famille == "modifier":
        candidates = [(c, cl) for c, cl in candidates if base.lignes_de(c)]
    if not candidates:
        raise ScenarioImpossible(
            f"aucun candidat pour l'intention « {famille} » "
            f"({'éligible' if eligible else 'inéligible'}) sur cette base : "
            "prendre un autre seed (§S16.1)."
        )
    commande, client = rng.choice(candidates)
    nom = base.nom_client(client) or client
    if famille != "modifier":
        return Scenario(seed, domaine, famille, eligible, client, nom, commande)
    article, quantite_actuelle = rng.choice(base.lignes_de(commande))
    tirage = rng.randint(1, 4)
    quantite = tirage + 1 if tirage >= quantite_actuelle else tirage
    return Scenario(seed, domaine, famille, eligible, client, nom, commande, article, quantite)


def _etat_attendu(base: BaseDetail, scenario: Scenario) -> str:
    """Le dump canonique attendu à la fin de l'épisode (§S16.2)."""
    copie = base.cloner()
    try:
        if scenario.eligible:
            if scenario.famille == "annuler":
                copie.annuler_commande(scenario.commande_id)
            elif scenario.famille == "modifier":
                copie.modifier_ligne(scenario.commande_id, scenario.article_id, scenario.quantite)
            else:
                copie.retourner_commande(scenario.commande_id)
        return copie.dump_canonique()
    finally:
        copie.fermer()


#: Gabarits du premier message (§S16.3), tirés au rng du simulateur.
_SALUTATIONS = ("Bonjour", "Bonjour à vous", "Bonsoir")
_MOTS_ISSUE = (
    "annulée",
    "annulee",
    "modifiée",
    "modifiee",
    "retournée",
    "retournee",
    "quantité mise à jour",
    "ne peux pas",
    "ne pouvons pas",
    "impossible",
    "refus",
    "n'est pas possible",
    "au revoir",
)


class SimulateurScripte:
    """L'utilisateur `scripte` (§S16.3) : déterministe, porté par le scénario.

    Politique d'énonciation, dans cet ordre de lecture du message de l'agent :
    question sur l'identité → le nom ; question sur la commande → l'identifiant ;
    issue annoncée (transaction faite, ou refus motivé) → au revoir ; sinon une
    relance neutre. C'est un DÉCOR déterministe, pas un juge : la conformité se
    mesure à l'évaluateur (§S17.1), jamais à ses répliques.
    """

    def __init__(self, scenario: Scenario) -> None:
        self._scenario = scenario
        self._rng = Random(f"utilisateur-{scenario.seed}")

    def premier_message(self) -> str:
        """Salutation + intention en langage naturel, nommant la commande (§S16.3)."""
        scenario = self._scenario
        salutation = self._rng.choice(_SALUTATIONS)
        if scenario.famille == "annuler":
            demande = f"je voudrais annuler ma commande {scenario.commande_id}"
        elif scenario.famille == "modifier":
            demande = (
                f"je voudrais passer la quantité de {scenario.article_id} à "
                f"{scenario.quantite} dans ma commande {scenario.commande_id}"
            )
        else:
            demande = f"je voudrais retourner ma commande {scenario.commande_id}"
        return f"{salutation}, {demande}."

    def repondre(self, message_agent: str) -> str:
        """La réplique déterministe au message de l'agent (§S16.3)."""
        minuscule = message_agent.lower()
        if "nom" in minuscule or "qui êtes-vous" in minuscule or "identit" in minuscule:
            return f"Je m'appelle {self._scenario.client_nom}."
        if "commande" in minuscule and "?" in minuscule:
            return f"Il s'agit de la commande {self._scenario.commande_id}."
        if any(mot in minuscule for mot in _MOTS_ISSUE):
            return "Merci, au revoir."
        return "D'accord."
