"""Superviseur : détecte la stagnation, puis redirige — sans jamais agir.

@spec docs/BACKLOG.md U15 — Superviseur
@spec docs/BACKLOG.md U35 — Sonde fraîche jointe à l'intervention (§H10.4)
@spec docs/SPEC_HARNAIS.md §H10.1 (rôle, séparation stricte des pouvoirs),
      §H10.2 (déclencheurs mesurables), §H10.3 (intervention, cooldown, journalisation),
      §H10.4 (sonde fraîche : appel séparé sans historique, dégradation propre),
      §H5.1 (injection append-only dans le transcript principal)

Mécanisme du papier AVO §3.3 : sur une recherche longue, deux échecs guettent —
l'agent épuise sa piste, ou tourne en rond sur des éditions qui n'améliorent rien. Le
superviseur les détecte et intervient **conditionnellement**.

**Il ne joue jamais d'action** (séparation reprise de Tycho : seul l'acteur agit). Il
n'a d'autre pouvoir que d'écrire un message dans l'historique de l'acteur, lequel
reste libre de ce qu'il en fait. Un superviseur qui agirait doublerait la politique
et rendrait le score inattribuable.

Les déclencheurs sont **mesurés, pas interprétés** : des compteurs et des empreintes,
jamais une appréciation portée sur du texte libre. Un déclencheur qui dépendrait de ce
que le modèle raconte de lui-même serait précisément aveugle quand il tourne en rond.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from avo.config import Config
from avo.context.transcript import Transcript
from avo.llm.client import AuthError, LLMClient, LLMError

_journal = logging.getLogger("avo.superviseur")

#: Version des prompts du superviseur, comme pour ceux de la boucle (§H8.1).
VERSION: Final = "1.1"

#: Fenêtre d'observation des cycles improductifs, et nombre de répétitions qui la
#: rend suspecte (§H10.2).
FENETRE_CYCLE: Final = 12
REPETITIONS_CYCLE: Final = 8

#: Nombre d'entrées consécutives de Bug-Fixing au-delà duquel le volume est anormal.
BUG_FIXING_CONSECUTIFS_MAX: Final = 5

#: Balise du message injecté. L'acteur doit pouvoir distinguer une redirection d'une
#: observation de l'environnement.
BALISE: Final = "[SUPERVISEUR]"

SYSTEME_SUPERVISEUR: Final = """Tu supervises un agent qui explore un jeu inconnu et
semble ne plus progresser. Tu ne joues aucune action : tu diagnostiques et tu
rediriges.

Rends deux choses, brièvement : ce qui bloque selon toi, puis deux ou trois
directions alternatives concrètes que l'agent n'a pas encore essayées. Sois
spécifique et court."""

SYSTEME_SONDE: Final = """Tu découvres une tâche : on te donne son énoncé et la
dernière observation, rien d'autre. Aucun travail antérieur ne t'est connu et tu
n'en supposes aucun.

Propose, brièvement : la première approche que tu tenterais, puis la prochaine
étape concrète qui la met à l'épreuve. Sois spécifique et court."""

#: Intitulé sous lequel la proposition de la sonde rejoint le message
#: d'intervention (§H10.4) : sa provenance — un appel sans historique — est
#: l'information qui permet à l'acteur de la lire comme une alternative non
#: ancrée, pas comme une suite de son propre raisonnement.
INTITULE_SONDE: Final = (
    "Proposition indépendante, formulée sans connaître ton historique ni tes notes :"
)


