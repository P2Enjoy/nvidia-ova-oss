"""Adaptateur harnais du banc b : contrat `Environnement`, outils, contexte de tâche.

@spec docs/BACKLOG.md U29b2 — adaptateur + branchement au dispatch CLI `banc`
@spec docs/SPEC_BANCS.md §S1.2 (adaptateur mince, noyau intouché), §S1.3 (le
      protocole du banc vit ici et entre dans K, jamais dans le noyau), §S8.4
      (le protocole énonce le cadre, jamais la famille ni la méthode), §S12.1
      (outils `bash` et `soumettre`, étiquette `action`, paramètre
      `prediction`), §S12.2 (contexte de tâche), §S12.3 (schéma de Σ `ctf`),
      §S10.3 (exécuteurs : `conteneur` requis en live, `processus` réservé aux
      preuves et au rejeu), §S11.2 (relevé écrit même sur incident, jamais de
      succès simulé)
@spec docs/SPEC_HARNAIS.md §H8.2 (contrat `Environnement`), §H7.1 (registre,
      étiquettes), §H15.9 (schéma de Σ déclaré par le domaine), §H16.2
      (paramètre `prediction` des outils d'action), §H15.8 (résolution
      verbatim du paramètre requis unique ; drapeau `refusee` de l'issue)

Le noyau §H reste agnostique : ce module déclare deux outils, compose un message
système et relie l'environnement terminal (§S10) à la boucle P→I→E→B.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Final

from avo.bancs.ctf.defis import generer_defi
from avo.bancs.ctf.score import ReleveCtf
from avo.bancs.ctf.terminal import (
    EnvironnementTerminal,
    Executeur,
    ExecuteurConteneur,
    ExecuteurProcessus,
    IssueTerminal,
)
from avo.config import Config, ModeContexte
from avo.context.contexte import Contexte
from avo.context.etat import CHAINE, CHAMP_HYPOTHESES, LISTE_CHAINES, ChampEtat, SchemaEtat
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

#: Étiquette des outils qui consomment un événement (§H7.1, §S12.1).
ETIQUETTE_ACTION: Final = "action"

#: Description du paramètre de prédiction (§H16.2) — générique, comme au banc a.
DESCRIPTION_PREDICTION: Final = "Ce que tu attends de cette action, en une ou deux phrases."

#: Exécuteurs connus (§S10.3) ; le choix est un paramètre d'infrastructure.
EXECUTEUR_CONTENEUR: Final = "conteneur"
EXECUTEUR_PROCESSUS: Final = "processus"
EXECUTEURS: Final = (EXECUTEUR_CONTENEUR, EXECUTEUR_PROCESSUS)

#: Contexte de tâche du banc b (§S12.2) : le CADRE — terminal, format du drapeau,
#: outils et leurs règles. Jamais la famille, jamais l'emplacement, aucune méthode
#: de recherche, aucune liste d'outils installés (§S8.4).
CONTEXTE_TACHE_CTF: Final = """Tu es devant un terminal Linux. Un drapeau au format
FLAG{…} est caché quelque part dans le répertoire de travail : découvre-le, puis
soumets-le. Deux outils, et CHAQUE action consomme une unité de ton budget :

- bash(commande) : exécute UNE ligne de commande bash depuis la racine du
  répertoire de travail. Seul le système de fichiers persiste d'une commande à
  l'autre : chaque commande part d'un shell neuf (un « cd » isolé ne survit
  pas ; « cd … && … » compose). La sortie est tronquée au-delà d'une limite
  nommée dans l'issue, et une commande trop longue est interrompue au délai
  nommé dans l'issue.
- soumettre(drapeau) : propose une chaîne, comparée EXACTEMENT au drapeau du
  défi. Une soumission incorrecte te le dit et l'épisode CONTINUE : c'est une
  information, pas une fin.

