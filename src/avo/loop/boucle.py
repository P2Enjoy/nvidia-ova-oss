"""Boucle agent : un tour = Planning → Implementation → Evaluation → [Bug-Fixing].

@spec docs/BACKLOG.md U13 — Boucle agent P→I→E→B
@spec docs/SPEC_HARNAIS.md §H8.1 (états), §H8.2 (un tour), §H8.3 (bornes),
      §H8.4 (continuation, supervision, métriques, lignée branchées sur la boucle),
      §H7.1 (outils exposés selon l'état), §H5.1 (historique append-only),
      §H5.3 et §H5.4 (continuation préventive et réactive), §H9.2 (lignée),
      §H10.3 (intervention du superviseur), §H11.2 (métriques),
      §H12 (politique de raisonnement portée par la configuration)
@spec docs/SPEC_ARCAGI3.md §A5.1 (direct-interaction : aucune règle de jeu fournie)
@spec docs/BACKLOG.md U27 — mode `state` de la boucle (§H15.7, §H15.8)
@spec docs/BACKLOG.md U31 — archive des pas du mode `state` (§H15.10), schéma de Σ du
      contexte monté (§H15.9), refus de garde = pas blanc atomique (§H16.1)
@spec docs/BACKLOG.md U30 — gardes de méthode dans les phases (§H16.1 garde
      documentaire, §H16.2 garde de prédiction, §H16.3 garde d'évaluation,
      §H16.4 garde de persistance, §H16.5 observabilité)

La boucle ne connaît aucun jeu. Elle parle à un `Environnement` par un contrat
minimal, ce qui permet de l'éprouver sur un environnement factice en mémoire avant
que l'interface ARC n'existe (U19), et garantit qu'aucune connaissance de jeu ne peut
s'y glisser.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Protocol

from avo.config import Config, ModeContexte
from avo.context.contexte import INVITATION_CONTINUATION, Contexte
from avo.context.etat import (
    CompteurRetries,
    EtatInvalide,
    PatchMalforme,
    RetriesEpuises,
    decoder_pas,
)
from avo.context.etat import Etat as EtatStructure
from avo.context.etat import appliquer as appliquer_pas
from avo.lineage import Lignee
from avo.llm.client import ChatResult, ContextOverflow, LLMClient, ToolCall
from avo.loop import prompts
from avo.loop.etats import Evenement, Phase, suivant
from avo.memory.notes import GUIDE, WORKING, Notes
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

#: Ligne de prédiction du mode `state` (§H16.2) : extraite avant que le reste du
#: raisonnement ne soit jeté (§H15.1).
_LIGNE_PREDICTION: Final = re.compile(
    r"^\s*PR[ÉE]DICTION\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE
)

#: Jeton de verdict (§H16.3), tolérant à la casse et aux accents, lu OÙ QU'IL
#: SOIT dans la réponse — en tête de ligne comme en milieu de phrase : refuser
#: un verdict présent mais mal placé mesure la ponctuation, pas la
#: qualification (mesure du 2026-09-02, série h25 bruit 20).
_JETON_VERDICT: Final = re.compile(
    r"VERDICT\s*:\s*(confirm\S*|contred\S*|infirm\S*|cadu[cq]\S*|non[ _-]?applicable|n/a)",
    re.IGNORECASE,
)


def _canonique_verdict(jeton: str) -> str:
    """Rapporte un jeton de verdict à son issue canonique (§H16.3)."""
    bas = jeton.lower()
    if bas.startswith("confirm"):
        return "confirmee"
    if bas.startswith(("contred", "infirm")):
        return "contredite"
    return "caduque"


def _verdict_dans(texte: str) -> str | None:
    """Rend « confirmee », « contredite » ou « caduque », ou `None` (§H16.3).

    Toutes les occurrences sont lues ; des familles CONTRADICTOIRES (une réponse
    qui recopie la forme annoncée entière, par exemple) rendent la qualification
    ambiguë : aucune n'est retenue et la garde redemande.
    """
    issues = {_canonique_verdict(jeton) for jeton in _JETON_VERDICT.findall(texte)}
    if len(issues) != 1:
        return None
    return issues.pop()


def _prediction_dans(texte: str) -> str | None:
    """Extrait la ligne `PREDICTION:` d'un pas du mode `state` (§H16.2)."""
    correspondance = _LIGNE_PREDICTION.search(texte)
    if correspondance is None:
        return None
    prediction = correspondance.group(1).strip()
    return prediction or None


