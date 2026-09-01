"""Adaptateur harnais du banc a : contrat `Environnement`, outils, contexte de tâche.

@spec docs/BACKLOG.md U29a2 — adaptateur harnais + CLI `banc` ; U29a4 —
      branchement du Dépôt logiciel à l'adaptateur et à la CLI
@spec docs/SPEC_BANCS.md §S1.2 (adaptateur mince, noyau intouché), §S1.3 (règles
      données à l'agent : le protocole du banc vit ici et entre dans K, jamais
      dans le noyau), §S2.3 (l'agent ne voit que les observations et les issues
      de ses actions), §S4.2 et §S4.5 (protocole du Dépôt logiciel donné à
      l'agent), §S6.1 (contrat de boucle et outils étiquetés `action` avec
      `prediction`), §S6.2 (contexte de tâche : protocole sans état de vérité),
      §S5.3 (relevé `banc.json` écrit dans le workspace du run)
@spec docs/SPEC_HARNAIS.md §H8.2 (contrat `Environnement`), §H7.1 (registre,
      étiquettes), §H16.2 (paramètre `prediction` des outils d'action),
      §H15.8 (le message système du mode `state` est celui du contexte monté)

Le noyau §H reste agnostique : ce module ne fait que déclarer des outils, composer
un message système et relier les environnements du banc (§S3 Entrepôt, §S4 Dépôt
logiciel) à la boucle P→I→E→B.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Final, Generic, Protocol, TypeVar

from avo.bancs.skillexec.depot import EnvironnementDepot, generer_episode_depot
from avo.bancs.skillexec.entrepot import EnvironnementEntrepot
from avo.bancs.skillexec.generation import generer_episode
from avo.bancs.skillexec.score import Releve
from avo.config import Config, ModeContexte
from avo.context.contexte import Contexte
from avo.llm.client import LLMClient
from avo.loop.boucle import Bilan, BoucleAgent
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

#: Contexte de tâche de l'Entrepôt (§S1.3, §S6.2) : persona, espace d'actions,
#: règles de validité et obligations — la « documentation d'API » que le responsable
#: donne à l'agent. Jamais l'état de vérité, jamais la suite d'événements, aucune
#: solution.
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
bruit de capteurs, sans rapport avec la tâche. Les lignes sous
« --- ALERTE EXTERNE --- » rapportent des changements RÉELS effectués hors de
ton contrôle : prends-les en compte et mets ton état à jour.

L'état de l'entrepôt ne t'est jamais montré : tiens-le toi-même, exactement, car
le score est le nombre d'événements traités par l'action correcte."""

#: Contexte de tâche du Dépôt logiciel (§S1.3, §S6.2) : le protocole de §S4.2 et
#: §S4.5, donné comme une documentation d'API. Jamais l'état de vérité, jamais la
#: suite d'événements, aucune solution.
CONTEXTE_TACHE_DEPOT: Final = """Tu travailles dans un dépôt logiciel simulé. Les
demandes de fonctionnalité arrivent une par une : la demande demande_N porte le
fichier fichier_N et la branche branche_N. Les événements arrivent un par un, et
CHAQUE événement appelle exactement UNE action de ta part :

- « Issue affectée : demande_N — écrire fichier_N sur branche_N. » →
  commit(branche, fichier) : écrit le fichier sur la branche, en la créant au
  besoin. Valide seulement pour la branche d'une demande annoncée non encore
  fusionnée. La CI de la branche apparaît à son premier commit : verte, ou rouge
  si le travail a introduit un défaut.
- « Revue approuvée pour branche_N : la PR peut être ouverte. » →
  create_pr(branche) : ouvre une PR pour la branche. Valide seulement si la
  branche existe et n'a pas déjà une PR ouverte. Les numéros de PR croissent
  depuis 1 dans l'ordre où TU les ouvres. Si la branche n'existe pas ou porte
  déjà une PR, il n'y a rien à ouvrir : joue wait().
- « CI en échec pour PR #k (branche_N) : erreur de lint. » → fix_ci(branche) :
  corrige le défaut ; la CI passe verte et le reste. Valide seulement si la
  branche existe et que sa CI est rouge. Sinon, il n'y a rien à corriger : joue
  wait().
- « CI verte pour PR #k (branche_N) : prête à fusionner. » → merge(pr) :
  fusionne la PR dans master, la ferme et supprime sa branche. Valide dès que la
  PR est ouverte — mais fusionner une PR dont la CI est rouge CASSE la CI de
  master, et la demande n'est alors pas correctement résolue. Si ta PR #k n'est
  pas ouverte avec une CI verte, joue wait().
- wait() : ne fait rien ; c'est la bonne réponse quand l'action appelée par
  l'événement n'est plus jouable sur l'état réel du dépôt.

Une action invalide rend une erreur nommée, ne change rien au dépôt, et
l'événement est perdu. Une action valide s'exécute toujours, même si elle ne
répond pas à l'événement. Les événements référencent les numéros de PR du
déroulé nominal : si tu as divergé, ils peuvent ne plus correspondre aux tiens.
Les lignes sous « --- TELEMETRIE DE FOND --- » sont de la télémétrie de serveurs
sans rapport avec la tâche. Les lignes sous « --- ALERTE EXTERNE --- »
rapportent des changements RÉELS effectués hors de ton contrôle : prends-les en
compte et mets ton état à jour.

L'état du dépôt ne t'est jamais montré : tiens-le toi-même, exactement, car le
score est le nombre d'événements traités par l'action correcte, et une demande
n'est résolue que si son fichier atteint master sans casser la CI."""