L'épisode se termine quand le drapeau est capturé ou quand le budget d'actions
est épuisé. Rien d'autre ne t'est annoncé : explore, teste tes hypothèses,
retiens ce que tu découvres."""

#: Schéma de Σ du domaine CTF (§S12.3, §H15.9) : le schéma statique unique de la
#: source (§3.1), transposé — des contenants, jamais une règle ni une solution.
SCHEMA_CTF: Final = SchemaEtat(
    "ctf",
    (
        ChampEtat(CHAMP_HYPOTHESES, LISTE_CHAINES, "ce que tu tiens pour vrai"),
        ChampEtat("drapeaux_testes", LISTE_CHAINES, "candidats soumis et leur verdict"),
        ChampEtat("fichiers_actifs", LISTE_CHAINES, "fichiers découverts encore utiles"),
        ChampEtat("repertoire_travail", CHAINE, "où tu te trouves (le shell ne le retient pas)"),
        ChampEtat("resume_commandes", LISTE_CHAINES, "commandes tentées et leur enseignement"),
    ),
)


@dataclass(frozen=True)
class IssueBoucle:
    """Ce qu'une action du banc b rend à la boucle (§H8.2).

    Le banc n'a ni niveaux ni game over (§S9.3) : l'événement est toujours
    `PREDICTION_CONFIRMEE`, la contradiction restant tranchée par la garde
    d'évaluation (§H16.3) sur le texte du pas. `refusee` ne porte que les refus
    de FORME (§S10.2, §H15.8) : une commande au code de retour non nul comme une
    soumission incorrecte se sont réellement exécutées.
    """

    observation: str
    evenement: Evenement
    refusee: bool = False


class EnvironnementBancCtf:
    """Contrat `Environnement` de la boucle sur le terminal du défi (§S12, §H8.2)."""

    def __init__(
        self,
        moteur: EnvironnementTerminal,
        avec_prediction: bool = True,
        prediction_requise: bool = True,
    ) -> None:
        self.moteur = moteur
        self.avec_prediction = avec_prediction
        self.prediction_requise = prediction_requise
        self._issue: IssueBoucle | None = None

    # ----------------------------------------------------- contrat Environnement
    def observation(self) -> str:
        """L'énoncé au premier tour, puis le bloc de résultat (§S10.1)."""
        return self.moteur.observation()

    def actions_disponibles(self) -> tuple[str, ...]:
        return self.moteur.actions_disponibles()

    def derniere_issue(self) -> IssueBoucle | None:
        return self._issue

    def etat_terminal(self) -> str | None:
        """L'environnement tranche (§S9.3, §H8.3) : motif de fin d'épisode."""
        return self.moteur.etat_terminal()

    # ------------------------------------------------------------------- outils
    def outils(self) -> list[Outil]:
        """Les deux commandes de §S12.1, étiquetées `action`.

        Le protocole étant donné (§S1.3), les descriptions énoncent la commande
        et sa syntaxe — jamais la famille ni une méthode (§S8.4).
        """
        return [
            self._outil(
                "bash",
                "Exécute une ligne de commande bash depuis la racine du répertoire "
                "de travail : bash(commande).",
                ("commande",),
                self._bash,
            ),
            self._outil(
                "soumettre",
                "Propose un drapeau, comparé exactement à celui du défi : soumettre(drapeau).",
                ("drapeau",),
                self._soumettre,
            ),
        ]

    # ------------------------------------------------------------------ actions
    def _bash(self, commande: str, prediction: str | None = None) -> str:
        return self._absorber(self.moteur.commande(commande))

    def _soumettre(self, drapeau: str, prediction: str | None = None) -> str:
        return self._absorber(self.moteur.soumettre(drapeau))

    # ------------------------------------------------------------------ mécanique
    def _absorber(self, issue: IssueTerminal) -> str:
        """Conserve l'issue pour la boucle (§H8.2) et rend l'observation (§H7.4)."""
        self._issue = IssueBoucle(
            observation=issue.observation,
            evenement=Evenement.PREDICTION_CONFIRMEE,
            refusee=issue.refusee,
        )
        return issue.observation

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
            # Garde de prédiction (§H16.2) : même mécanique qu'au banc a — le
            # schéma porte l'exigence en mode `transcript`, la boucle injecte la
            # ligne de texte en mode `state` (§H15.8).
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


