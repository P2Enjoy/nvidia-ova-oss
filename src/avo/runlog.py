"""Journalisation structurée du harnais : JSON une ligne, corrélée, sans secret.

@spec docs/BACKLOG.md U8 — Comptabilité, journalisation, workspace de run
@spec docs/SPEC_HARNAIS.md §H11.1 (logs JSON, niveaux, identifiant de run),
      §H4.6 (aucun secret journalisé)

La garantie « aucun secret » ne repose pas sur la discipline des appelants : un
filtre remplace les valeurs sensibles dans le message ET dans les champs
supplémentaires, juste avant écriture. Même un `logger.info(cle)` maladroit ne peut
donc pas faire fuiter la clé.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any, TextIO

#: Remplacement écrit à la place d'une valeur sensible.
MASQUE = "<masqué>"

#: En dessous de cette longueur, une valeur n'est pas traitée comme un secret :
#: masquer une chaîne de deux caractères rendrait les journaux illisibles sans rien
#: protéger d'utile.
LONGUEUR_SECRET_MIN = 8

#: Champs propres à `logging.LogRecord`, exclus des champs supplémentaires.
_CHAMPS_STANDARD = frozenset(vars(logging.makeLogRecord({})))


class FiltreSecrets(logging.Filter):
    """Remplace toute valeur sensible par `MASQUE` avant écriture (§H4.6)."""

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        super().__init__()
        self.secrets = tuple(
            secret for secret in secrets if secret and len(secret) >= LONGUEUR_SECRET_MIN
        )

    def _masquer(self, valeur: Any) -> Any:
        if isinstance(valeur, str):
            for secret in self.secrets:
                valeur = valeur.replace(secret, MASQUE)
            return valeur
        if isinstance(valeur, dict):
            return {cle: self._masquer(sous) for cle, sous in valeur.items()}
        if isinstance(valeur, list | tuple):
            return type(valeur)(self._masquer(sous) for sous in valeur)
        return valeur

    def filter(self, record: logging.LogRecord) -> bool:
        if not self.secrets:
            return True
        record.msg = self._masquer(record.msg)
        if record.args:
            record.args = self._masquer(record.args)
        for nom, valeur in list(vars(record).items()):
            if nom not in _CHAMPS_STANDARD:
                setattr(record, nom, self._masquer(valeur))
        return True


class FormateurJSON(logging.Formatter):
    """Formate chaque enregistrement en un objet JSON d'une seule ligne (§H11.1)."""

    def __init__(self, run_id: str | None = None) -> None:
        super().__init__()
        self.run_id = run_id

    def format(self, record: logging.LogRecord) -> str:
        charge: dict[str, Any] = {
            "horodatage": datetime.fromtimestamp(record.created, UTC).isoformat(
                timespec="milliseconds"
            ),
            "niveau": record.levelname,
            "journal": record.name,
            "message": record.getMessage(),
        }
        if self.run_id:
            charge["run_id"] = self.run_id
        for nom, valeur in vars(record).items():
            if nom not in _CHAMPS_STANDARD and nom not in charge:
                charge[nom] = valeur
        if record.exc_info:
            charge["exception"] = self.formatException(record.exc_info)
        return json.dumps(charge, ensure_ascii=False, default=str)


def configurer_journalisation(
    run_id: str | None = None,
    secrets: Sequence[str] = (),
    niveau: int = logging.INFO,
    flux: TextIO | None = None,
) -> logging.Handler:
    """Installe la journalisation JSON du harnais et rend le gestionnaire posé.

    Remplace les gestionnaires précédemment posés par le harnais : une session qui
    reconfigure ne laisse pas deux sorties concurrentes derrière elle.
    """
    racine = logging.getLogger("avo")
    for ancien in list(racine.handlers):
        racine.removeHandler(ancien)
        ancien.close()
    gestionnaire = logging.StreamHandler(flux if flux is not None else sys.stderr)
    gestionnaire.setFormatter(FormateurJSON(run_id))
    gestionnaire.addFilter(FiltreSecrets(secrets))
    racine.addHandler(gestionnaire)
    racine.setLevel(niveau)
    racine.propagate = False
    return gestionnaire


def nouveau_run_id(horloge: datetime | None = None, suffixe: str = "") -> str:
    """Identifiant de run lisible et triable : `AAAAMMJJ-HHMMSS[-suffixe]`.

    L'horloge est injectable pour rendre les tests déterministes.
    """
    instant = horloge or datetime.now(UTC)
    base = instant.strftime("%Y%m%d-%H%M%S")
    return f"{base}-{suffixe}" if suffixe else base
