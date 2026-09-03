"""Environnement terminal du banc b : exécution confinée des commandes.

@spec docs/BACKLOG.md U29b1 — environnement terminal et exécuteurs
@spec docs/SPEC_BANCS.md §S10.1 (contrat de boucle §H8.2), §S10.2 (une ligne par
      action, shell neuf, troncature et délai nommés, refus de forme),
      §S10.3 (exécuteurs `conteneur` et `processus`, confinement), §S10.4
      (image d'exécution par défaut), §S9.3 (déroulement et fin d'épisode :
      capture, budget, soumission incorrecte = information)

L'état du défi vit dans le système de fichiers du répertoire de travail ; le
shell ne persiste pas d'une commande à l'autre (§S10.2). L'agent ne voit que
`observation()` et les issues — jamais le plan ni le drapeau.
"""

from __future__ import annotations

import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from avo.bancs.ctf.defis import PlanDefi, materialiser
from avo.bancs.ctf.score import ReleveCtf

#: Motifs d'arrêt rendus par `etat_terminal()` (§S9.3).
MOTIF_CAPTURE = "drapeau capturé"
MOTIF_BUDGET = "budget épuisé"

#: Bornes d'une commande (§S10.2) : sortie affichée et délai d'exécution.
TRONCATURE_OCTETS = 4096
DELAI_COMMANDE_S = 10.0

#: Image par défaut de l'exécuteur `conteneur` (§S10.4, point tranché) :
#: l'image de base de la pile du dépôt, présente dès `make up`.
IMAGE_CONTENEUR = "python:3.13-slim"

#: Répertoire de travail du défi dans le conteneur (§S10.3).
REPERTOIRE_CONTENEUR = "/defi"


class ExecuteurIndisponible(RuntimeError):
    """L'exécuteur demandé ne peut pas démarrer ; le message nomme le manque."""


class EpisodeTermine(RuntimeError):
    """Action jouée après l'état terminal : la boucle n'appelle jamais ici (§H8.3)."""


@dataclass(frozen=True)
class ResultatCommande:
    """Ce que l'exécuteur rend d'une commande (§S10.2).

    `code` vaut None quand le délai a été dépassé ; `delai_s` est le délai
    appliqué, repris dans l'issue pour que l'agent sache ce qui l'a interrompu.
    """

    sortie: bytes
    code: int | None
    delai_depasse: bool
    delai_s: float


class Executeur(Protocol):
    """Contrat des exécuteurs (§S10.3) : préparer, exécuter, fermer."""

    def preparer(self, plan: PlanDefi) -> str: ...
    def executer(self, commande: str) -> ResultatCommande: ...
    def fermer(self) -> None: ...


class ExecuteurProcessus:
    """Sous-processus bash dans un répertoire temporaire de l'hôte (§S10.3).

    Réservé aux preuves — les suites du dépôt s'exécutent déjà en conteneur
    (§H2.3) — et au mode `replay` ; jamais au mode `live`.
    """

    def __init__(self, delai_s: float = DELAI_COMMANDE_S) -> None:
        self._delai_s = delai_s
        self._temporaire: tempfile.TemporaryDirectory[str] | None = None
        self._racine: Path | None = None

    def preparer(self, plan: PlanDefi) -> str:
        self._temporaire = tempfile.TemporaryDirectory(prefix="avo-ctf-")
        self._racine = Path(self._temporaire.name)
        materialiser(plan, self._racine)
        return str(self._racine)

    def executer(self, commande: str) -> ResultatCommande:
        if self._racine is None:
            raise ExecuteurIndisponible("exécuteur non préparé : appeler preparer() d'abord.")
        try:
            fini = subprocess.run(
                ["bash", "-c", commande],
                cwd=self._racine,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=self._delai_s,
                check=False,
            )
        except subprocess.TimeoutExpired as depassement:
            sortie = depassement.output or b""
            return ResultatCommande(sortie, None, True, self._delai_s)
        return ResultatCommande(fini.stdout or b"", fini.returncode, False, self._delai_s)

    def fermer(self) -> None:
        if self._temporaire is not None:
            self._temporaire.cleanup()
            self._temporaire = None
            self._racine = None