def empreinte_frame(observation: str) -> str:
    """Empreinte courte d'une observation, pour comparer des frames sans les garder."""
    return hashlib.sha256(observation.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class PasDeTrajectoire:
    """Une action jouée et ce qu'elle a produit. Purement factuel."""

    index: int
    action: str
    empreinte: str
    niveau_complete: bool = False
    bug_fixing: bool = False


@dataclass
class Trajectoire:
    """Historique factuel de la recherche, sur lequel les déclencheurs raisonnent."""

    pas: list[PasDeTrajectoire] = field(default_factory=list)
    actions_depuis_progres: int = 0
    bug_fixing_consecutifs: int = 0

    def enregistrer(
        self,
        action: str,
        observation: str,
        niveau_complete: bool = False,
        bug_fixing: bool = False,
    ) -> None:
        self.pas.append(
            PasDeTrajectoire(
                index=len(self.pas),
                action=action,
                empreinte=empreinte_frame(observation),
                niveau_complete=niveau_complete,
                bug_fixing=bug_fixing,
            )
        )
        self.actions_depuis_progres = 0 if niveau_complete else self.actions_depuis_progres + 1
        self.bug_fixing_consecutifs = self.bug_fixing_consecutifs + 1 if bug_fixing else 0

    def signaler_version_committee(self) -> None:
        """Une entrée de lignée est un progrès au même titre qu'un niveau (§H10.2)."""
        self.actions_depuis_progres = 0

    @property
    def actions(self) -> int:
        return len(self.pas)


def stagnation(trajectoire: Trajectoire, seuil: int) -> str | None:
    """Trop d'actions sans complétion de niveau ni nouvelle entrée de lignée (§H10.2)."""
    if trajectoire.actions_depuis_progres >= seuil:
        return (
            f"stagnation : {trajectoire.actions_depuis_progres} actions sans progrès "
            f"(seuil {seuil})"
        )
    return None


def cycle_improductif(
    trajectoire: Trajectoire,
    fenetre: int = FENETRE_CYCLE,
    repetitions: int = REPETITIONS_CYCLE,
) -> str | None:
    """Mêmes actions répétées sans que la frame change (§H10.2).

    La double condition compte : répéter une action qui produit des effets différents
    est une exploration légitime ; la répéter sans que rien ne bouge ne l'est pas.
    """
    recents = trajectoire.pas[-fenetre:]
    if len(recents) < fenetre:
        return None
    comptes: dict[str, int] = {}
    for index, pas in enumerate(recents):
        precedente = recents[index - 1].empreinte if index else None
        if precedente is not None and pas.empreinte != precedente:
            continue
        comptes[pas.action] = comptes.get(pas.action, 0) + 1
    for action, compte in comptes.items():
        if compte >= repetitions:
            return (
                f"cycle improductif : « {action} » répétée {compte} fois sur "
                f"{fenetre} actions sans changement de frame"
            )
    return None


def rafale_bug_fixing(
    trajectoire: Trajectoire, maximum: int = BUG_FIXING_CONSECUTIFS_MAX
) -> str | None:
    """Volume anormal de corrections consécutives (§H10.2)."""
    if trajectoire.bug_fixing_consecutifs > maximum:
        return (
            f"corrections en rafale : {trajectoire.bug_fixing_consecutifs} passages "
            f"consécutifs en Bug-Fixing (maximum {maximum})"
        )
    return None


@dataclass
class Intervention:
    """Ce qu'une intervention a produit."""

    motif: str
    directive: str
    action_declencheuse: int
    #: Proposition de la sonde fraîche (§H10.4), `None` quand la sonde est
    #: désactivée, a dégradé, ou a rendu une proposition vide.
    proposition: str | None = None

    @property
    def message(self) -> str:
        """Le message `[SUPERVISEUR]` complet, tel que l'acteur le reçoit (§H10.3).

        UN seul message, quel que soit le mode de remise : le diagnostic, puis la
        proposition de la sonde quand elle existe, sous son intitulé de provenance.
        """
        if self.proposition is None:
            return f"{BALISE} {self.directive}"
        return f"{BALISE} {self.directive}\n\n{INTITULE_SONDE}\n{self.proposition}"


class Superviseur:
    """Surveille la trajectoire et redirige l'acteur quand elle s'enlise (§H10)."""

    def __init__(self, config: Config, client: LLMClient) -> None:
        self.config = config
        self.client = client
        self.trajectoire = Trajectoire()
        self.interventions: list[Intervention] = []
        self._action_derniere_intervention: int | None = None

    # ------------------------------------------------------------- déclencheurs
    def motif_declencheur(self) -> str | None:
        """Premier motif applicable, ou `None`. Ordre stable pour la reproductibilité."""
        detecteurs: tuple[Callable[[], str | None], ...] = (
            lambda: stagnation(self.trajectoire, self.config.sup_stall_actions),
            lambda: cycle_improductif(self.trajectoire),
            lambda: rafale_bug_fixing(self.trajectoire),
        )
        for detecteur in detecteurs:
            motif = detecteur()
            if motif is not None:
                return motif
        return None

    def en_cooldown(self) -> bool:
        """Une intervention a-t-elle eu lieu il y a moins de `AVO_SUP_COOLDOWN` actions ?"""
        if self._action_derniere_intervention is None:
            return False
        ecoulees = self.trajectoire.actions - self._action_derniere_intervention
        return ecoulees < self.config.sup_cooldown

    def doit_intervenir(self) -> str | None:
        """Motif si une intervention est due ET permise par le cooldown (§H10.3)."""
        motif = self.motif_declencheur()
        if motif is None or self.en_cooldown():
            return None
        return motif

    # ------------------------------------------------------------- intervention
    def _resume_trajectoire(self, derniers: int = 12) -> str:
        lignes = [
            f"- action {pas.index + 1} : {pas.action} → frame {pas.empreinte}"
            + (" [niveau complété]" if pas.niveau_complete else "")
            for pas in self.trajectoire.pas[-derniers:]
        ]
        return "\n".join(lignes) or "(aucune action enregistrée)"

    def diagnostiquer(self, motif: str, notes: str, observation: str) -> str:
        """Appel LLM **séparé**, sur un contexte propre (§H10.3).

        Le superviseur ne voit pas l'historique de l'acteur : il en reçoit un résumé
        factuel. C'est délibéré — un superviseur qui hériterait du contexte hériterait
        aussi de l'ornière dont il doit sortir l'acteur.
        """
        transcript = (
            Transcript.ouvrir(SYSTEME_SUPERVISEUR)
            .utilisateur(f"Motif du déclenchement : {motif}")
            .utilisateur(f"Dernières actions :\n{self._resume_trajectoire()}")
            .utilisateur(f"Notes de l'agent :\n{notes}")
            .utilisateur(f"Observation courante :\n{observation}")
        )
        resultat = self.client.chat(transcript.pour_api())
        return resultat.content.strip()

    def sonder_frais(self, enonce: str, observation: str) -> str | None:
        """Appel FRAIS (§H10.4) : l'énoncé de tâche brut et la dernière observation.

        Ni notes, ni trajectoire, ni motif, ni diagnostic : toute fuite d'historique
        réintroduirait l'ancrage que l'appel a pour objet d'éviter. Rend `None` quand
        la sonde est désactivée, que l'appel a dégradé ou que la proposition est
        vide — l'intervention se fait alors sans elle, jamais une panne. Seule
        `AuthError` se propage : elle est fatale partout (§H4.4).
        """
        if not self.config.sup_sonde_fraiche:
            return None
        transcript = (
            Transcript.ouvrir(SYSTEME_SONDE)
            .utilisateur(f"Énoncé de la tâche :\n{enonce}")
            .utilisateur(f"Dernière observation :\n{observation}")
        )
        try:
            resultat = self.client.chat(transcript.pour_api())
        except AuthError:
            raise
        except LLMError as erreur:
            _journal.info(
                "sonde fraîche dégradée",
                extra={"erreur": type(erreur).__name__},
            )
            return None
        proposition = resultat.content.strip()
        return proposition or None

    def intervenir(
        self,
        transcript: Transcript,
        motif: str,
        notes: str,
        observation: str,
        enonce: str = "",
    ) -> tuple[Transcript, Intervention]:
        """Injecte la redirection dans l'historique de l'acteur, en append (§H5.1).

        Le message est balisé : l'acteur doit pouvoir distinguer une redirection d'une
        observation de l'environnement. Quand la sonde fraîche (§H10.4) rend une
        proposition, elle rejoint le MÊME message, sous son intitulé de provenance.
        """
        directive = self.diagnostiquer(motif, notes, observation)
        proposition = self.sonder_frais(enonce, observation)
        intervention = Intervention(
            motif=motif,
            directive=directive,
            action_declencheuse=self.trajectoire.actions,
            proposition=proposition,
        )
        self.interventions.append(intervention)
        self._action_derniere_intervention = self.trajectoire.actions
        _journal.info(
            "intervention du superviseur",
            extra={
                "motif": motif,
                "action": self.trajectoire.actions,
                "interventions": len(self.interventions),
                "directive_caracteres": len(directive),
                "proposition_caracteres": len(proposition or ""),
            },
        )
        return transcript.utilisateur(intervention.message), intervention

    def resume(self) -> dict[str, Any]:
        """Résumé journalisable : des compteurs et des motifs, aucun contenu."""
        return {
            "actions_observees": self.trajectoire.actions,
            "actions_depuis_progres": self.trajectoire.actions_depuis_progres,
            "bug_fixing_consecutifs": self.trajectoire.bug_fixing_consecutifs,
            "interventions": len(self.interventions),
            "motifs": [intervention.motif for intervention in self.interventions],
            "sondes_fraiches": sum(
                1 for intervention in self.interventions if intervention.proposition
            ),
            "prompts_version": VERSION,
        }


def motifs(interventions: Sequence[Intervention]) -> list[str]:
    """Motifs des interventions, pour le rapport de campagne."""
    return [intervention.motif for intervention in interventions]