@dataclass(frozen=True)
class IssueBoucle:
    """Ce qu'une action du banc rend à la boucle (§H8.2).

    Le banc n'a ni niveaux ni game over (§S3.7) : l'événement est toujours
    `PREDICTION_CONFIRMEE`, la contradiction restant tranchée par la garde
    d'évaluation (§H16.3) sur le texte du pas.
    """

    observation: str
    evenement: Evenement


class MoteurBanc(Protocol):
    """Ce que la mécanique commune attend d'un moteur d'environnement (§S6.1)."""

    def observation(self) -> str: ...

    def etat_terminal(self) -> str | None: ...


TMoteur = TypeVar("TMoteur", bound=MoteurBanc)


class _EnvironnementBancCommun(Generic[TMoteur]):
    """Mécanique partagée des environnements de boucle du banc (§S6.1, §H8.2).

    Les sous-classes déclarent leurs outils et leurs actions ; la composition de
    l'observation, l'issue et le motif de fin sont identiques partout — même
    comportement dans les deux environnements, par construction.
    """

    def __init__(
        self,
        moteur: TMoteur,
        avec_prediction: bool = True,
        prediction_requise: bool = True,
    ) -> None:
        self.moteur: TMoteur = moteur
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

    def derniere_issue(self) -> IssueBoucle | None:
        return self._issue

    def etat_terminal(self) -> str | None:
        """L'environnement tranche (§S3.7, §S4.6, §H8.3) : motif de fin d'épisode."""
        return self.moteur.etat_terminal()

    # ------------------------------------------------------------------ mécanique
    def _absorber(self, observation: str) -> str:
        """Conserve l'issue pour la boucle (§H8.2) et la rend au modèle (§H7.4)."""
        self._issue = IssueBoucle(observation=observation, evenement=Evenement.PREDICTION_CONFIRMEE)
        return observation

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


class EnvironnementBancEntrepot(_EnvironnementBancCommun[EnvironnementEntrepot]):
    """Contrat `Environnement` de la boucle sur l'entrepôt (§S6.1, §H8.2)."""

    def actions_disponibles(self) -> tuple[str, ...]:
        return ("store", "ship", "move", "wait")

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

    # ------------------------------------------------------------------ actions
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


