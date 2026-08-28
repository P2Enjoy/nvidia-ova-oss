"""Runner de campagne ARC-AGI-3 : joue des jeux, mesure, et reprend où il s'est arrêté.

@spec docs/BACKLOG.md U23 — Runner de campagne et rapport
@spec docs/SPEC_ARCAGI3.md §A7.1 (runner, plafonds), §A7.2 (scorecard et garde
      d'accord), §A7.4 (contrat d'implémentation, reprise, lignée par jeu),
      §A6 (RHAE), §A5 (interface de tâche), §A2.2 (historique typé persisté)
@spec docs/SPEC_HARNAIS.md §H6.1 (workspace du run), §H8.3 (bornes d'actions),
      §H8.4 (branchements de la boucle), §H9.3 (lignée jetable), §H13.2 (reprise)

Le même chemin de code sert en rejeu et en live : seul l'hôte change. Une branche
live jamais éprouvée serait une branche fausse le jour où elle compte.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from avo.arc.client import ArcClient
from avo.arc.interface import InterfaceArc
from avo.arc.memoire import (
    SCHEMA_DIFF,
    SCHEMA_INSPECT,
    SCHEMA_READ_PIXELS,
    MemoireFrames,
    outil_diff,
    outil_inspect,
    outil_read_pixels,
)
from avo.arc.rhae import NiveauJoue, ResultatRhae, niveaux_joues, rhae_global, rhae_jeu
from avo.config import Config, Mode
from avo.lineage import Lignee, ScorerARC
from avo.llm.client import LLMClient
from avo.loop.boucle import Bilan, BoucleAgent
from avo.memory.notes import (
    SCHEMA_NOTE_READ,
    SCHEMA_NOTE_WRITE,
    Notes,
    note_read,
    note_write,
)
from avo.memory.workspace import Workspace
from avo.supervisor import Superviseur
from avo.tools.registre import RegistreOutils, outil_depuis_schema

_journal = logging.getLogger("avo.campagne")

#: Nom du fichier d'état de campagne, dans le workspace du run (§A7.4).
ETAT = "campagne.json"

#: Étiquettes posées sur le scorecard de la campagne (§A7.2).
ETIQUETTES = ("avo", "campagne")


class CampagneInvalide(RuntimeError):
    """Campagne impossible : la cause est nommée, jamais contournée."""


@dataclass(frozen=True)
class Plafonds:
    """Bornes d'une campagne (§A7.1). Obligatoires en live, facultatives en rejeu."""

    actions_niveau: int
    actions_jeu: int
    tours_max: int
    secondes_jeu: float | None = None
    tokens_jeu: int | None = None

    def en_json(self) -> dict[str, Any]:
        return {
            "actions_niveau": self.actions_niveau,
            "actions_jeu": self.actions_jeu,
            "tours_max": self.tours_max,
            "secondes_jeu": self.secondes_jeu,
            "tokens_jeu": self.tokens_jeu,
        }

    @classmethod
    def depuis_json(cls, donnees: dict[str, Any]) -> Plafonds:
        return cls(
            actions_niveau=int(donnees["actions_niveau"]),
            actions_jeu=int(donnees["actions_jeu"]),
            tours_max=int(donnees["tours_max"]),
            secondes_jeu=donnees.get("secondes_jeu"),
            tokens_jeu=donnees.get("tokens_jeu"),
        )