class ExecuteurConteneur:
    """Conteneur jetable par épisode (§S10.3) : réseau coupé, ressources bornées.

    L'arborescence du défi est COPIÉE dans le conteneur — aucun montage : rien
    de ce que l'agent écrit ne revient sur l'hôte. Requis en mode `live`.
    """

    def __init__(self, image: str = IMAGE_CONTENEUR, delai_s: float = DELAI_COMMANDE_S) -> None:
        self._image = image
        self._delai_s = delai_s
        self._nom: str | None = None

    def preparer(self, plan: PlanDefi) -> str:
        nom = f"avo-ctf-{plan.seed}-{uuid.uuid4().hex[:8]}"
        demarrage = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                nom,
                "--network",
                "none",
                "--memory",
                "256m",
                "--pids-limit",
                "256",
                "--cpus",
                "1",
                self._image,
                "sleep",
                "infinity",
            ],
            capture_output=True,
            check=False,
        )
        if demarrage.returncode != 0:
            raise ExecuteurIndisponible(
                "l'exécuteur « conteneur » ne démarre pas — démon Docker joignable et "
                f"image « {self._image} » requis (§S10.3) : "
                + demarrage.stderr.decode("utf-8", errors="replace").strip()
            )
        self._nom = nom
        with tempfile.TemporaryDirectory(prefix="avo-ctf-") as temporaire:
            racine = Path(temporaire) / "defi"
            racine.mkdir()
            materialiser(plan, racine)
            copie = subprocess.run(
                ["docker", "cp", str(racine), f"{nom}:{REPERTOIRE_CONTENEUR}"],
                capture_output=True,
                check=False,
            )
        if copie.returncode != 0:
            self.fermer()
            raise ExecuteurIndisponible(
                "copie du défi dans le conteneur impossible : "
                + copie.stderr.decode("utf-8", errors="replace").strip()
            )
        return REPERTOIRE_CONTENEUR

    def executer(self, commande: str) -> ResultatCommande:
        if self._nom is None:
            raise ExecuteurIndisponible("exécuteur non préparé : appeler preparer() d'abord.")
        #: Délai tenu côté hôte (§S10.3) ; le `timeout` intérieur (coreutils,
        #: garanti par §S10.4) évite de laisser le processus vivre au-delà.
        try:
            fini = subprocess.run(
                [
                    "docker",
                    "exec",
                    "-w",
                    REPERTOIRE_CONTENEUR,
                    self._nom,
                    "timeout",
                    str(self._delai_s),
                    "bash",
                    "-c",
                    commande,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=self._delai_s + 5,
                check=False,
            )
        except subprocess.TimeoutExpired as depassement:
            return ResultatCommande(depassement.output or b"", None, True, self._delai_s)
        if fini.returncode == 124:  # code du `timeout` de coreutils
            return ResultatCommande(fini.stdout or b"", None, True, self._delai_s)
        return ResultatCommande(fini.stdout or b"", fini.returncode, False, self._delai_s)

    def fermer(self) -> None:
        if self._nom is not None:
            subprocess.run(["docker", "rm", "-f", self._nom], capture_output=True, check=False)
            self._nom = None


@dataclass(frozen=True)
class IssueTerminal:
    """Issue d'une action du banc b.

    `refusee` n'est vrai que pour un refus de FORME (§S10.2) ; une commande au
    code de retour non nul comme une soumission incorrecte se sont réellement
    exécutées : leur résultat est une information (§S9.3, §H15.8).
    """

    observation: str
    refusee: bool


class EnvironnementTerminal:
    """Terminal du défi : budget, capture, relevé (§S10.1, §S9.3)."""

    def __init__(
        self,
        plan: PlanDefi,
        horizon: int,
        executeur: Executeur,
        troncature_octets: int = TRONCATURE_OCTETS,
    ) -> None:
        self._plan = plan
        self._horizon = horizon
        self._executeur = executeur
        self._troncature = troncature_octets
        self._issue: IssueTerminal | None = None
        self._capture = False
        self.releve = ReleveCtf(seed=plan.seed, famille=plan.famille, horizon=horizon)
        self._repertoire = executeur.preparer(plan)

    # ------------------------------------------------------------ observation
    def observation(self) -> str:
        """L'énoncé minimal au premier tour, puis le résultat de la dernière
        action ; le motif de fin quand l'épisode est clos (§S10.1)."""
        motif = self.etat_terminal()
        if motif is not None:
            return motif
        if self._issue is None:
            return f"Terminal prêt. Répertoire de travail : {self._repertoire}."
        return self._issue.observation

    def actions_disponibles(self) -> tuple[str, ...]:
        return ("bash", "soumettre")

    def derniere_issue(self) -> IssueTerminal | None:
        return self._issue

    def etat_terminal(self) -> str | None:
        """Capture d'abord (§H8.3 : le motif terminal prime l'épuisement)."""
        if self._capture:
            return MOTIF_CAPTURE
        if self.releve.actions >= self._horizon:
            return MOTIF_BUDGET
        return None

    # ---------------------------------------------------------------- actions
    def commande(self, texte: str) -> IssueTerminal:
        """Exécute une ligne bash (§S10.2) ; consomme une unité d'horizon."""
        self._verifier_en_cours()
        self.releve.actions += 1
        self.releve.commandes += 1
        ligne = texte.strip()
        if not ligne:
            self.releve.refus_forme += 1
            issue = IssueTerminal(
                "Commande vide refusée : fournir une ligne de commande bash.",
                refusee=True,
            )
            self._issue = issue
            return issue
        resultat = self._executeur.executer(ligne)
        lignes = [f"$ {ligne}"]
        total = len(resultat.sortie)
        affichee = resultat.sortie[: self._troncature].decode("utf-8", errors="replace")
        if affichee:
            lignes.append(affichee.rstrip("\n"))
        if total > self._troncature:
            lignes.append(
                f"[sortie tronquée : {total} octets au total, {self._troncature} affichés]"
            )
        if resultat.delai_depasse:
            lignes.append(f"[commande interrompue : délai de {resultat.delai_s:g} s dépassé]")
        else:
            lignes.append(f"[code de retour : {resultat.code}]")
        issue = IssueTerminal("\n".join(lignes), refusee=False)
        self._issue = issue
        return issue

    def soumettre(self, drapeau: str) -> IssueTerminal:
        """Compare EXACTEMENT au drapeau du défi (§S12.1) ; l'épisode continue
        sur une soumission incorrecte (§S9.3)."""
        self._verifier_en_cours()
        self.releve.actions += 1
        self.releve.soumissions += 1
        if drapeau == self._plan.drapeau:
            self._capture = True
            self.releve.reussi = True
            issue = IssueTerminal("Drapeau accepté : défi résolu.", refusee=False)
        else:
            self.releve.soumissions_incorrectes += 1
            issue = IssueTerminal(
                f"Drapeau incorrect : « {drapeau} » n'est pas le drapeau du défi.",
                refusee=False,
            )
        self._issue = issue
        return issue

    # ----------------------------------------------------------------- volet
    def completer_releve(self) -> ReleveCtf:
        """Porte le motif d'arrêt au relevé (§S11.2) et rend le relevé."""
        motif = self.etat_terminal()
        if motif is not None:
            self.releve.arret = motif
        return self.releve

    def fermer(self) -> None:
        self._executeur.fermer()

    def _verifier_en_cours(self) -> None:
        motif = self.etat_terminal()
        if motif is not None:
            raise EpisodeTermine(f"épisode terminé ({motif}) : aucune action n'est due (§H8.3).")