class EnvironnementBancDepot(_EnvironnementBancCommun[EnvironnementDepot]):
    """Contrat `Environnement` de la boucle sur le dépôt logiciel (§S6.1, §H8.2)."""

    def actions_disponibles(self) -> tuple[str, ...]:
        return ("commit", "create_pr", "merge", "fix_ci", "wait")

    # ------------------------------------------------------------------- outils
    def outils(self) -> list[Outil]:
        """Les cinq commandes de §S4.2, étiquetées `action` (§S6.1).

        Comme pour l'Entrepôt, le protocole est donné (§S1.3) : les descriptions
        énoncent commande, syntaxe et effet. Le numéro de PR de `merge` voyage en
        texte, comme tout paramètre du banc — son analyse appartient au moteur
        (§S4.2), qui nomme l'erreur d'un numéro imprenable.
        """
        return [
            self._outil(
                "commit",
                "Écrit un fichier sur la branche d'une demande annoncée, en la "
                "créant au besoin : commit(branche, fichier).",
                ("branche", "fichier"),
                self._commit,
            ),
            self._outil(
                "create_pr",
                "Ouvre une PR pour une branche existante qui n'en a pas : create_pr(branche).",
                ("branche",),
                self._create_pr,
            ),
            self._outil(
                "merge",
                "Fusionne une PR ouverte dans master et supprime sa branche : merge(pr).",
                ("pr",),
                self._merge,
            ),
            self._outil(
                "fix_ci",
                "Corrige le défaut d'une branche dont la CI est rouge : fix_ci(branche).",
                ("branche",),
                self._fix_ci,
            ),
            self._outil("wait", "Ne fait rien : wait().", (), self._wait),
        ]

    # ------------------------------------------------------------------ actions
    def _commit(self, branche: str, fichier: str, prediction: str | None = None) -> str:
        return self._absorber(self.moteur.commit(branche, fichier).observation)

    def _create_pr(self, branche: str, prediction: str | None = None) -> str:
        return self._absorber(self.moteur.create_pr(branche).observation)

    def _merge(self, pr: str, prediction: str | None = None) -> str:
        return self._absorber(self.moteur.merge(pr).observation)

    def _fix_ci(self, branche: str, prediction: str | None = None) -> str:
        return self._absorber(self.moteur.fix_ci(branche).observation)

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
    environnement: str = "entrepot",
    derive: bool = False,
) -> Releve:
    """Monte la boucle complète sur un épisode et écrit le relevé (§S6.3, §S5.3).

    `tours_max` par défaut : 4 × horizon (décision, journal 2026-09-01 suite 13) —
    un pas retenu par une garde consomme un tour sans consommer d'événement.
    `environnement` choisit le terrain (§S2.1) : `entrepot` (§S3) ou `depot`
    (§S4) — même boucle, mêmes gardes, même relevé. `derive` active la condition 3
    (§S3.8, §S4.7) : dérive d'état et mesure de récupération (§S5.5).
    """
    moteur: EnvironnementEntrepot | EnvironnementDepot
    env_boucle: _EnvironnementBancCommun[Any]
    avec_prediction = config.gardes
    prediction_requise = config.contexte_mode is ModeContexte.TRANSCRIPT
    if environnement == "entrepot":
        moteur = EnvironnementEntrepot(generer_episode(seed, horizon, bruit, derive))
        env_boucle = EnvironnementBancEntrepot(moteur, avec_prediction, prediction_requise)
        systeme = CONTEXTE_TACHE
    elif environnement == "depot":
        moteur = EnvironnementDepot(generer_episode_depot(seed, horizon, bruit, derive))
        env_boucle = EnvironnementBancDepot(moteur, avec_prediction, prediction_requise)
        systeme = CONTEXTE_TACHE_DEPOT
    else:
        raise ValueError(f"environnement inconnu : {environnement}")
    notes = Notes(workspace.notes)
    registre = RegistreOutils(
        [
            outil_depuis_schema(SCHEMA_NOTE_READ, lambda name: note_read(notes, name), ["notes"]),
            outil_depuis_schema(
                SCHEMA_NOTE_WRITE,
                lambda name, content: note_write(notes, name, content),
                ["notes"],
            ),
            *env_boucle.outils(),
        ]
    )
    client = client_llm or LLMClient(config)
    boucle = BoucleAgent(
        config,
        client,
        registre,
        env_boucle,
        notes,
        contexte=Contexte(config=config, systeme=systeme),
        workspace=workspace,
        superviseur=Superviseur(config, client),
        jeu=f"skillexec-{environnement}-{seed}",
    )
    debut = time.monotonic()
    try:
        bilan = boucle.executer(tours_max or 4 * horizon)
    except Exception as erreur:
        # Relevé d'incident (§S5.3) : l'épisode est perdu, pas sa mesure — les
        # compteurs valent ce qui a réellement été consommé, `arret` nomme
        # l'incident, et l'erreur remonte inchangée (aucun masquage).
        _ecrire_releve(
            _releve_final(moteur),
            bilan=boucle.bilan,
            config=config,
            workspace=workspace,
            debut=debut,
            arret=f"incident : {type(erreur).__name__}: {erreur}",
            environnement=environnement,
        )
        raise
    return _ecrire_releve(
        _releve_final(moteur),
        bilan=bilan,
        config=config,
        workspace=workspace,
        debut=debut,
        arret=bilan.arret,
        environnement=environnement,
    )


def _releve_final(moteur: EnvironnementEntrepot | EnvironnementDepot) -> Releve:
    """Le relevé du moteur, complété des compteurs propres à l'environnement.

    Le Dépôt logiciel ajoute la résolution B.1 (§S4.4) ; les deux environnements
    ajoutent la mesure de récupération quand la dérive est active (§S5.5).
    """
    return moteur.completer_releve()


def _ecrire_releve(
    releve: Releve,
    bilan: Bilan,
    config: Config,
    workspace: Workspace,
    debut: float,
    arret: str,
    environnement: str,
) -> Releve:
    """Complète le relevé depuis le bilan de boucle et l'écrit dans `banc.json` (§S5.3)."""
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
            "environnement": environnement,
            "mode_contexte": config.contexte_mode.value,
            "arret": arret,
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
