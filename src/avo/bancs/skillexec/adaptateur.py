"""Adaptateur harnais du banc a : contrat `Environnement`, outils, contexte de tâche.

@spec docs/BACKLOG.md U29a2 — adaptateur harnais + CLI `banc`
@spec docs/SPEC_BANCS.md §S1.2 (adaptateur mince, noyau intouché), §S1.3 (règles
      données à l'agent : le protocole du banc vit ici et entre dans K, jamais
      dans le noyau), §S2.3 (l'agent ne voit que les observations et les issues
      de ses actions), §S6.1 (contrat de boucle et outils étiquetés `action`
      avec `prediction`), §S6.2 (contexte de tâche : protocole sans état de
      vérité), §S5.3 (relevé `banc.json` écrit dans le workspace du run)
@spec docs/SPEC_HARNAIS.md §H8.2 (contrat `Environnement`), §H7.1 (registre,
      étiquettes), §H16.2 (paramètre `prediction` des outils d'action),
      §H15.8 (le message système du mode `state` est celui du contexte monté)

Le noyau §H reste agnostique : ce module ne fait que déclarer des outils, composer
un message système et relier l'environnement Entrepôt (§S3) à la boucle P→I→E→B.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Final

from avo.bancs.skillexec.entrepot import EnvironnementEntrepot
from avo.bancs.skillexec.generation import generer_episode
from avo.bancs.skillexec.score import Releve
from avo.config import Config, ModeContexte
from avo.context.contexte import Contexte
from avo.llm.client import LLMClient
from avo.loop.boucle import BoucleAgent
from avo.loop.etats import Evenement
from avo.memory.notes import (
    SCHEMA_NOTE_READ,
    SCHEMA_NOTE_WRITE,
    Notes,
    note_read,
    note_write,
)
from avo.memory.workspace import Workspace
from avo.supervisor import Superviseur
from avo.tools.registre import Outil, RegistreOutils, outil_depuis_schema

#: Étiquette des outils qui consomment un événement (§H7.1, §S6.1).
ETIQUETTE_ACTION: Final = "action"

#: Description du paramètre de prédiction (§H16.2), identique en esprit à celle
#: de l'interface ARC : générique, aucun effet réel décrit.
DESCRIPTION_PREDICTION: Final = "Ce que tu attends de cette action, en une ou deux phrases."

#: Contexte de tâche du banc (§S1.3, §S6.2) : persona, espace d'actions, règles de
#: validité et obligations — la « documentation d'API » que le responsable donne à
#: l'agent. Jamais l'état de vérité, jamais la suite d'événements, aucune solution.
CONTEXTE_TACHE: Final = """Tu gères un entrepôt de 500 étagères, nommées etagere_0 à
etagere_499 ; chacune porte au plus un article. Les événements arrivent un par un,
et CHAQUE événement appelle exactement UNE action de ta part :

- « Livraison reçue : <article>. » → store(article, etagere) : range l'article sur
  une étagère VIDE de ton choix. Valide seulement si l'article est en attente de
  rangement et si l'étagère est vide.
- « Commande client : <article>. » → ship(article, etagere) : expédie l'article
  depuis l'étagère qui le porte. Valide seulement si cette étagère porte
  exactement cet article.
- « Maintenance requise sur <etagere>. » → move(article, source, destination) :
  déplace l'article porté par cette étagère vers une étagère vide. Valide
  seulement si la source porte l'article et si la destination est vide. Si
  l'étagère visée est vide, il n'y a rien à déplacer : joue wait().
- wait() : ne fait rien ; c'est la bonne réponse quand il n'y a rien à faire.

Une action invalide rend une erreur nommée, ne change rien à l'entrepôt, et
l'événement est perdu. Une action valide s'exécute toujours, même si elle ne
répond pas à l'événement. Les lignes sous « --- TELEMETRIE DE FOND --- » sont du
bruit de capteurs, sans rapport avec la tâche.

