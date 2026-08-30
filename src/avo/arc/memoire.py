"""Mémoire de frames sans perte, et outils d'inspection gratuits au score.

@spec docs/BACKLOG.md U18 — Rendu texte, inspection, mémoire de frames
@spec docs/SPEC_ARCAGI3.md §A4.3 (mémoire sans perte, `inspect`, `read_pixels`,
      `diff`), §A4.2 (coordonnées (row, col)), §A4.4 (outils purs)
@spec docs/SPEC_ARCAGI3.md §A1.2 (l'inspection ne coûte aucune action)

Mécanisme repris de VISTA : **toute** frame reçue est conservée, décision comme
transitoire, et l'agent décide seul de ce qu'il veut revoir. C'est ce qui remplace la
mémoire implicite du contexte, laquelle est compressée et de portée limitée : ici
rien ne se perd, et rien ne revient sans que l'agent l'ait demandé.

Ces outils ne coûtent aucune action au score (§A1.2) : les employer est gratuit, ne
pas les employer ne rapporte rien.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from avo.arc.rendu import COTE, Grille, rendre_grille, valider_grille

#: Nombre maximal de cellules listées par un `diff` (§A4.3). Au-delà, le compte suffit :
#: une liste de plusieurs milliers de cellules noierait l'information et le budget.
DIFF_CELLULES_MAX: Final = 64

#: Nombre maximal de vues par appel à `inspect` (§A4.3).
VUES_MAX: Final = 4

Region = tuple[int, int, int, int]


class RegionInvalide(ValueError):
    """Région hors grille ou mal ordonnée."""


class FrameInconnue(LookupError):
    """Aucune frame ne correspond au tour et à l'index demandés."""


def valider_region(region: Region) -> Region:
    """Vérifie une région (ligne0, colonne0, ligne1, colonne1), bornes incluses."""
    ligne0, colonne0, ligne1, colonne1 = region
    for nom, valeur in (
        ("ligne0", ligne0),
        ("colonne0", colonne0),
        ("ligne1", ligne1),
        ("colonne1", colonne1),
    ):
        if not 0 <= valeur < COTE:
            raise RegionInvalide(f"{nom}={valeur} hors de la grille (0 à {COTE - 1})")
    if ligne1 < ligne0 or colonne1 < colonne0:
        raise RegionInvalide(
            f"région mal ordonnée : ({ligne0},{colonne0}) doit précéder ({ligne1},{colonne1})"
        )
    return region


def rendre_region(grille: Sequence[Sequence[int]], region: Region) -> str:
    """Découpe rendue avec les index de lignes et de colonnes en marge (§A4.3).

    Les marges sont indispensables : sans elles, l'agent ne peut pas rattacher ce
    qu'il voit aux coordonnées qu'il devra employer pour cliquer.
    """
    ligne0, colonne0, ligne1, colonne1 = valider_region(region)
    largeur = max(len(str(valeur)) for ligne in grille for valeur in ligne)
    marge = len(str(COTE - 1))
    entete = " " * (marge + 1) + " ".join(
        str(colonne).rjust(largeur) for colonne in range(colonne0, colonne1 + 1)
    )
    lignes = [entete]
    for ligne in range(ligne0, ligne1 + 1):
        cellules = " ".join(
            str(grille[ligne][colonne]).rjust(largeur) for colonne in range(colonne0, colonne1 + 1)
        )
        lignes.append(f"{str(ligne).rjust(marge)} {cellules}")
    return "\n".join(lignes)


@dataclass(frozen=True)
class FrameMemorisee:
    """Une frame conservée, avec de quoi la retrouver."""

    tour: int
    index: int
    type: str
    grille: Grille


