"""Notes persistantes de l'agent : `GUIDE.md` et `WORKING.md`.

@spec docs/BACKLOG.md U11 — Notes persistantes
@spec docs/SPEC_HARNAIS.md §H6.2 (mécanisme VISTA repris tel quel), §H7.3 (outils
      `note_read` / `note_write`), §H7.4 (erreurs d'outil rendues au modèle),
      §H5.3 (injection en tête de segment frais)
@spec docs/BACKLOG.md U30 — compteur d'écritures monotone (§H16.4 : la garde de
      persistance constate une écriture, jamais une différence de contenu)

Mécanisme repris de VISTA : deux notes seulement, aux rôles distincts. `GUIDE`
porte la compréhension durable, transverse aux niveaux ; `WORKING` est le brouillon
du niveau courant. Ce sont elles qui **survivent** à une continuation, quand le
contexte conversationnel, lui, est renouvelé — c'est donc là que l'agent doit écrire
ce qu'il ne veut pas oublier.

Deux noms, pas trois : la contrainte est délibérée. Un espace de notes libre se
transforme en système de fichiers parallèle dont plus rien ne garantit la relecture.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

#: Les deux seuls noms de note acceptés (§H7.3).
GUIDE: Final = "GUIDE"
WORKING: Final = "WORKING"
NOMS_AUTORISES: Final = (GUIDE, WORKING)

#: Rôle de chaque note, rappelé au modèle dans le bloc injecté (§H6.2).
ROLES: Final = {
    GUIDE: "compréhension durable du jeu, transverse aux niveaux",
    WORKING: "brouillon du niveau courant",
}


class NomDeNoteInvalide(ValueError):
    """Nom de note hors des deux autorisés (§H7.3)."""


class Notes:
    """Accès aux notes persistantes d'un run, dans `runs/<id>/notes/`."""

    def __init__(self, dossier: Path) -> None:
        self.dossier = dossier
        self.dossier.mkdir(parents=True, exist_ok=True)
        #: Écritures par note depuis l'ouverture (§H16.4). Monotone et en mémoire :
        #: la garde de persistance compare des compteurs, jamais des contenus — une
        #: réécriture à l'identique est une confirmation explicite, elle compte.
        self._ecritures: dict[str, int] = dict.fromkeys(NOMS_AUTORISES, 0)

    @staticmethod
    def valider(nom: str) -> str:
        """Rend le nom normalisé, ou lève en nommant les noms acceptés."""
        normalise = nom.strip().upper().removesuffix(".MD")
        if normalise not in NOMS_AUTORISES:
            raise NomDeNoteInvalide(
                f"note « {nom} » inconnue : seuls {' et '.join(NOMS_AUTORISES)} existent "
                "(docs/SPEC_HARNAIS.md §H7.3)."
            )
        return normalise

    def chemin(self, nom: str) -> Path:
        return self.dossier / f"{self.valider(nom)}.md"

    def lire(self, nom: str) -> str:
        """Contenu de la note. Une note jamais écrite est vide, pas absente."""
        chemin = self.chemin(nom)
        return chemin.read_text(encoding="utf-8") if chemin.exists() else ""

    def ecrire(self, nom: str, contenu: str) -> None:
        """Remplace le contenu d'une note.

        Une note se réécrit entièrement, à la différence du transcript qui, lui, est
        append-only : c'est précisément son rôle de pouvoir être révisée quand la
        compréhension change (§H6.2).
        """
        normalise = self.valider(nom)
        self.chemin(normalise).write_text(contenu, encoding="utf-8")
        self._ecritures[normalise] += 1

    def ecritures(self, nom: str) -> int:
        """Nombre d'écritures de la note depuis l'ouverture (§H16.4)."""
        return self._ecritures[self.valider(nom)]

    def vider(self, nom: str) -> None:
        """Efface une note. Employé sur `WORKING` à un changement de niveau."""
        self.ecrire(nom, "")

    def toutes(self) -> dict[str, str]:
        return {nom: self.lire(nom) for nom in NOMS_AUTORISES}

    def pour_segment_frais(self) -> str:
        """Bloc injecté en tête d'un segment frais (§H5.3, §H6.2).

        Les notes vides sont annoncées comme telles plutôt qu'omises : leur absence
        est une information pour l'agent, qui saura qu'il n'a rien consigné.
        """
        morceaux: list[str] = ["Tes notes persistantes :"]
        for nom in NOMS_AUTORISES:
            contenu = self.lire(nom).strip()
            morceaux.append(f"\n## {nom}.md — {ROLES[nom]}\n")
            morceaux.append(contenu if contenu else "(vide)")
        return "\n".join(morceaux)

    def resume(self) -> dict[str, int]:
        """Résumé journalisable : des tailles, aucun contenu (§H4.6)."""
        return {f"{nom.lower()}_caracteres": len(self.lire(nom)) for nom in NOMS_AUTORISES}


# --------------------------------------------------------------------- outils
# Surface d'outil (§H7.3). Le domaine lève, la surface d'outil convertit en texte :
# une erreur d'outil est rendue au modèle pour qu'il se corrige, jamais propagée
# comme une exception qui interromprait le run (§H7.4).

SCHEMA_NOTE_READ: Final[dict[str, Any]] = {
    "type": "function",
    "function": {
        "name": "note_read",
        "description": "Lit une note persistante. Noms acceptés : GUIDE, WORKING.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string", "enum": list(NOMS_AUTORISES)}},
            "required": ["name"],
        },
    },
}

SCHEMA_NOTE_WRITE: Final[dict[str, Any]] = {
    "type": "function",
    "function": {
        "name": "note_write",
        "description": (
            "Remplace le contenu d'une note persistante. Noms acceptés : GUIDE, WORKING. "
            "Les notes survivent au renouvellement du contexte."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "enum": list(NOMS_AUTORISES)},
                "content": {"type": "string"},
            },
            "required": ["name", "content"],
        },
    },
}


def note_read(notes: Notes, name: str) -> str:
    """Outil `note_read` (§H7.3). Rend le contenu, ou un texte d'erreur (§H7.4)."""
    try:
        contenu = notes.lire(name)
    except NomDeNoteInvalide as erreur:
        return f"error: {erreur}"
    return contenu if contenu else "(note vide)"


def note_write(notes: Notes, name: str, content: str) -> str:
    """Outil `note_write` (§H7.3). Confirme l'écriture, ou rend un texte d'erreur."""
    try:
        notes.ecrire(name, content)
    except NomDeNoteInvalide as erreur:
        return f"error: {erreur}"
    return f"note {Notes.valider(name)}.md écrite ({len(content)} caractères)"