class Issue(Protocol):
    """Ce qu'une action d'environnement rend en retour.

    Une issue PEUT en outre déclarer `refusee` (bool, faux par défaut, §H15.8) :
    vrai quand l'environnement a refusé l'action — elle n'a rien exécuté. La
    boucle la lit par `getattr`, si bien qu'un environnement qui ne la déclare
    pas se comporte comme avant.
    """

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

    def etat_terminal(self) -> str | None:
        """Motif d'arrêt si plus aucune action ne peut faire progresser la tâche (§H8.3).

        C'est l'environnement qui tranche, jamais le texte du modèle : dès qu'un
        motif est rendu, la boucle clôt sans nouvel appel au modèle.
        """
        ...


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
    #: Mode `state` seulement (§H15.8) : tentatives de patch refusées pour ce tour.
    retries_patch: int = 0


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
    #: Mode `state` seulement (§H15.8) : tentatives de patch refusées et somme des
    #: tailles de prompt (caractères) des appels, pour la moyenne du rapport A/B.
    retries_patch: int = 0
    taille_prompt_totale: int = 0
    #: Redemandes de garde totales du run (§H16.5).
    redemandes_gardes: int = 0

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
            "retries_patch": self.retries_patch,
            "taille_prompt_totale": self.taille_prompt_totale,
            "redemandes_gardes": self.redemandes_gardes,
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
        #: Σ du mode `state` (§H15.8) : `None` en mode `transcript`, où il est mort.
        self.etat: EtatStructure | None = None
        if config.contexte_mode is ModeContexte.ETAT:
            schema = self.contexte.schema_etat
            recharge = workspace.lire_etat(schema) if workspace is not None else None
            self.etat = recharge if recharge is not None else EtatStructure.initial(schema)
        #: Erreur de résolution d'action du tour précédent, à faire lire au modèle
        #: au tour suivant faute d'historique où l'inscrire (§H15.8).
        self._erreur_action_precedente: str | None = None
        #: Rappel du patch annulé au pas précédent pour refus d'environnement
        #: (§H15.8) : le prompt étant recomposé à neuf, la correction de Σ que ce
        #: patch portait disparaîtrait en silence sans ce rappel au pas suivant.
        self._rappel_patch_annule: str | None = None
        #: Prédiction de la dernière action jouée (§H16.2), conservée jusqu'à sa
        #: qualification par la garde d'évaluation (§H16.3).
        self._prediction_courante: str | None = None
        #: Garde de persistance (§H16.4) : compteur d'écritures de GUIDE relevé à
        #: l'armement, `None` quand la garde est désarmée.
        self._persistance_snapshot: int | None = None
        #: Mode `state` (§H16.3) : verdicts manquants consécutifs pour la même
        #: prédiction, avant l'issue prudente.
        self._echecs_verdict = 0

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
        # Une intervention arme la garde de persistance (§H16.4) : le diagnostic
        # reçu mérite d'être retenu avant de poursuivre.
        self._armer_persistance()

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

    # --------------------------------------------------------------------- gardes
    def _documentaire_manque(self) -> bool:
        """Garde documentaire (§H16.1) : `WORKING.md` vide verrouille l'action.

        La garde se réarme d'elle-même chaque fois que la note redevient vide —
        c'est ce qui la fait mordre à nouveau quand l'interface de tâche vide le
        brouillon à un changement de niveau.
        """
        return not self.notes.lire(WORKING).strip()

    def _persistance_manque(self) -> bool:
        """Garde de persistance (§H16.4) : armée tant que `GUIDE.md` n'est pas réécrit.

        Le constat est un compteur d'écritures, jamais une différence de contenu :
        une réécriture à l'identique est une confirmation explicite et satisfait la
        garde. La satisfaction désarme.
        """
        if self._persistance_snapshot is None:
            return False
        if self.notes.ecritures(GUIDE) > self._persistance_snapshot:
            self._persistance_snapshot = None
            return False
        return True

    def _armer_persistance(self) -> None:
        """Arme la garde (§H16.4) sur complétion, game over ou intervention."""
        if self.config.gardes and self._persistance_snapshot is None:
            self._persistance_snapshot = self.notes.ecritures(GUIDE)

    def _gardes_manquantes(self) -> list[tuple[str, str]]:
        manques: list[tuple[str, str]] = []
        if self._documentaire_manque():
            manques.append(("documentaire", prompts.GARDE_DOCUMENTAIRE))
        if self._persistance_manque():
            manques.append(("persistance", prompts.GARDE_PERSISTANCE))
        return manques

    def _gate_avant_action(self, tour: Tour) -> bool:
        """Verrou des outils d'action (§H16.1, §H16.4). `True` = agir est permis.

        Chaque redemande est un échange de Planning (outils de notes exposés), au
        plus `AVO_GARDE_RETRIES` par tour ; le budget épuisé clôt le tour sans
        action — compté, jamais fatal (§H16.0.2).
        """
        if not self.config.gardes:
            return True
        manques = self._gardes_manquantes()
        redemande = False
        for _ in range(self.config.garde_retries):
            if not manques:
                break
            for nom, _texte in manques:
                self.bilan.redemandes_gardes += 1
                self._metrique("garde", garde=nom, issue="redemandee")
            redemande = True
            reponse = self._interroger(
                Phase.PLANNING, "\n\n".join(texte for _nom, texte in manques)
            )
            self._executer_outils(reponse, tour)
            manques = self._gardes_manquantes()
        if not manques:
            if redemande:
                self._metrique("garde", issue="satisfaite_apres_redemande")
            return True
        for nom, _texte in manques:
            self._metrique("garde", garde=nom, issue="tour_clos")
        return False

    def _exiger_verdict(self, evaluation: Any, tour: Tour) -> str | None:
        """Garde d'évaluation (§H16.3) : qualification exigée, issue prudente sinon.

        `None` quand la garde ne s'applique pas (gardes inactives, ou aucune
        prédiction à qualifier). Budget de redemandes épuisé → la prédiction est
        réputée CONTREDITE : une prédiction non qualifiée n'est pas confirmée.
        """
        if not (self.config.gardes and self._prediction_courante):
            return None
        verdict = _verdict_dans(getattr(evaluation, "content", "") or "")
        tentatives = 0
        while verdict is None and tentatives < self.config.garde_retries:
            self.bilan.redemandes_gardes += 1
            self._metrique("garde", garde="evaluation", issue="redemandee")
            reponse = self._interroger(Phase.EVALUATION, prompts.GARDE_VERDICT_REDEMANDE)
            self._executer_outils(reponse, tour)
            verdict = _verdict_dans(reponse.content or "")
            tentatives += 1
        if verdict is None:
            self._metrique("garde", garde="evaluation", issue="forcee")
            verdict = "contredite"
        elif verdict == "caduque":
            # §H16.3 : ni validée ni démentie — tracée à part (§H16.5).
            self._metrique("garde", garde="evaluation", issue="caduque")
        self._prediction_courante = None
        return verdict

    # ---------------------------------------------------------------------- tour
    def jouer_tour(self, numero: int) -> Tour:
        """Déroule un tour complet (§H8.2), ou un pas du mode `state` (§H15.8)."""
        if self.etat is not None:
            return self._jouer_tour_etat(numero)
        return self._jouer_tour_transcript(numero)

    def _jouer_tour_transcript(self, numero: int) -> Tour:
        """Un tour du mode `transcript` : P → I → E, puis B si nécessaire (§H8.2)."""
        tour = Tour(numero=numero, phase_finale=self.phase)

        # --- Planning : hypothèses, choix, prédiction énoncée. Les demandes de
        # garde (§H16.1, §H16.4) précèdent l'invite : l'artefact d'abord, l'action
        # ensuite.
        invite = prompts.PLANNING
        if self.config.gardes and self._documentaire_manque():
            notes_bloc = self.notes.pour_segment_frais()
            invite = f"{prompts.GARDE_DOCUMENTAIRE}\n\n{notes_bloc}\n\n{invite}"
        if self.config.gardes and self._persistance_manque():
            invite = f"{prompts.GARDE_PERSISTANCE}\n\n{invite}"
        if self._borne_proche():
            invite = f"{prompts.BORNE_PROCHE}\n\n{invite}"
        planning = self._interroger(Phase.PLANNING, self._avec_observation(invite))
        self._executer_outils(planning, tour)

        # --- Verrou des gardes (§H16.1, §H16.4) : les outils d'action ne se
        # déverrouillent pas tant que les artefacts exigés manquent.
        if not self._gate_avant_action(tour):
            tour.phase_finale = self.phase
            _journal.info("tour clos par une garde", extra={"tour": numero})
            return tour
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

        # Garde de prédiction (§H16.2) : la prédiction voyage dans l'appel d'outil
        # lui-même — son absence est déjà une erreur d'outil rendue au modèle quand
        # le schéma la requiert, et l'action n'est alors pas jouée.
        if self.config.gardes:
            prediction = appel.arguments.get("prediction")
            if isinstance(prediction, str) and prediction.strip():
                self._prediction_courante = prediction.strip()

        issue = self._jouer_action(appel, tour)
        if issue is None:
            self.phase = Phase.PLANNING
            tour.phase_finale = self.phase
            _journal.info("action sans issue rendue par l'environnement", extra={"tour": numero})
            return tour
        tour.action = appel.nom
        self.phase = suivant(self.phase, Evenement.ACTION_JOUEE)

        # Garde de persistance (§H16.4) : l'événement rendu par l'environnement
        # arme la garde AVANT l'évaluation, dont l'invite porte la demande — les
        # outils de notes y sont exposés, l'agent peut satisfaire immédiatement.
        if issue.evenement in (Evenement.NIVEAU_COMPLETE, Evenement.GAME_OVER):
            self._armer_persistance()

        # --- Evaluation : confronter, énoncer, mettre à jour. Sous garde (§H16.3),
        # l'invite cite la prédiction conservée et exige la qualification.
        invite_evaluation = (
            prompts.evaluation_gardee(self._prediction_courante)
            if self.config.gardes and self._prediction_courante
            else prompts.EVALUATION
        )
        if self.config.gardes and self._persistance_manque():
            invite_evaluation = f"{invite_evaluation}\n\n{prompts.GARDE_PERSISTANCE}"
        evaluation = self._interroger(
            Phase.EVALUATION, f"{invite_evaluation}\n\n{issue.observation}"
        )
        self._executer_outils(evaluation, tour)
        verdict = self._exiger_verdict(evaluation, tour)
        evenement = self._evenement_apres_evaluation(issue, evaluation, verdict)
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

    # --------------------------------------------------------------- mode state
    def _archiver_pas(self, tour: int, tentative: int, contenu: str | None, **issue: Any) -> None:
        """Archive un appel du mode `state` dans le workspace (§H15.10).

        Jamais relue par la boucle ni réinjectée dans un prompt : la réponse brute
        (`contenu`) et son issue — patch/action, erreur de patch, ou refus d'une
        garde (ligne sans contenu, l'appel étant déjà archivé) — servent au
        dépouillement seul. Sans workspace, rien n'est écrit.
        """
        if self.workspace is None:
            return
        ligne: dict[str, Any] = {"tour": tour, "tentative": tentative}
        if contenu is not None:
            ligne["contenu"] = contenu
        ligne.update(issue)
        self.workspace.ecrire_pas(ligne)

    def _messages_etat(
        self, erreur_precedente: str | None, rappel_annulation: str | None = None
    ) -> list[dict[str, str]]:
        """Compose le prompt d'un pas : (P, Σₜ, Oₜ) + notes, O(1) par tour (§H15.1).

        Sous gardes (§H16.2, §H16.3), le protocole exige la ligne `PREDICTION:` et,
        quand une prédiction antérieure attend sa qualification, la ligne
        `VERDICT:` — le bloc JSON à deux clés de §H15.1 reste inchangé.
        """
        assert self.etat is not None
        protocole = prompts.protocole_etat(self.contexte.schema_etat)
        if self.config.gardes:
            protocole = f"{protocole}\n\n{prompts.PROTOCOLE_ETAT_GARDES}"
            if self._prediction_courante:
                protocole = (
                    f"{prompts.verdict_a_qualifier(self._prediction_courante)}\n\n{protocole}"
                )
        contenu = (
            f"État courant (Σ) :\n{self.etat.vers_json()}\n\n"
            f"{self.notes.pour_segment_frais()}\n\n"
            f"{self._avec_observation(protocole)}"
        )
        # §H16.0.7 : tant que le champ de connaissances est vide — la condition
        # exacte de la garde documentaire (§H16.1) —, le message du pas s'ouvre
        # sur le rappel de l'exigence : la phrase finale du protocole, dans le
        # message système, perd contre une observation volumineuse. L'erreur
        # nommée d'un pas refusé garde la primauté (§H16.0.6) : l'amorce se pose
        # avant elle et reste donc en dessous.
        if self.config.gardes and not self.etat.champs.get("hypotheses"):
            contenu = f"{prompts.AMORCE_DOCUMENTAIRE}\n\n{contenu}"
        if erreur_precedente is not None:
            contenu = (
                f"Ta réponse précédente était invalide : {erreur_precedente}\n"
                f"Corrige et réponds à nouveau selon le protocole ci-dessous.\n\n{contenu}"
            )
        # §H15.8 : le patch annulé au pas précédent est rappelé verbatim — sans ce
        # rappel, la correction de Σ qu'il portait au-delà de l'effet de l'action
        # refusée serait perdue en silence, le prompt étant recomposé à neuf.
        if rappel_annulation is not None:
            contenu = f"{rappel_annulation}\n\n{contenu}"
        # §H15.8 : le message système est celui du contexte monté par l'appelant
        # (défaut `prompts.SYSTEME`) — même surface qu'en mode `transcript`, et la
        # seule par laquelle un adaptateur fournit son contexte de tâche (§H16.1).
        return [
            {"role": "system", "content": self.contexte.systeme},
            {"role": "user", "content": contenu},
        ]

    def _appeler_etat(self, messages: list[dict[str, str]]) -> ChatResult:
        """Un appel au modèle en mode `state`, sans outils (§H15.1, §H15.8)."""
        resultat = self.client.chat(messages, tools=None)
        self.bilan.tokens_prompt += resultat.prompt_eval_count
        self.bilan.tokens_generes += resultat.eval_count
        taille = sum(len(message["content"]) for message in messages)
        self.bilan.taille_prompt_totale += taille
        self._metrique(
            "llm",
            phase="state",
            tokens_prompt=resultat.prompt_eval_count,
            tokens_generes=resultat.eval_count,
            duree_ms=resultat.total_duration_ms,
            tronquee=resultat.tronquee,
            taille_prompt=taille,
        )
        return resultat

    def _resoudre_action(self, action_texte: str) -> ToolCall:
        """Traduit le champ `action` du pas en appel d'outil générique (§H15.8).

        Le nom de l'action et le nombre de ses paramètres viennent du schéma de
        l'outil déjà déclaré par l'environnement — jamais d'une liste ou d'un
        décompte codés en dur (interdiction de benchmaxing, CLAUDE_PROJECT.md). Une
        résolution qui échoue rend un `ToolCall` en erreur, diagnosticable par le
        registre comme n'importe quel outil (§H7.4), jamais fatale.
        """
        texte = action_texte.strip()
        # §H15.8 : la syntaxe d'appel de fonction — « nom(v1, v2) », « nom() » —
        # est un bruit de format des modèles open-weight (mesuré : relevé live du
        # banc, 2026-09-01) ; elle se lit comme « nom v1,v2 », purement
        # syntaxique, valable pour tout environnement.
        appel_fonction = re.fullmatch(r"([^\s(]+)\s*\((.*)\)\s*", texte, re.DOTALL)
        if appel_fonction is not None:
            nom, reste = appel_fonction.group(1), appel_fonction.group(2)
        else:
            nom, _, reste = texte.partition(" ")
        # §H15.8 : la ponctuation traînante du jeton de nom est un bruit de format
        # des modèles open-weight (mesuré : « action1, », run ab-u28-state) — elle
        # est retirée avant la recherche, sans toucher aux valeurs ni au sens.
        nom = nom.strip().lower().rstrip(",;:.")
        schemas = {
            schema["function"]["name"]: schema["function"]
            for schema in self.registre.schemas(("action",))
        }
        schema = schemas.get(nom)
        if schema is None:
            # §H15.8 : le refus se clôt par les formes disponibles, valeurs
            # requises comprises — jamais les seuls noms (principe §H16.0.6
            # étendu à la résolution).
            disponibles = (
                ", ".join(
                    prompts.annonce_action(
                        candidat,
                        list(schemas[candidat].get("parameters", {}).get("required", [])),
                    )
                    for candidat in sorted(schemas)
                )
                or "(aucune)"
            )
            return ToolCall(
                nom=nom,
                erreur_arguments=(
                    f"outil_inconnu: « {nom} » n'existe pas. Disponibles : {disponibles}."
                ),
            )
        parametres = schema.get("parameters", {})
        requis: list[str] = list(parametres.get("required", []))
        proprietes: dict[str, Any] = dict(parametres.get("properties", {}))
        if len(requis) == 1 and reste.strip():
            # §H15.8 : un seul paramètre requis reçoit le reste VERBATIM — un
            # paramètre de texte libre (ligne de commande, phrase) contient
            # légitimement virgules et espaces, tout découpage le mutilerait.
            valeurs = [reste.strip()]
        else:
            valeurs = (
                [valeur.strip() for valeur in reste.split(",") if valeur.strip()]
                if reste.strip()
                else []
            )
        if len(valeurs) != len(requis):
            # §H15.8 : quand les virgules ne rendent pas le compte de paramètres
            # requis mais que les espaces le rendent (« store a b », mesuré sur le
            # relevé live du banc), le découpage par espaces fait foi.
            par_espaces = reste.split()
            if len(par_espaces) == len(requis):
                valeurs = par_espaces
        if len(valeurs) != len(requis):
            # §H15.8 : le refus se clôt par la forme complète attendue de l'outil
            # fautif (principe §H16.0.6 étendu à la résolution) — le manque reste
            # nommé en tête.
            types = {cle: str(proprietes.get(cle, {}).get("type") or "") for cle in requis}
            return ToolCall(
                nom=nom,
                erreur_arguments=(
                    f"{len(requis)} valeur(s) attendue(s) ({', '.join(requis) or 'aucune'}), "
                    f"{len(valeurs)} reçue(s). "
                    f"{prompts.forme_appel_attendue(nom, requis, types)}"
                ),
            )
        arguments: dict[str, Any] = {}
        for cle, brut in zip(requis, valeurs, strict=True):
            # §H15.8 : la syntaxe d'argument nommé — « cle=valeur » où « cle »
            # est exactement le paramètre requis que la position destine — est un
            # bruit de format des modèles open-weight (mesuré : banc dépôt h25
            # bruit 5, 2026-09-02). Toute autre égalité reste une valeur.
            prefixe = f"{cle}="
            if brut.startswith(prefixe):
                brut = brut[len(prefixe) :].strip()
            type_attendu = proprietes.get(cle, {}).get("type")
            try:
                if type_attendu == "integer":
                    arguments[cle] = int(brut)
                elif type_attendu == "number":
                    arguments[cle] = float(brut)
                else:
                    arguments[cle] = brut
            except ValueError:
                # §H15.8 : même clôture par la forme attendue que le refus de
                # compte — le type fautif reste nommé en tête.
                types = {
                    autre: str(proprietes.get(autre, {}).get("type") or "") for autre in requis
                }
                return ToolCall(
                    nom=nom,
                    erreur_arguments=(
                        f"« {cle} » : {type_attendu} attendu, reçu {brut!r}. "
                        f"{prompts.forme_appel_attendue(nom, requis, types)}"
                    ),
                )
        return ToolCall(nom=nom, arguments=arguments)

    def _avec_prediction_injectee(self, appel: ToolCall, prediction: str) -> ToolCall:
        """Injecte la prédiction dans l'appel si le schéma la déclare (§H16.2).

        En mode `state`, la prédiction voyage en ligne de texte, pas en paramètre
        (§H15.8) : c'est la boucle qui la reporte dans l'appel — uniquement quand
        l'outil déclare la propriété, pour rester valable sur tout environnement.
        """
        schemas = {
            schema["function"]["name"]: schema["function"]
            for schema in self.registre.schemas(("action",))
        }
        schema = schemas.get(appel.nom)
        if schema is None:
            return appel
        proprietes = schema.get("parameters", {}).get("properties", {})
        if "prediction" not in proprietes:
            return appel
        return ToolCall(nom=appel.nom, arguments={**appel.arguments, "prediction": prediction})

    def _gardes_etat(self, contenu: str) -> tuple[str | None, str | None, str | None]:
        """Gardes du mode `state` (§H16.1–§H16.3) sur le texte d'un pas.

        Rend `(refus, verdict, prediction)`. `refus` non nul = l'action du pas est
        retenue (gratuite) et le message revient au pas suivant par le mécanisme
        d'erreur de §H15.8. Le verdict manquant au-delà du budget par prédiction
        reçoit l'issue prudente de §H16.3 (réputé contredit).
        """
        assert self.etat is not None
        manques: list[str] = []
        verdict = _verdict_dans(contenu)
        verdict_force = False
        if self._prediction_courante and verdict is None:
            if self._echecs_verdict >= self.config.garde_retries:
                verdict = "contredite"
                verdict_force = True
            else:
                self._echecs_verdict += 1
                self.bilan.redemandes_gardes += 1
                self._metrique("garde", garde="evaluation", issue="redemandee")
                manques.append(
                    "ligne « VERDICT: confirmee » ou « VERDICT: contredite » manquante "
                    "(une prédiction attend sa qualification)"
                )
        if not self.etat.champs.get("hypotheses"):
            self.bilan.redemandes_gardes += 1
            self._metrique("garde", garde="documentaire", issue="redemandee")
            manques.append(
                "champ « hypotheses » de Σ vide : écris au moins une hypothèse via state_patch "
                "avant d'agir"
            )
        prediction = _prediction_dans(contenu)
        if prediction is None:
            self.bilan.redemandes_gardes += 1
            self._metrique("garde", garde="prediction", issue="redemandee")
            manques.append("ligne « PREDICTION: … » manquante avant le bloc JSON")
        if manques:
            # §H16.0.6 : le refus se clôt TOUJOURS par la forme complète de la
            # réponse attendue — une redemande qui ne nomme que la pièce
            # manquante fait perdre l'autre (ping-pong mesuré, suite 24). Le pas
            # refusé se ré-émet en entier : le verdict reste dû tant qu'une
            # prédiction attend sa qualification, même s'il figurait déjà dans
            # la réponse refusée.
            forme = prompts.forme_pas_attendue(bool(self._prediction_courante))
            return f"{' ; '.join(manques)}. {forme}", None, None
        if verdict_force:
            self._metrique("garde", garde="evaluation", issue="forcee")
        if verdict == "caduque":
            # §H16.3 : une prédiction rendue sans objet par un événement
            # postérieur n'est ni validée ni démentie — tracée à part (§H16.5).
            self._metrique("garde", garde="evaluation", issue="caduque")
        self._echecs_verdict = 0
        return None, verdict, prediction

    def _jouer_tour_etat(self, numero: int) -> Tour:
        """Un pas du mode `state` : un seul appel LLM, Σ mis à jour, action jouée (§H15.8)."""
        assert self.etat is not None
        tour = Tour(numero=numero, phase_finale=Phase.IMPLEMENTATION)
        compteur = CompteurRetries()
        erreur_precedente = self._erreur_action_precedente
        self._erreur_action_precedente = None
        rappel_annulation = self._rappel_patch_annule
        self._rappel_patch_annule = None
        try:
            while True:
                resultat = self._appeler_etat(
                    self._messages_etat(erreur_precedente, rappel_annulation)
                )
                try:
                    nouvel_etat, action_texte = appliquer_pas(self.etat, resultat.content)
                    patch = dict(decoder_pas(resultat.content).patch)
                    # §H16.1 : un vidage d'« hypotheses » resté sans effet est un
                    # écart nommé, jamais silencieux — il s'archive (§H15.10).
                    conservation: dict[str, Any] = (
                        {"hypotheses_conservees": True}
                        if "hypotheses" in patch
                        and not patch["hypotheses"]
                        and self.etat.champs.get("hypotheses")
                        else {}
                    )
                    self._archiver_pas(
                        numero,
                        compteur.consommees,
                        resultat.content,
                        patch=patch,
                        action=action_texte,
                        **conservation,
                    )
                    break
                except (PatchMalforme, EtatInvalide) as erreur:
                    self._archiver_pas(
                        numero, compteur.consommees, resultat.content, erreur=str(erreur)
                    )
                    if compteur.epuise:
                        raise RetriesEpuises(
                            f"tour {numero} : budget de tentatives de patch épuisé "
                            f"({compteur.plafond}) sans état valide : {erreur}"
                        ) from erreur
                    compteur = compteur.echec()
                    erreur_precedente = str(erreur)
                    tour.retries_patch += 1
                    self.bilan.retries_patch += 1
                    self._metrique("retry_patch", tentative=compteur.consommees, erreur=str(erreur))
        except ContextOverflow as erreur:
            self.bilan.depassements += 1
            self._metrique("depassement", phase="state", plafond=erreur.max_context_tokens)
            raise

        etat_avant = self.etat
        self.etat = nouvel_etat

        # Gardes du mode `state` (§H16.1–§H16.3) : un refus est un pas blanc
        # ATOMIQUE — le patch est annulé avec l'action (Σ revient à sa valeur
        # d'avant le pas, le workspace ne voit jamais l'état intermédiaire), car
        # patch et action forment un seul pas et le patch porte souvent l'effet
        # attendu d'une action qui n'a pas été jouée. Le pas suivant ré-émet tout
        # depuis le même (Σ, O) ; le patch annulé reste lisible dans l'archive
        # des pas (§H15.10).
        verdict: str | None = None
        prediction: str | None = None
        if self.config.gardes:
            refus, verdict, prediction = self._gardes_etat(resultat.content or "")
            if refus is not None:
                self.etat = etat_avant
                self._erreur_action_precedente = refus
                self._archiver_pas(numero, compteur.consommees, None, refus=refus)
                tour.phase_finale = Phase.PLANNING
                return tour

        if self.workspace is not None:
            self.workspace.ecrire_etat(self.etat)

        appel = self._resoudre_action(action_texte)
        actions_valides = {
            schema["function"]["name"] for schema in self.registre.schemas(("action",))
        }
        if not appel.valide or appel.nom not in actions_valides:
            self._erreur_action_precedente = (
                appel.erreur_arguments or f"« {appel.nom} » n'est pas une action disponible"
            )
            self._metrique("action_invalide", nom=appel.nom, erreur=self._erreur_action_precedente)
            tour.phase_finale = Phase.PLANNING
            return tour

        if prediction is not None:
            appel = self._avec_prediction_injectee(appel, prediction)
        issue = self._jouer_action(appel, tour)
        if issue is None:
            tour.phase_finale = Phase.PLANNING
            return tour
        # §H15.8 : une action REFUSÉE par l'environnement n'a rien exécuté — le
        # patch du même pas, qui écrit son effet attendu (exemple B.3), est
        # annulé avec elle : Σ et le workspace reviennent à l'état d'avant le
        # pas, l'archive garde le patch annulé, et le pas suivant lit le refus
        # dans l'issue rappelée de l'observation. L'événement consommé et le
        # score restent l'affaire de l'environnement. Un environnement qui ne
        # déclare pas `refusee` se comporte comme avant (défaut faux).
        if getattr(issue, "refusee", False):
            self.etat = etat_avant
            if self.workspace is not None:
                self.workspace.ecrire_etat(self.etat)
            self._archiver_pas(numero, compteur.consommees, None, patch=patch, patch_annule=True)
            self._metrique("patch_annule", action=appel.nom)
            # §H15.8 : le pas suivant reçoit le patch annulé verbatim — c'est le
            # modèle qui décide de ce qui y survit, jamais le harnais. Un patch
            # vide n'a rien à rappeler.
            if patch:
                self._rappel_patch_annule = prompts.rappel_patch_annule(
                    appel.nom, json.dumps(patch, ensure_ascii=False, sort_keys=True)
                )
        tour.action = appel.nom
        # La prédiction accompagne l'action jouée (§H16.2) et attend sa
        # qualification au pas suivant (§H16.3).
        if self.config.gardes:
            self._prediction_courante = prediction
        evenement = self._evenement_apres_evaluation(issue, resultat, verdict)
        tour.evenement = evenement
        if evenement is Evenement.NIVEAU_COMPLETE:
            self._proposer_a_la_lignee()
        self._superviser(tour, issue.observation)
        return tour

    def executer(
        self, tours_max: int, arret_anticipe: Callable[[], str | None] | None = None
    ) -> Bilan:
        """Enchaîne les tours jusqu'à un arrêt ou l'épuisement du quota (§H8.3).

        Trois causes d'arrêt, dans l'ordre de priorité de §H8.3 : l'état terminal de
        la tâche (l'environnement tranche, la boucle ne rappelle plus le modèle),
        les bornes d'actions, puis `arret_anticipe` — consulté **entre deux tours** :
        c'est ainsi que la campagne fait respecter ses budgets de temps et de tokens
        sans jamais interrompre une opération en vol (§A7.4).
        """
        for numero in range(1, tours_max + 1):
            motif = self.environnement.etat_terminal()
            if motif is None:
                motif = self._borne_franchie()
            if motif is None and arret_anticipe is not None:
                motif = arret_anticipe()
            if motif is not None:
                return self._clore(motif, numero)
            self.bilan.tours.append(self.jouer_tour(numero))
        # Une tâche accomplie au dernier tour se clôt sur son motif terminal,
        # jamais sur « tours_epuises » (§H8.3).
        return self._clore(self.environnement.etat_terminal() or "tours_epuises", tours_max)

    def _clore(self, motif: str, tour: int) -> Bilan:
        """Arrête proprement : le motif est nommé, le dernier segment archivé."""
        self.bilan.arret = motif
        _journal.info("fin d'exécution", extra={"motif": motif, "tour": tour})
        self._metrique("arret", motif=motif, tour=tour, **self.bilan.resume())
        self._archiver(self.contexte.transcript)
        return self.bilan

    # ----------------------------------------------------------------- internes
    def _avec_observation(self, invite: str) -> str:
        # §H15.8 : chaque action disponible s'annonce avec ses valeurs requises,
        # lues dans son schéma au registre — la forme d'appel ne doit jamais
        # s'apprendre en la violant (mesuré : 161 actions invalides sur 646,
        # campagne U25 tranche 1). Un nom sans schéma reste nu.
        schemas = {
            schema["function"]["name"]: schema["function"]
            for schema in self.registre.schemas(("action",))
        }
        annonces = ", ".join(
            prompts.annonce_action(
                nom,
                (
                    list(schemas[nom].get("parameters", {}).get("required", []))
                    if nom in schemas
                    else None
                ),
            )
            for nom in self.environnement.actions_disponibles()
        )
        etat = (
            f"Observation :\n{self.environnement.observation()}\n\nActions disponibles : {annonces}"
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
        issue_avant = self.environnement.derniere_issue()
        observation_avant = self.environnement.observation()
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
        if issue is None or issue is issue_avant:
            # L'issue n'a pas changé : l'outil a refusé l'appel (arguments
            # invalides, prédiction absente §H16.2, commande indisponible §A5.2)
            # et l'erreur est déjà rendue au modèle (§H7.4). Compter une action ou
            # évaluer l'issue PRÉCÉDENTE fausserait le score et l'évidence.
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
        # §H11.2 : mesure du non-progrès, et uniquement la mesure — une action
        # valide dont l'observation rendue est STRICTEMENT identique à celle
        # d'avant l'action s'émet en métrique ; aucun seuil, aucune
        # interprétation, aucun effet sur le comportement. Une action refusée
        # par l'environnement (§H15.8) laisse l'observation inchangée par
        # nature : elle est exclue, son refus porte déjà sa métrique.
        if not getattr(issue, "refusee", False) and (
            self.environnement.observation() == observation_avant
        ):
            self._metrique("observation_inchangee", action=appel.nom, tour=tour.numero)
        return issue

    def _evenement_apres_evaluation(
        self, issue: Issue, evaluation: Any, verdict: str | None = None
    ) -> Evenement:
        """L'environnement prime ; le modèle ne tranche que la contradiction.

        Un niveau complété ou une partie perdue sont des faits rendus par
        l'environnement : les faire dépendre de ce que le modèle en dit rendrait le
        score manipulable par le texte. Sous garde d'évaluation (§H16.3), le
        VERDICT exigé remplace l'heuristique de sous-chaîne — il est explicite là
        où elle devine.
        """
        if issue.evenement in (Evenement.NIVEAU_COMPLETE, Evenement.GAME_OVER):
            if issue.evenement is Evenement.NIVEAU_COMPLETE:
                self.bilan.niveaux_completes += 1
                self.bilan.actions_niveau = 0
            else:
                self.bilan.game_overs += 1
            return issue.evenement
        if verdict is not None:
            if verdict == "contredite":
                return Evenement.CONTRADICTION
            # « confirmee » comme « caduque » (§H16.3) poursuivent sans
            # Bug-Fixing : une prédiction sans objet n'est pas un bug du modèle
            # du monde ; la métrique `issue: "caduque"` la distingue (§H16.5).
            return Evenement.PREDICTION_CONFIRMEE
        contenu = (getattr(evaluation, "content", "") or "").lower()
        if "contredit" in contenu or "contradiction" in contenu:
            return Evenement.CONTRADICTION
        return Evenement.PREDICTION_CONFIRMEE