@dataclass(frozen=True)
class ResultatJeu:
    """Ce qu'un jeu a produit. Sérialisable : c'est l'unité de reprise (§A7.4)."""

    game_id: str
    guid: str
    niveaux: tuple[NiveauJoue, ...]
    rhae: ResultatRhae
    tours: int
    arret: str
    actions: int
    niveaux_completes: int
    game_overs: int
    tokens_prompt: int
    tokens_generes: int
    secondes: float
    continuations: int
    depassements: int
    interventions: int
    versions_committees: int

    @property
    def tokens(self) -> int:
        return self.tokens_prompt + self.tokens_generes

    def en_json(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "guid": self.guid,
            "niveaux": [
                {
                    "niveau": niveau.niveau,
                    "baseline": niveau.baseline,
                    "actions": niveau.actions,
                    "complete": niveau.complete,
                }
                for niveau in self.niveaux
            ],
            "rhae": self.rhae.valeur,
            "efficacite_ponderee": self.rhae.efficacite_ponderee,
            "plafond_completion": self.rhae.plafond_completion,
            "plafonne": self.rhae.plafonne,
            "tours": self.tours,
            "arret": self.arret,
            "actions": self.actions,
            "niveaux_completes": self.niveaux_completes,
            "game_overs": self.game_overs,
            "tokens_prompt": self.tokens_prompt,
            "tokens_generes": self.tokens_generes,
            "secondes": self.secondes,
            "continuations": self.continuations,
            "depassements": self.depassements,
            "interventions": self.interventions,
            "versions_committees": self.versions_committees,
        }

    @classmethod
    def depuis_json(cls, donnees: dict[str, Any]) -> ResultatJeu:
        niveaux = tuple(
            NiveauJoue(
                niveau=int(entree["niveau"]),
                baseline=int(entree["baseline"]),
                actions=int(entree["actions"]),
                complete=bool(entree["complete"]),
            )
            for entree in donnees["niveaux"]
        )
        return cls(
            game_id=str(donnees["game_id"]),
            guid=str(donnees["guid"]),
            niveaux=niveaux,
            rhae=rhae_jeu(niveaux),
            tours=int(donnees["tours"]),
            arret=str(donnees["arret"]),
            actions=int(donnees["actions"]),
            niveaux_completes=int(donnees["niveaux_completes"]),
            game_overs=int(donnees["game_overs"]),
            tokens_prompt=int(donnees["tokens_prompt"]),
            tokens_generes=int(donnees["tokens_generes"]),
            secondes=float(donnees["secondes"]),
            continuations=int(donnees["continuations"]),
            depassements=int(donnees["depassements"]),
            interventions=int(donnees["interventions"]),
            versions_committees=int(donnees["versions_committees"]),
        )