L'état de l'entrepôt ne t'est jamais montré : tiens-le toi-même, exactement, car
le score est le nombre d'événements traités par l'action correcte."""


@dataclass(frozen=True)
class IssueBoucle:
    """Ce qu'une action du banc rend à la boucle (§H8.2).

    Le banc n'a ni niveaux ni game over (§S3.7) : l'événement est toujours
    `PREDICTION_CONFIRMEE`, la contradiction restant tranchée par la garde
    d'évaluation (§H16.3) sur le texte du pas.
    """

    observation: str
    evenement: Evenement


class EnvironnementBancEntrepot:
    """Contrat `Environnement` de la boucle sur l'entrepôt (§S6.1, §H8.2)."""

    def __init__(
        self,
        moteur: EnvironnementEntrepot,
        avec_prediction: bool = True,
        prediction_requise: bool = True,
    ) -> None:
        self.moteur = moteur
        self.avec_prediction = avec_prediction
        self.prediction_requise = prediction_requise
        self._issue: IssueBoucle | None = None

    # ----------------------------------------------------- contrat Environnement
    def observation(self) -> str:
        """L'événement courant, précédé de l'issue de la dernière action (§S2.3).

        En mode `state`, le prompt d'un pas ne porte que (P, Σ, O) : sans ce
        rappel, l'agent ne verrait jamais le « Succès/error » de son action
        précédente, que la source lui donne (décision, journal 2026-09-01
        suite 13).
        """
        courante = self.moteur.observation()
        if self._issue is None:
            return courante
        return f"Issue de ta dernière action : {self._issue.observation}\n\n{courante}"

    def actions_disponibles(self) -> tuple[str, ...]:
        return ("store", "ship", "move", "wait")

    def derniere_issue(self) -> IssueBoucle | None:
        return self._issue

    def etat_terminal(self) -> str | None:
        """L'environnement tranche (§S3.7, §H8.3) : motif quand l'épisode est épuisé."""
        return self.moteur.etat_terminal()

    # ------------------------------------------------------------------- outils
    def outils(self) -> list[Outil]:
        """Les quatre commandes de §S3.2, étiquetées `action` (§S6.1).

        Le protocole étant donné (§S1.3), les descriptions énoncent la commande,
        sa syntaxe et son effet — contrairement à ARC (§A5.1), et c'est assumé.
        """
        return [
            self._outil(
                "store",
                "Range un article en attente sur une étagère vide : store(article, etagere).",
                ("article", "etagere"),
                self._store,
            ),
            self._outil(
                "ship",
                "Expédie un article depuis l'étagère qui le porte : ship(article, etagere).",
                ("article", "etagere"),
                self._ship,
            ),
            self._outil(
                "move",
                "Déplace un article d'une étagère vers une étagère vide : "
                "move(article, source, destination).",
                ("article", "source", "destination"),
                self._move,
            ),
            self._outil("wait", "Ne fait rien : wait().", (), self._wait),
        ]

    def _outil(
        self,
        nom: str,
        description: str,
        requis: tuple[str, ...],
        fonction: Any,
    ) -> Outil:
        proprietes: dict[str, Any] = {cle: {"type": "string"} for cle in requis}
        obligatoires = list(requis)
        if self.avec_prediction:
            # Garde de prédiction (§H16.2) : le schéma porte l'exigence, le
            # registre la fait respecter — une action sans prédiction n'est pas
            # jouée en mode `transcript` ; en mode `state` la prédiction voyage en
            # ligne de texte et la boucle l'injecte (§H15.8).
            proprietes["prediction"] = {"type": "string", "description": DESCRIPTION_PREDICTION}
            if self.prediction_requise:
                obligatoires.append("prediction")
        parametres: dict[str, Any] = {"type": "object", "properties": proprietes}
        if obligatoires:
            parametres["required"] = obligatoires
        return Outil(
            nom=nom,
            description=description,
            parametres=parametres,
            fonction=fonction,
            etiquettes=frozenset({ETIQUETTE_ACTION}),
        )

    # ------------------------------------------------------------------ actions
    def _absorber(self, observation: str) -> str:
        """Conserve l'issue pour la boucle (§H8.2) et la rend au modèle (§H7.4)."""
        self._issue = IssueBoucle(observation=observation, evenement=Evenement.PREDICTION_CONFIRMEE)
        return observation

    def _store(self, article: str, etagere: str, prediction: str | None = None) -> str:
        return self._absorber(self.moteur.store(article, etagere).observation)

    def _ship(self, article: str, etagere: str, prediction: str | None = None) -> str:
        return self._absorber(self.moteur.ship(article, etagere).observation)

    def _move(
        self, article: str, source: str, destination: str, prediction: str | None = None
    ) -> str:
        return self._absorber(self.moteur.move(article, source, destination).observation)

    def _wait(self, prediction: str | None = None) -> str:
        return self._absorber(self.moteur.wait().observation)


def jouer_episode(
    config: Config,
    workspace: Workspace,
    seed: int,
    horizon: int,
    bruit: int = 0,
    tours_max: int | None = None,
    client_llm: LLMClient | None = None,
) -> Releve:
    """Monte la boucle complète sur un épisode et écrit le relevé (§S6.3, §S5.3).

    `tours_max` par défaut : 4 × horizon (décision, journal 2026-09-01 suite 13) —
    un pas retenu par une garde consomme un tour sans consommer d'événement.
    """
    episode = generer_episode(seed, horizon, bruit)
    moteur = EnvironnementEntrepot(episode)
    environnement = EnvironnementBancEntrepot(
        moteur,
        avec_prediction=config.gardes,
        prediction_requise=config.contexte_mode is ModeContexte.TRANSCRIPT,
    )
    notes = Notes(workspace.notes)
    registre = RegistreOutils(
        [
            outil_depuis_schema(SCHEMA_NOTE_READ, lambda name: note_read(notes, name), ["notes"]),
            outil_depuis_schema(
                SCHEMA_NOTE_WRITE,
                lambda name, content: note_write(notes, name, content),
                ["notes"],
            ),
            *environnement.outils(),
        ]
    )
    client = client_llm or LLMClient(config)
    boucle = BoucleAgent(
        config,
        client,
        registre,
        environnement,
        notes,
        contexte=Contexte(config=config, systeme=CONTEXTE_TACHE),
        workspace=workspace,
        superviseur=Superviseur(config, client),
        jeu=f"skillexec-entrepot-{seed}",
    )
    debut = time.monotonic()
    bilan = boucle.executer(tours_max or 4 * horizon)
    releve = moteur.releve
    releve.duree_secondes = round(time.monotonic() - debut, 3)
    releve.tokens_consommes = bilan.tokens_prompt + bilan.tokens_generes
    appels = len(bilan.tours) + bilan.retries_patch
    if bilan.taille_prompt_totale and appels:
        # Mode `state` seulement : la boucle relève la taille (caractères) de
        # chaque prompt émis (§H15.8) ; la moyenne alimente §S5.3.
        releve.taille_prompt_moyenne = round(bilan.taille_prompt_totale / appels, 1)
    releve.champs_libres.update(
        {
            "banc": "skillexec",
            "environnement": "entrepot",
            "mode_contexte": config.contexte_mode.value,
            "arret": bilan.arret,
            "tours": len(bilan.tours),
            "retries_patch": bilan.retries_patch,
            "redemandes_gardes": bilan.redemandes_gardes,
        }
    )
    chemin = workspace.chemin / "banc.json"
    chemin.write_text(
        json.dumps(releve.en_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return releve
