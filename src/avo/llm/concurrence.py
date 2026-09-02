"""Limitation de concurrence des requêtes LLM par endpoint (§H4.9).

@spec docs/BACKLOG.md U32 — Limitation de concurrence des requêtes LLM par endpoint
@spec docs/SPEC_HARNAIS.md §H4.9 (jetons de fichiers, attente bornée, jeton périmé,
      activation live uniquement), §H3.1 (AVO_LLM_MAX_CONCURRENT, AVO_LLM_SLOTS_DIR)

L'endpoint public tolère un nombre borné de requêtes simultanées (instruction du
responsable, 2026-09-02 : au plus 3, sinon HTTP 500 ou timeouts). Le limiteur
impose ce plafond côté client par des JETONS DE FICHIERS : un répertoire par
endpoint contient au plus `plafond` fichiers `slot-<n>` ; réclamer un jeton est
une création exclusive (`O_CREAT|O_EXCL`), donc atomique pour tout ce qui partage
le répertoire — fils d'un processus, processus d'un même hôte, conteneurs montés
sur le même volume. Aucun jeton libre : l'appelant PATIENTE (scrutation courte
avec jitter), au plus `timeout_s` cumulées, puis une erreur explicite nomme le
répertoire et les occupants — jamais un blocage silencieux.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import socket
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

_journal = logging.getLogger("avo.llm")

#: Marge ajoutée à `timeout_s` avant de réputer un jeton abandonné (§H4.9) : plus
#: long que la plus longue requête légitime, pour ne jamais voler un jeton vivant.
MARGE_PEREMPTION_S = 60.0

#: Intervalle de base entre deux scrutations d'un jeton libre, en secondes. Le
#: jitter (±50 % via `alea`) désynchronise les processus qui attendent ensemble.
INTERVALLE_SCRUTATION_S = 0.5


class PatienceEpuisee(RuntimeError):
    """Aucun jeton libéré dans le délai imparti : l'erreur nomme l'état observé."""


@dataclass(frozen=True)
class LimiteurConcurrence:
    """Sémaphore inter-processus à jetons de fichiers (§H4.9).

    `dormir` et `alea` sont injectables comme pour les retries (§H4.5) : les
    tests éprouvent l'attente sans attendre réellement.
    """

    dossier: Path
    plafond: int
    timeout_s: float
    dormir: Callable[[float], None] = time.sleep
    alea: Callable[[], float] = random.random

    @contextmanager
    def jeton(self) -> Iterator[None]:
        """Tient un jeton le temps du bloc ; plafond ≤ 0 = limiteur désactivé."""
        if self.plafond <= 0:
            yield
            return
        chemin = self._acquerir()
        try:
            yield
        finally:
            chemin.unlink(missing_ok=True)

    def _acquerir(self) -> Path:
        self.dossier.mkdir(parents=True, exist_ok=True)
        attendu = 0.0
        premiere_attente = True
        while True:
            chemin = self._reclamer_un_jeton()
            if chemin is not None:
                return chemin
            if attendu >= self.timeout_s:
                raise PatienceEpuisee(
                    f"aucun jeton LLM libéré après {round(attendu)} s d'attente — "
                    f"plafond {self.plafond}, répertoire {self.dossier}, "
                    f"occupants : {self._occupants()}"
                )
            if premiere_attente:
                _journal.info(
                    "requête LLM en file d'attente",
                    extra={"plafond": self.plafond, "dossier": str(self.dossier)},
                )
                premiere_attente = False
            delai = INTERVALLE_SCRUTATION_S * (0.5 + self.alea())
            self.dormir(delai)
            attendu += delai

    def _reclamer_un_jeton(self) -> Path | None:
        """Essaie chaque slot une fois ; reprend au passage un jeton périmé."""
        for numero in range(self.plafond):
            chemin = self.dossier / f"slot-{numero}"
            if self._creer_exclusif(chemin):
                return chemin
            self._reprendre_si_perime(chemin)
            if self._creer_exclusif(chemin):
                return chemin
        return None

    def _creer_exclusif(self, chemin: Path) -> bool:
        try:
            descripteur = os.open(chemin, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        with os.fdopen(descripteur, "w") as fichier:
            json.dump(
                {"pid": os.getpid(), "hote": socket.gethostname(), "depuis": time.time()},
                fichier,
            )
        return True

    def _reprendre_si_perime(self, chemin: Path) -> None:
        """Supprime un jeton dont l'occupant est réputé mort (§H4.9).

        La course résiduelle entre deux repreneurs peut brièvement dépasser le
        plafond d'une unité : acceptée et documentée par la spécification.
        """
        try:
            age = time.time() - chemin.stat().st_mtime
        except FileNotFoundError:
            return
        if age > self.timeout_s + MARGE_PEREMPTION_S:
            _journal.info(
                "jeton LLM périmé repris",
                extra={"jeton": chemin.name, "age_s": round(age)},
            )
            chemin.unlink(missing_ok=True)

    def _occupants(self) -> str:
        contenus: list[str] = []
        for jeton in sorted(self.dossier.glob("slot-*")):
            try:
                contenus.append(f"{jeton.name}={jeton.read_text().strip()}")
            except OSError:
                contenus.append(f"{jeton.name}=<illisible>")
        return "; ".join(contenus) or "<aucun>"


def dossier_endpoint(racine: Path, hote: str) -> Path:
    """Sous-répertoire des jetons propre à UN endpoint (§H4.9) : le plafond est
    par endpoint, jamais global à des serveurs distincts."""
    empreinte = hashlib.sha256(hote.encode()).hexdigest()[:12]
    return racine / empreinte