@dataclass
class EtatCampagne:
    """État persisté après CHAQUE jeu : une interruption ne coûte qu'un jeu (§A7.4)."""

    run_id: str
    mode: str
    plafonds: Plafonds
    jeux_demandes: list[str]
    #: L'accord de publication appartient à la CAMPAGNE, pas à l'invocation : il est
    #: donc persisté. Une reprise le relit au lieu de se l'accorder toute seule, et
    #: une reprise d'une campagne jamais autorisée reste refusée (§A7.2).
    autorise_publication: bool = False
    card_id: str | None = None
    resultats: list[ResultatJeu] = field(default_factory=list)

    @property
    def termines(self) -> set[str]:
        return {resultat.game_id for resultat in self.resultats}

    def restants(self) -> list[str]:
        return [jeu for jeu in self.jeux_demandes if jeu not in self.termines]

    def ecrire(self, workspace: Workspace) -> None:
        contenu = {
            "run_id": self.run_id,
            "mode": self.mode,
            "plafonds": self.plafonds.en_json(),
            "jeux_demandes": self.jeux_demandes,
            "autorise_publication": self.autorise_publication,
            "card_id": self.card_id,
            "resultats": [resultat.en_json() for resultat in self.resultats],
        }
        (workspace.chemin / ETAT).write_text(
            json.dumps(contenu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    @classmethod
    def lire(cls, workspace: Workspace) -> EtatCampagne:
        chemin = workspace.chemin / ETAT
        if not chemin.exists():
            raise CampagneInvalide(
                f"aucun état de campagne dans {workspace.chemin} : rien à reprendre "
                f"(le fichier {ETAT} est écrit après chaque jeu)"
            )
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
        return cls(
            run_id=str(donnees["run_id"]),
            mode=str(donnees["mode"]),
            plafonds=Plafonds.depuis_json(donnees["plafonds"]),
            jeux_demandes=list(donnees["jeux_demandes"]),
            autorise_publication=bool(donnees.get("autorise_publication", False)),
            card_id=donnees.get("card_id"),
            resultats=[ResultatJeu.depuis_json(entree) for entree in donnees["resultats"]],
        )


@dataclass(frozen=True)
class ResultatCampagne:
    """Ce qu'une campagne a produit, et de quoi écrire le rapport (§A7.3)."""

    run_id: str
    mode: str
    card_id: str | None
    plafonds: Plafonds
    jeux: tuple[ResultatJeu, ...]
    score_global: float

    def resume(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "mode": self.mode,
            "jeux": len(self.jeux),
            "score_global": self.score_global,
            "actions": sum(jeu.actions for jeu in self.jeux),
            "tokens": sum(jeu.tokens for jeu in self.jeux),
        }


def valider(config: Config, plafonds: Plafonds | None, autorise_publication: bool) -> None:
    """Refus de campagne, nommés (§A7.1, §A7.2).

    La garde d'accord est explicite parce que la conséquence l'est : jouer via l'API
    officielle enregistre un scorecard au nom du responsable.
    """
    if config.mode is not Mode.LIVE:
        return
    if not autorise_publication:
        raise CampagneInvalide(
            "mode live sans --j-autorise-la-publication : jouer via l'API officielle "
            "enregistre un scorecard au nom du responsable (docs/SPEC_ARCAGI3.md §A7.2). "
            "L'accord doit être donné explicitement, campagne par campagne."
        )
    if plafonds is None:
        raise CampagneInvalide("mode live sans plafonds")
    manquants = [
        nom
        for nom, valeur in (
            ("--budget-secondes-jeu", plafonds.secondes_jeu),
            ("--budget-tokens-jeu", plafonds.tokens_jeu),
        )
        if valeur is None
    ]
    if manquants:
        raise CampagneInvalide(
            f"mode live : plafonds obligatoires manquants ({', '.join(manquants)}). "
            "Une campagne live sans budget de temps ni de tokens peut dépenser sans "
            "fin (docs/SPEC_ARCAGI3.md §A7.1)."
        )


def registre_de_jeu(memoire: MemoireFrames, notes: Notes) -> RegistreOutils:
    """Outils gratuits au score : inspection (§A4.3) et notes (§H7.3).

    Les outils d'action ne figurent pas ici : c'est l'interface qui les pose et les
    renouvelle à chaque frame (§A5.2).
    """
    return RegistreOutils(
        [
            outil_depuis_schema(
                SCHEMA_INSPECT,
                lambda **kwargs: outil_inspect(memoire, **kwargs),
                ["inspection"],
            ),
            outil_depuis_schema(
                SCHEMA_READ_PIXELS,
                lambda **kwargs: outil_read_pixels(memoire, **kwargs),
                ["inspection"],
            ),
            outil_depuis_schema(
                SCHEMA_DIFF,
                lambda **kwargs: outil_diff(memoire, **kwargs),
                ["inspection"],
            ),
            outil_depuis_schema(SCHEMA_NOTE_READ, lambda name: note_read(notes, name), ["notes"]),
            outil_depuis_schema(
                SCHEMA_NOTE_WRITE,
                lambda name, content: note_write(notes, name, content),
                ["notes"],
            ),
        ]
    )


def jouer_un_jeu(
    config: Config,
    workspace: Workspace,
    plafonds: Plafonds,
    game_id: str,
    baselines: Sequence[int],
    card_id: str | None,
    client_llm: LLMClient,
    client_arc: ArcClient,
    notes: Notes,
) -> ResultatJeu:
    """Monte l'agent complet sur un jeu, le joue, et mesure ce qu'il a fait.

    Un client ARC **neuf par jeu** : son historique typé et son suivi de score sont
    ceux d'une partie, pas d'une campagne.
    """
    memoire = MemoireFrames()
    registre = registre_de_jeu(memoire, notes)
    interface = InterfaceArc(
        client_arc, memoire=memoire, game_id=game_id, card_id=card_id, registre=registre
    )
    interface.demarrer()

    lignee = Lignee.ouvrir(workspace.chemin / "lineage" / game_id, ScorerARC())
    boucle = BoucleAgent(
        replace(
            config,
            actions_max_niveau=plafonds.actions_niveau,
            actions_max_jeu=plafonds.actions_jeu,
        ),
        client_llm,
        registre,
        interface,
        notes,
        workspace=workspace,
        superviseur=Superviseur(config, client_llm),
        lignee=lignee,
        jeu=game_id,
    )

    debut = time.monotonic()

    def arret_anticipe() -> str | None:
        """Budgets de campagne, évalués ENTRE deux tours (§A7.4, §H8.3)."""
        if plafonds.secondes_jeu is not None:
            ecoule = time.monotonic() - debut
            if ecoule >= plafonds.secondes_jeu:
                return f"budget de temps du jeu épuisé ({plafonds.secondes_jeu} s)"
        if plafonds.tokens_jeu is not None:
            consommes = boucle.bilan.tokens_prompt + boucle.bilan.tokens_generes
            if consommes >= plafonds.tokens_jeu:
                return f"budget de tokens du jeu épuisé ({plafonds.tokens_jeu})"
        return None

    bilan: Bilan = boucle.executer(plafonds.tours_max, arret_anticipe=arret_anticipe)
    secondes = time.monotonic() - debut

    client_arc.historique.ecrire(workspace.frames / game_id)
    niveaux = tuple(niveaux_joues(client_arc.historique.entrees, baselines))
    resultat = ResultatJeu(
        game_id=game_id,
        guid=interface.guid or "",
        niveaux=niveaux,
        rhae=rhae_jeu(niveaux),
        tours=len(bilan.tours),
        arret=bilan.arret,
        actions=interface.comptage.actions_jeu,
        niveaux_completes=bilan.niveaux_completes,
        game_overs=bilan.game_overs,
        tokens_prompt=bilan.tokens_prompt,
        tokens_generes=bilan.tokens_generes,
        secondes=secondes,
        continuations=bilan.continuations,
        depassements=bilan.depassements,
        interventions=bilan.interventions,
        versions_committees=bilan.versions_committees,
    )
    _journal.info("jeu terminé", extra={"jeu": game_id, "rhae": resultat.rhae.valeur})
    workspace.metrique("jeu", **resultat.en_json())
    return resultat


def executer_campagne(
    config: Config,
    workspace: Workspace,
    plafonds: Plafonds,
    jeux: Sequence[str] | None = None,
    autorise_publication: bool = False,
    client_llm: LLMClient | None = None,
    fabrique_arc: Any = None,
    etat: EtatCampagne | None = None,
) -> ResultatCampagne:
    """Exécute une campagne, jeu par jeu, en persistant l'état après chacun (§A7).

    `etat` non nul = reprise : les jeux déjà terminés ne sont pas rejoués et le
    scorecard ouvert est réutilisé (§H13.2, §A7.4).
    """
    valider(config, plafonds, autorise_publication)
    fabriquer = fabrique_arc or (lambda: ArcClient(config))
    llm = client_llm or LLMClient(config)

    catalogue = {str(jeu["game_id"]): jeu for jeu in fabriquer().games()}
    if etat is None:
        demandes = list(jeux) if jeux is not None else list(catalogue)
        if not demandes:
            raise CampagneInvalide("aucun jeu à jouer : le périmètre est vide")
        inconnus = [jeu for jeu in demandes if jeu not in catalogue]
        if inconnus:
            raise CampagneInvalide(
                f"jeux inconnus du serveur : {', '.join(inconnus)} ; "
                f"disponibles : {', '.join(sorted(catalogue))}"
            )
        etat = EtatCampagne(
            run_id=workspace.run_id,
            mode=config.mode.value,
            plafonds=plafonds,
            jeux_demandes=demandes,
            autorise_publication=autorise_publication,
        )
        etat.ecrire(workspace)

    if etat.card_id is None:
        etat.card_id = fabriquer().open_scorecard(list(ETIQUETTES))
        etat.ecrire(workspace)

    notes = Notes(workspace.notes)
    for game_id in etat.restants():
        baselines = [int(valeur) for valeur in catalogue[game_id]["baseline_actions"]]
        etat.resultats.append(
            jouer_un_jeu(
                config,
                workspace,
                plafonds,
                game_id,
                baselines,
                etat.card_id,
                llm,
                fabriquer(),
                notes,
            )
        )
        etat.ecrire(workspace)

    fabriquer().close_scorecard(etat.card_id)
    jeux_joues = tuple(etat.resultats)
    resultat = ResultatCampagne(
        run_id=etat.run_id,
        mode=etat.mode,
        card_id=etat.card_id,
        plafonds=etat.plafonds,
        jeux=jeux_joues,
        score_global=rhae_global([jeu.rhae.valeur for jeu in jeux_joues]),
    )
    # Import local : le rapport lit les structures de ce module, l'importer en tête
    # ferait un cycle. « Campagne terminée ⇒ rapport écrit » est un invariant du
    # runner, pas un devoir de l'appelant (§A7.3).
    from avo.arc import rapport

    rapport.ecrire(workspace, resultat)
    return resultat


def reprendre_campagne(
    config: Config,
    racine: Path,
    run_id: str,
    client_llm: LLMClient | None = None,
    fabrique_arc: Any = None,
) -> ResultatCampagne:
    """Reprend un run : les jeux terminés ne sont pas rejoués (§H13.2, §A7.4)."""
    chemin = racine / run_id
    if not chemin.is_dir():
        raise CampagneInvalide(f"run inconnu : {chemin} n'existe pas")
    workspace = Workspace(racine, run_id)
    etat = EtatCampagne.lire(workspace)
    _journal.info(
        "reprise de campagne",
        extra={"run": run_id, "termines": len(etat.resultats), "restants": len(etat.restants())},
    )
    return executer_campagne(
        config,
        workspace,
        etat.plafonds,
        jeux=etat.jeux_demandes,
        autorise_publication=etat.autorise_publication,
        client_llm=client_llm,
        fabrique_arc=fabrique_arc,
        etat=etat,
    )
