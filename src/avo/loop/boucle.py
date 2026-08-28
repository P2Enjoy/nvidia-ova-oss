"""Boucle agent : un tour = Planning → Implementation → Evaluation → [Bug-Fixing].

@spec docs/BACKLOG.md U13 — Boucle agent P→I→E→B
@spec docs/SPEC_HARNAIS.md §H8.1 (états), §H8.2 (un tour), §H8.3 (bornes),
      §H8.4 (continuation, supervision, métriques, lignée branchées sur la boucle),
      §H7.1 (outils exposés selon l'état), §H5.1 (historique append-only),
      §H5.3 et §H5.4 (continuation préventive et réactive), §H9.2 (lignée),
      §H10.3 (intervention du superviseur), §H11.2 (métriques),
      §H12 (politique de raisonnement portée par la configuration)
@spec docs/SPEC_ARCAGI3.md §A5.1 (direct-interaction : aucune règle de jeu fournie)

La boucle ne connaît aucun jeu. Elle parle à un `Environnement` par un contrat
minimal, ce qui permet de l'éprouver sur un environnement factice en mémoire avant
que l'interface ARC n'existe (U19), et garantit qu'aucune connaissance de jeu ne peut
s'y glisser.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from avo.config import Config
from avo.context.contexte import INVITATION_CONTINUATION, Contexte
from avo.lineage import Lignee
from avo.llm.client import ChatResult, ContextOverflow, LLMClient
from avo.loop import prompts
from avo.loop.etats import Evenement, Phase, suivant
from avo.memory.notes import Notes
from avo.memory.workspace import Workspace
from avo.supervisor import Superviseur
from avo.tools.registre import RegistreOutils

_journal = logging.getLogger("avo.boucle")

#: Étiquettes d'outils exposées à chaque phase (§H7.1). Les outils d'action ne sont
#: offerts qu'à l'état où agir est permis : hors de là, le modèle ne peut pas
#: dépenser une action par mégarde.
OUTILS_PAR_PHASE: dict[Phase, tuple[str, ...]] = {
    Phase.PLANNING: ("notes", "inspection"),
    Phase.IMPLEMENTATION: ("action",),
    Phase.EVALUATION: ("notes", "inspection"),
    Phase.BUG_FIXING: ("notes", "inspection"),
}

#: Fraction du budget d'actions au-delà de laquelle l'agent est prévenu (§H8.3).
SEUIL_AVERTISSEMENT_BORNE = 0.9


class Issue(Protocol):
    """Ce qu'une action d'environnement rend en retour."""

    @property
    def observation(self) -> str: ...
    @property
    def evenement(self) -> Evenement: ...


class Environnement(Protocol):
    """Contrat minimal d'un environnement de tâche (§H8.2).

    Volontairement pauvre : la boucle ne doit rien pouvoir apprendre du jeu autrement
    qu'en agissant. L'interface ARC-AGI-3 l'implémentera en U19.

    L'action est jouée **par l'outil d'action** (§H8.1), pas par la boucle : c'est le
    registre qui l'exécute, comme n'importe quel outil, et l'environnement conserve
    l'issue produite. La boucle la relit ensuite. Sans ce détour, l'outil d'action
    serait une déclaration décorative que rien n'exécuterait.
    """

    def observation(self) -> str: ...
    def actions_disponibles(self) -> Sequence[str]: ...
    def derniere_issue(self) -> Issue | None: ...


class BorneAtteinte(RuntimeError):
    """Une borne d'actions a été franchie : le jeu s'arrête proprement (§H8.3)."""


@dataclass
class Tour:
    """Trace d'un tour, pour les métriques et le rapport."""

    numero: int
    phase_finale: Phase
    evenement: Evenement | None = None
    action: str | None = None
    outils_executes: int = 0
    garde_outils_franchie: bool = False