@dataclass
class MemoireFrames:
    """Toutes les frames reçues, sans perte (§A4.3)."""

    frames: list[FrameMemorisee] = field(default_factory=list)
    tour_courant: int = 0

    def enregistrer_tour(self, frames: Sequence[tuple[str, Sequence[Sequence[int]]]]) -> int:
        """Conserve les frames d'un tour et rend son numéro."""
        self.tour_courant += 1
        for index, (type_frame, grille) in enumerate(frames):
            valider_grille(grille)
            self.frames.append(
                FrameMemorisee(
                    tour=self.tour_courant,
                    index=index,
                    type=str(type_frame),
                    grille=[list(ligne) for ligne in grille],
                )
            )
        return self.tour_courant

    # ------------------------------------------------------------------ accès
    def frame(self, tour: int | None = None, index: int | None = None) -> FrameMemorisee:
        """Frame d'un tour. Sans index, la dernière du tour ; sans tour, la plus récente."""
        if not self.frames:
            raise FrameInconnue("aucune frame en mémoire")
        cible_tour = self.tour_courant if tour is None else tour
        candidates = [frame for frame in self.frames if frame.tour == cible_tour]
        if not candidates:
            tours = sorted({frame.tour for frame in self.frames})
            raise FrameInconnue(f"tour {cible_tour} inconnu ; tours disponibles : {tours}")
        if index is None:
            return candidates[-1]
        for frame in candidates:
            if frame.index == index:
                return frame
        raise FrameInconnue(
            f"tour {cible_tour} : index {index} inconnu ; "
            f"index disponibles : {[frame.index for frame in candidates]}"
        )

    def frames_de_decision(self) -> list[FrameMemorisee]:
        """Frames depuis lesquelles agir était possible (§A2.2)."""
        agissables = {"decision", "reset_init", "level_init"}
        return [frame for frame in self.frames if frame.type in agissables]

    # ------------------------------------------------------------------ outils
    def inspect(
        self,
        tour: int | None = None,
        frame: int | None = None,
        region: Region | None = None,
        vues: Sequence[Region] | None = None,
    ) -> str:
        """Réaffiche une frame passée ou des découpes (§A4.3). Gratuit au score."""
        memorisee = self.frame(tour, frame)
        entete = f"tour {memorisee.tour}, frame {memorisee.index} ({memorisee.type})"
        regions = list(vues) if vues else ([region] if region else [])
        if not regions:
            return f"{entete}\n{rendre_grille(memorisee.grille)}"
        if len(regions) > VUES_MAX:
            raise RegionInvalide(f"{len(regions)} vues demandées, {VUES_MAX} au plus")
        morceaux = [entete]
        for vue in regions:
            morceaux.append(f"\nrégion {vue}\n{rendre_region(memorisee.grille, vue)}")
        return "\n".join(morceaux)

    def read_pixels(self, region: Region, tour: int | None = None, frame: int | None = None) -> str:
        """Valeurs exactes d'une région (§A4.3). Gratuit au score."""
        memorisee = self.frame(tour, frame)
        ligne0, colonne0, ligne1, colonne1 = valider_region(region)
        valeurs = [
            f"({ligne},{colonne})={memorisee.grille[ligne][colonne]}"
            for ligne in range(ligne0, ligne1 + 1)
            for colonne in range(colonne0, colonne1 + 1)
        ]
        return " ".join(valeurs)

    def diff(self, tour_a: int, tour_b: int) -> str:
        """Cellules qui changent entre deux frames de décision (§A4.3).

        La liste est bornée : au-delà, le compte suffit. Une énumération de milliers
        de cellules noierait l'information utile et le budget de contexte avec.
        """
        avant = self.frame(tour_a).grille
        apres = self.frame(tour_b).grille
        changements = [
            (ligne, colonne, avant[ligne][colonne], apres[ligne][colonne])
            for ligne in range(COTE)
            for colonne in range(COTE)
            if avant[ligne][colonne] != apres[ligne][colonne]
        ]
        if not changements:
            return f"tours {tour_a} → {tour_b} : aucune cellule modifiée"
        listees = changements[:DIFF_CELLULES_MAX]
        details = " ".join(
            f"({ligne},{colonne}):{ancien}→{nouveau}" for ligne, colonne, ancien, nouveau in listees
        )
        suite = (
            ""
            if len(changements) == len(listees)
            else f" … et {len(changements) - len(listees)} autres"
        )
        return (
            f"tours {tour_a} → {tour_b} : {len(changements)} cellules modifiées\n{details}{suite}"
        )

    def resume(self) -> dict[str, Any]:
        """Résumé journalisable : des compteurs, aucune grille (§H4.6)."""
        return {
            "tours": self.tour_courant,
            "frames": len(self.frames),
            "frames_de_decision": len(self.frames_de_decision()),
        }


# --------------------------------------------------------------------- outils
# Schémas de la surface d'outil (§A4.3, §H7.3). Comme pour les notes, le domaine
# lève et la surface convertit en texte rendu au modèle (§H7.4).

SCHEMA_INSPECT: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "inspect",
        "description": (
            "Réaffiche une frame déjà reçue, ou une découpe avec les index en marge. "
            "Gratuit : n'entre pas dans le compte des actions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "turn": {"type": "integer"},
                "frame": {"type": "integer"},
                "region": {"type": "array", "items": {"type": "integer"}},
            },
        },
    },
}

SCHEMA_READ_PIXELS: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "read_pixels",
        "description": (
            "Valeurs exactes des cellules d'une région (ligne0, colonne0, ligne1, "
            "colonne1). Gratuit : n'entre pas dans le compte des actions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "region": {"type": "array", "items": {"type": "integer"}},
                "turn": {"type": "integer"},
                "frame": {"type": "integer"},
            },
            "required": ["region"],
        },
    },
}

SCHEMA_DIFF: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "diff",
        "description": (
            "Cellules qui changent entre deux tours. Gratuit : n'entre pas dans le "
            "compte des actions."
        ),
        "parameters": {
            "type": "object",
            "properties": {"turn_a": {"type": "integer"}, "turn_b": {"type": "integer"}},
            "required": ["turn_a", "turn_b"],
        },
    },
}


def _region(brut: Any) -> Region:
    if not isinstance(brut, list | tuple) or len(brut) != 4:
        raise RegionInvalide("région attendue sous la forme [ligne0, colonne0, ligne1, colonne1]")
    return (int(brut[0]), int(brut[1]), int(brut[2]), int(brut[3]))


def outil_inspect(
    memoire: MemoireFrames,
    turn: int | None = None,
    frame: int | None = None,
    region: Any = None,
) -> str:
    """Outil `inspect` (§A4.3). Rend le texte, ou une erreur exploitable (§H7.4)."""
    try:
        return memoire.inspect(turn, frame, _region(region) if region else None)
    except (RegionInvalide, FrameInconnue) as erreur:
        return f"error: {type(erreur).__name__}: {erreur}"


def outil_read_pixels(
    memoire: MemoireFrames, region: Any, turn: int | None = None, frame: int | None = None
) -> str:
    """Outil `read_pixels` (§A4.3)."""
    try:
        return memoire.read_pixels(_region(region), turn, frame)
    except (RegionInvalide, FrameInconnue) as erreur:
        return f"error: {type(erreur).__name__}: {erreur}"


def outil_diff(memoire: MemoireFrames, turn_a: int, turn_b: int) -> str:
    """Outil `diff` (§A4.3)."""
    try:
        return memoire.diff(int(turn_a), int(turn_b))
    except FrameInconnue as erreur:
        return f"error: {type(erreur).__name__}: {erreur}"