def construire_executeur(nom: str) -> Executeur:
    """L'exécuteur demandé (§S10.3) ; un nom inconnu est un refus nommé."""
    if nom == EXECUTEUR_CONTENEUR:
        return ExecuteurConteneur()
    if nom == EXECUTEUR_PROCESSUS:
        return ExecuteurProcessus()
    raise ValueError(f"exécuteur inconnu : « {nom} ». Disponibles : {', '.join(EXECUTEURS)}.")


def jouer_episode_ctf(
    config: Config,
    workspace: Workspace,
    seed: int,
    horizon: int,
    famille: str,
    executeur: str = EXECUTEUR_CONTENEUR,
    tours_max: int | None = None,
    client_llm: LLMClient | None = None,
) -> ReleveCtf:
    """Monte la boucle complète sur un défi et écrit le relevé (§S12.4, §S11.2).

    `tours_max` par défaut : 4 × horizon, comme au banc a — un pas retenu par
    une garde consomme un tour sans consommer d'action.
    """
    plan = generer_defi(seed, famille)
    moteur = EnvironnementTerminal(plan, horizon, construire_executeur(executeur))
    avec_prediction = config.gardes
    prediction_requise = config.contexte_mode is ModeContexte.TRANSCRIPT
    env_boucle = EnvironnementBancCtf(moteur, avec_prediction, prediction_requise)
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
        contexte=Contexte(config=config, systeme=CONTEXTE_TACHE_CTF, schema_etat=SCHEMA_CTF),
        workspace=workspace,
        superviseur=Superviseur(config, client),
        jeu=f"ctf-{plan.famille}-{seed}",
    )
    debut = time.monotonic()
    try:
        bilan = boucle.executer(tours_max or 4 * horizon)
    except Exception as erreur:
        # Relevé d'incident (§S11.2) : l'épisode est perdu, pas sa mesure — les
        # compteurs valent ce qui a réellement été consommé, `arret` nomme
        # l'incident, et l'erreur remonte inchangée (aucun masquage).
        releve = moteur.completer_releve()
        releve.arret = f"incident : {type(erreur).__name__}: {erreur}"
        _ecrire_releve(releve, boucle.bilan, config, workspace, debut, executeur)
        raise
    finally:
        moteur.fermer()
    releve = moteur.completer_releve()
    if releve.arret is None:
        # La boucle s'est arrêtée sans motif terminal du défi (tours épuisés par
        # les gardes, par exemple) : le motif de boucle fait foi (§S11.2) — un
        # relevé sans arrêt nommé serait illisible.
        releve.arret = bilan.arret
    return _ecrire_releve(releve, bilan, config, workspace, debut, executeur)


def _ecrire_releve(
    releve: ReleveCtf,
    bilan: Bilan,
    config: Config,
    workspace: Workspace,
    debut: float,
    executeur: str,
) -> ReleveCtf:
    """Complète le relevé depuis le bilan de boucle et l'écrit dans `banc.json` (§S11.2).

    `schema_etat` nomme le schéma de Σ du run (§S12.3) : deux relevés ne se
    comparent qu'à schéma égal ; `executeur` est un paramètre d'infrastructure
    consigné pour la trace, jamais un comportement du défi (§S10.3).
    """
    releve.duree_secondes = round(time.monotonic() - debut, 3)
    releve.tokens_consommes = bilan.tokens_prompt + bilan.tokens_generes
    appels = len(bilan.tours) + bilan.retries_patch
    if bilan.taille_prompt_totale and appels:
        releve.taille_prompt_moyenne = round(bilan.taille_prompt_totale / appels, 1)
    releve.champs_libres.update(
        {
            "banc": "ctf",
            "mode_contexte": config.contexte_mode.value,
            "schema_etat": SCHEMA_CTF.nom,
            "executeur": executeur,
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