@dataclass
class Bilan:
    """Ce qu'une exécution a produit (§H8.3)."""

    tours: list[Tour] = field(default_factory=list)
    actions_niveau: int = 0
    actions_jeu: int = 0
    niveaux_completes: int = 0
    game_overs: int = 0
    arret: str = "tours_epuises"
    #: Événements de run, exigés par le rapport de campagne (§A7.3).
    continuations: int = 0
    depassements: int = 0
    interventions: int = 0
    versions_committees: int = 0
    tokens_prompt: int = 0
    tokens_generes: int = 0

    def resume(self) -> dict[str, Any]:
        return {
            "tours": len(self.tours),
            "actions_jeu": self.actions_jeu,
            "actions_niveau": self.actions_niveau,
            "niveaux_completes": self.niveaux_completes,
            "game_overs": self.game_overs,
            "arret": self.arret,
            "continuations": self.continuations,
            "depassements": self.depassements,
            "interventions": self.interventions,
            "versions_committees": self.versions_committees,
            "tokens_prompt": self.tokens_prompt,
            "tokens_generes": self.tokens_generes,
            "prompts_version": prompts.VERSION,
        }


class BoucleAgent:
    """Orchestre un tour de jeu et les transitions entre phases (§H8.1, §H8.2)."""

    def __init__(
        self,
        config: Config,
        client: LLMClient,
        registre: RegistreOutils,
        environnement: Environnement,
        notes: Notes,
        contexte: Contexte | None = None,
        workspace: Workspace | None = None,
        superviseur: Superviseur | None = None,
        lignee: Lignee | None = None,
        jeu: str = "",
    ) -> None:
        """Les quatre derniers paramètres sont les branchements de §H8.4.

        Ils sont optionnels **par construction** : sans eux, la boucle se comporte
        exactement comme avant, ce qui préserve les preuves qui l'éprouvent sur un
        environnement factice, sans workspace ni services.
        """
        self.config = config
        self.client = client
        self.registre = registre
        self.environnement = environnement
        self.notes = notes
        self.contexte = contexte or Contexte(config=config, systeme=prompts.SYSTEME)
        self.workspace = workspace
        self.superviseur = superviseur
        self.lignee = lignee
        self.jeu = jeu
        self.phase = Phase.PLANNING
        self.bilan = Bilan()

    # ------------------------------------------------------------------- bornes
    def _borne_franchie(self) -> str | None:
        if self.bilan.actions_niveau >= self.config.actions_max_niveau:
            return f"borne d'actions du niveau atteinte ({self.config.actions_max_niveau})"
        if self.bilan.actions_jeu >= self.config.actions_max_jeu:
            return f"borne d'actions du jeu atteinte ({self.config.actions_max_jeu})"
        return None

    def _borne_proche(self) -> bool:
        return (
            self.bilan.actions_niveau >= SEUIL_AVERTISSEMENT_BORNE * self.config.actions_max_niveau
        )

    # -------------------------------------------------------------------- phases
    def _interroger(self, phase: Phase, invite: str) -> Any:
        """Un échange avec le modèle pour une phase, outils filtrés par l'état (§H8.4).

        La continuation encadre l'appel des deux côtés : préventive si le seuil est
        déjà franchi, réactive si le serveur refuse le contexte. Dans le second cas
        aucun appel n'est refait sur le segment plein (§H5.4) : on n'y retourne jamais.
        """
        if self.contexte.seuil_atteint():
            self._continuer(preventive=True)
        self.contexte.ajouter_observation(invite)
        try:
            resultat = self._appeler(phase)
        except ContextOverflow as erreur:
            self.contexte.absorber_depassement(erreur)
            self.bilan.depassements += 1
            self._metrique("depassement", phase=phase.value, plafond=erreur.max_context_tokens)
            self._continuer(preventive=False)
            self.contexte.ajouter_observation(invite)
            resultat = self._appeler(phase)
        self.contexte.enregistrer_reponse(resultat)
        return resultat

    def _appeler(self, phase: Phase) -> ChatResult:
        """Un appel au modèle, mesuré (§H11.2). Les compteurs viennent du serveur."""
        resultat = self.client.chat(
            self.contexte.transcript.pour_api(),
            self.registre.schemas(OUTILS_PAR_PHASE[phase]),
        )
        self.bilan.tokens_prompt += resultat.prompt_eval_count
        self.bilan.tokens_generes += resultat.eval_count
        self._metrique(
            "llm",
            phase=phase.value,
            tokens_prompt=resultat.prompt_eval_count,
            tokens_generes=resultat.eval_count,
            duree_ms=resultat.total_duration_ms,
            tronquee=resultat.tronquee,
            segment=self.contexte.segment,
        )
        return resultat

    # --------------------------------------------------------------- H8.4
    def _metrique(self, type_evenement: str, **champs: Any) -> None:
        """Écrit une métrique si un workspace est branché (§H11.2)."""
        if self.workspace is not None:
            self.workspace.metrique(type_evenement, jeu=self.jeu, **champs)

    def _etat_de_continuation(self) -> str:
        """État écrit PAR LE HARNAIS, pour le chemin réactif (§H5.4, §H8.4).

        Le segment vient d'être refusé : lui demander quoi que ce soit le referait
        refuser. Ce résumé est donc factuel — ce que la boucle sait d'elle-même — et
        ne coûte aucun appel.
        """
        return (
            "Reprise après un refus de contexte : l'historique de conversation a été "
            "archivé sans pouvoir être résumé par toi. Ce que le harnais sait : "
            f"phase {self.phase.value}, tour {len(self.bilan.tours) + 1}, "
            f"{self.bilan.actions_jeu} actions jouées dont "
            f"{self.bilan.actions_niveau} sur le niveau courant, "
            f"{self.bilan.niveaux_completes} niveau(x) complété(s). "
            "Tes notes ci-dessous sont intactes : elles sont ta mémoire."
        )

    def _continuer(self, preventive: bool) -> None:
        """Ouvre un segment frais et archive celui qui se ferme (§H5.3, §H8.4)."""
        if preventive:
            self.contexte.ajouter_observation(INVITATION_CONTINUATION)
            etat = self._appeler(self.phase).content.strip()
            self.contexte.transcript = self.contexte.transcript.assistant(etat)
        else:
            etat = self._etat_de_continuation()
        self.contexte.continuer(
            etat, self.notes.pour_segment_frais(), self.environnement.observation()
        )
        self.bilan.continuations += 1
        self._archiver(self.contexte.segments_archives[-1])
        self._metrique(
            "continuation",
            preventive=preventive,
            segment=self.contexte.segment,
            caracteres_etat=len(etat),
        )

    def _archiver(self, transcript: Any) -> None:
        """Écrit un segment intégral dans `transcripts/` (§H11.3)."""
        if self.workspace is None:
            return
        numero = self.workspace.nouveau_segment()
        for message in transcript.pour_api():
            self.workspace.ajouter_au_transcript(numero, message)

    def _superviser(self, tour: Tour, observation: str) -> None:
        """Tient la trajectoire et laisse le superviseur décider (§H10.3, §H8.4).

        La boucle n'interprète pas le diagnostic : elle l'ajoute en fin d'historique,
        et le tour suivant s'y confronte. Le superviseur ne joue jamais d'action.
        """
        if self.superviseur is None or tour.action is None:
            return
        self.superviseur.trajectoire.enregistrer(
            action=tour.action,
            observation=observation,
            niveau_complete=tour.evenement is Evenement.NIVEAU_COMPLETE,
            bug_fixing=tour.evenement in (Evenement.CONTRADICTION, Evenement.GAME_OVER),
        )
        motif = self.superviseur.doit_intervenir()
        if motif is None:
            return
        self.contexte.transcript, intervention = self.superviseur.intervenir(
            self.contexte.transcript,
            motif,
            self.notes.pour_segment_frais(),
            observation,
        )
        self.bilan.interventions += 1
        self._metrique("superviseur", motif=motif, action=intervention.action_declencheuse)

    def _proposer_a_la_lignee(self) -> None:
        """Une complétion de niveau propose une version (§H9.2, §H8.4).

        La politique « correct ∧ ≥ meilleur » décide seule : un refus n'est pas un
        incident, c'est le mécanisme qui fonctionne.
        """
        if self.lignee is None:
            return
        decision = self.lignee.proposer(
            self.bilan,
            self.notes.toutes(),
            {"jeu": self.jeu, "tours": len(self.bilan.tours)},
        )
        self._metrique(
            "lignee", acceptee=decision.acceptee, motif=decision.motif, score=decision.score
        )
        if not decision.acceptee:
            return
        self.bilan.versions_committees += 1
        if self.superviseur is not None:
            self.superviseur.trajectoire.signaler_version_committee()

    def _executer_outils(self, resultat: Any, tour: Tour) -> None:
        if not resultat.tool_calls:
            return
        execution = self.registre.executer(
            resultat.tool_calls,
            self.contexte.transcript,
            self.config.tool_steps_max,
            deja_executes=tour.outils_executes,
        )
        self.contexte.transcript = execution.transcript
        tour.outils_executes = execution.executes
        tour.garde_outils_franchie = execution.garde_franchie or tour.garde_outils_franchie

    # ---------------------------------------------------------------------- tour
    def jouer_tour(self, numero: int) -> Tour:
        """Déroule un tour complet : P → I → E, puis B si nécessaire (§H8.2)."""
        tour = Tour(numero=numero, phase_finale=self.phase)

        # --- Planning : hypothèses, choix, prédiction énoncée.
        invite = prompts.PLANNING
        if self._borne_proche():
            invite = f"{prompts.BORNE_PROCHE}\n\n{invite}"
        planning = self._interroger(Phase.PLANNING, self._avec_observation(invite))
        self._executer_outils(planning, tour)
        self.phase = suivant(self.phase, Evenement.ACTION_CHOISIE)

        # --- Implementation : exactement une action d'environnement.
        implementation = self._interroger(Phase.IMPLEMENTATION, prompts.IMPLEMENTATION)
        appel = self._action_demandee(implementation)
        if appel is None:
            # Aucun outil d'action appelé : le tour n'a pas agi. On revient planifier
            # plutôt que de forcer une action que le modèle n'a pas choisie.
            self.phase = Phase.PLANNING
            tour.phase_finale = self.phase
            _journal.info("tour sans action", extra={"tour": numero})
            return tour

        issue = self._jouer_action(appel, tour)
        if issue is None:
            self.phase = Phase.PLANNING
            tour.phase_finale = self.phase
            _journal.info("action sans issue rendue par l'environnement", extra={"tour": numero})
            return tour
        tour.action = appel.nom
        self.phase = suivant(self.phase, Evenement.ACTION_JOUEE)

        # --- Evaluation : confronter, énoncer, mettre à jour.
        evaluation = self._interroger(
            Phase.EVALUATION, f"{prompts.EVALUATION}\n\n{issue.observation}"
        )
        self._executer_outils(evaluation, tour)
        evenement = self._evenement_apres_evaluation(issue, evaluation)
        tour.evenement = evenement
        self.phase = suivant(self.phase, evenement)

        # --- Bug-Fixing : conditionnel.
        if self.phase is Phase.BUG_FIXING:
            correction = self._interroger(Phase.BUG_FIXING, prompts.BUG_FIXING)
            self._executer_outils(correction, tour)
            self.phase = suivant(self.phase, Evenement.REVISION_FAITE)

        # --- Branchements de §H8.4, dans cet ordre : une version committée est un
        # progrès que le superviseur doit connaître avant de juger la trajectoire.
        if evenement is Evenement.NIVEAU_COMPLETE:
            self._proposer_a_la_lignee()
        self._superviser(tour, issue.observation)

        tour.phase_finale = self.phase
        return tour

    def executer(
        self, tours_max: int, arret_anticipe: Callable[[], str | None] | None = None
    ) -> Bilan:
        """Enchaîne les tours jusqu'à une borne ou l'épuisement du quota (§H8.3).

        `arret_anticipe` est consulté **entre deux tours** : c'est ainsi que la
        campagne fait respecter ses budgets de temps et de tokens sans jamais
        interrompre une opération en vol (§A7.4, qui concilie ce besoin avec §H8.3).
        """
        for numero in range(1, tours_max + 1):
            motif = self._borne_franchie()
            if motif is None and arret_anticipe is not None:
                motif = arret_anticipe()
            if motif is not None:
                return self._clore(motif, numero)
            self.bilan.tours.append(self.jouer_tour(numero))
        return self._clore("tours_epuises", tours_max)

    def _clore(self, motif: str, tour: int) -> Bilan:
        """Arrête proprement : le motif est nommé, le dernier segment archivé."""
        self.bilan.arret = motif
        _journal.info("fin d'exécution", extra={"motif": motif, "tour": tour})
        self._metrique("arret", motif=motif, tour=tour, **self.bilan.resume())
        self._archiver(self.contexte.transcript)
        return self.bilan

    # ----------------------------------------------------------------- internes
    def _avec_observation(self, invite: str) -> str:
        etat = (
            f"Observation :\n{self.environnement.observation()}\n\n"
            f"Actions disponibles : {', '.join(self.environnement.actions_disponibles())}"
        )
        return f"{etat}\n\n{invite}"

    def _action_demandee(self, resultat: Any) -> Any | None:
        """Premier appel d'outil d'ACTION demandé, s'il y en a un.

        Un appel à une note ou à une inspection glissé ici n'est pas une action :
        seule une action d'environnement fait avancer le tour et coûte au score.
        """
        actions = {schema["function"]["name"] for schema in self.registre.schemas(("action",))}
        for appel in resultat.tool_calls:
            if appel.valide and appel.nom in actions:
                return appel
        return None

    def _jouer_action(self, appel: Any, tour: Tour) -> Issue | None:
        """Exécute l'action **par le registre** (§H8.1), puis relit l'issue.

        Le résultat textuel de l'outil devient un message `role: tool`, comme pour
        tout autre outil ; l'issue typée vient de l'environnement, qui reste
        l'autorité sur ce qui s'est produit. Sans ce détour, l'outil d'action serait
        une déclaration décorative que rien n'exécuterait.
        """
        execution = self.registre.executer(
            [appel],
            self.contexte.transcript,
            self.config.tool_steps_max,
            deja_executes=tour.outils_executes,
        )
        self.contexte.transcript = execution.transcript
        tour.outils_executes = execution.executes
        tour.garde_outils_franchie = execution.garde_franchie or tour.garde_outils_franchie
        issue = self.environnement.derniere_issue()
        if issue is None:
            return None
        self.bilan.actions_niveau += 1
        self.bilan.actions_jeu += 1
        self._metrique(
            "action",
            action=appel.nom,
            tour=tour.numero,
            actions_jeu=self.bilan.actions_jeu,
            actions_niveau=self.bilan.actions_niveau,
            evenement=issue.evenement.value,
        )
        return issue

    def _evenement_apres_evaluation(self, issue: Issue, evaluation: Any) -> Evenement:
        """L'environnement prime ; le modèle ne tranche que la contradiction.

        Un niveau complété ou une partie perdue sont des faits rendus par
        l'environnement : les faire dépendre de ce que le modèle en dit rendrait le
        score manipulable par le texte.
        """
        if issue.evenement in (Evenement.NIVEAU_COMPLETE, Evenement.GAME_OVER):
            if issue.evenement is Evenement.NIVEAU_COMPLETE:
                self.bilan.niveaux_completes += 1
                self.bilan.actions_niveau = 0
            else:
                self.bilan.game_overs += 1
            return issue.evenement
        contenu = (getattr(evaluation, "content", "") or "").lower()
        if "contredit" in contenu or "contradiction" in contenu:
            return Evenement.CONTRADICTION
        return Evenement.PREDICTION_CONFIRMEE
