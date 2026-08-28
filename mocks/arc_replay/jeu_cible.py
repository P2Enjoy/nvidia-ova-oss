"""Jeu synthétique `cible` : déterministe, en forme fermée, éprouvable exactement.

@spec docs/BACKLOG.md U16
@spec docs/SPEC_ARCAGI3.md §A3.2 (spécification fermée du jeu), §A1.1 (grilles 64×64,
      frames transitoires), §A1.2 (protocole de score : RESET, complétion, game over)

Ce jeu n'imite aucun jeu officiel ARC-AGI-3 : c'est une fixture destinée à éprouver
la mécanique du harnais. Sa vertu est d'être **en forme fermée** — la baseline
humaine de chaque niveau se calcule, donc le RHAE attendu d'une partie parfaite est
connu à l'avance et se vérifie exactement dans les tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

#: Dimensions et palette (§A1.1).
COTE: Final = 64
FOND: Final = 0
BORDURE: Final = 5
CIBLE: Final = 3
CURSEUR: Final = 8
CURSEUR_TRANSITOIRE: Final = 9

#: Nombre de niveaux par défaut (§A3.2).
NIVEAUX: Final = 3

#: Position initiale du curseur (§A3.2).
DEPART: Final = (32, 32)

#: Clics hors cible tolérés dans une tentative avant la perte (§A3.2).
CLICS_RATES_MAX: Final = 3

#: Actions de déplacement, dans l'ordre du contrat (§A3.2).
DEPLACEMENTS: Final = {
    "ACTION1": (-1, 0),
    "ACTION2": (1, 0),
    "ACTION3": (0, -1),
    "ACTION4": (0, 1),
}
CLIC: Final = "ACTION6"
RESET: Final = "RESET"

Grille = list[list[int]]


class EtatPartie(StrEnum):
    """États rendus par le protocole (§A1.1)."""

    NON_COMMENCEE = "NOT_PLAYED"
    EN_COURS = "NOT_FINISHED"
    GAGNEE = "WIN"
    PERDUE = "GAME_OVER"


def coin_cible(niveau: int) -> tuple[int, int]:
    """Coin haut-gauche de la cible 2×2 du niveau (§A3.2), 1-indexé."""
    return ((7 * niveau) % 60 + 2, (13 * niveau) % 60 + 2)


def cellules_cible(niveau: int) -> set[tuple[int, int]]:
    ligne, colonne = coin_cible(niveau)
    return {(ligne + dl, colonne + dc) for dl in (0, 1) for dc in (0, 1)}


def baseline_humaine(niveau: int) -> int:
    """Baseline du niveau : distance de Manhattan initiale, plus le clic (§A3.2).

    En forme fermée : c'est exactement le nombre d'actions d'une partie parfaite, ce
    qui rend le RHAE attendu calculable sans jouer.
    """
    ligne, colonne = DEPART
    return min(abs(ligne - cl) + abs(colonne - cc) for cl, cc in cellules_cible(niveau)) + 1


@dataclass
class Resultat:
    """Ce qu'une commande rend : frames, état, score, actions disponibles (§A1.3)."""

    frames: list[Grille]
    etat: EtatPartie
    score: int
    actions_disponibles: list[str]
    actions_niveau: int
    niveau: int


@dataclass
class JeuCible:
    """Moteur du jeu `cible`. Déterministe : mêmes actions, mêmes frames (§A1.1)."""

    niveaux: int = NIVEAUX
    niveau: int = 1
    curseur: tuple[int, int] = DEPART
    etat: EtatPartie = EtatPartie.NON_COMMENCEE
    score: int = 0
    clics_rates: int = 0
    actions_niveau: int = 0
    actions_totales: int = 0
    actions_par_niveau: dict[int, int] = field(default_factory=dict)

    # ------------------------------------------------------------------- rendu
    def _grille(self, curseur_transitoire: bool = False) -> Grille:
        grille: Grille = [[FOND] * COTE for _ in range(COTE)]
        for index in range(COTE):
            grille[0][index] = BORDURE
            grille[COTE - 1][index] = BORDURE
            grille[index][0] = BORDURE
            grille[index][COTE - 1] = BORDURE
        for ligne, colonne in cellules_cible(self.niveau):
            grille[ligne][colonne] = CIBLE
        ligne, colonne = self.curseur
        grille[ligne][colonne] = CURSEUR_TRANSITOIRE if curseur_transitoire else CURSEUR
        return grille

    def _actions_disponibles(self) -> list[str]:
        if self.etat in (EtatPartie.GAGNEE, EtatPartie.PERDUE):
            return [RESET]
        return [*DEPLACEMENTS, CLIC, RESET]

    def _resultat(self, frames: list[Grille]) -> Resultat:
        return Resultat(
            frames=frames,
            etat=self.etat,
            score=self.score,
            actions_disponibles=self._actions_disponibles(),
            actions_niveau=self.actions_niveau,
            niveau=self.niveau,
        )

    # -------------------------------------------------------------- protocole
    def reset(self) -> Resultat:
        """`RESET` : gratuit s'il crée la partie, coûte une action sinon (§A1.2)."""
        creation = self.etat is EtatPartie.NON_COMMENCEE
        if not creation:
            self.actions_niveau += 1
            self.actions_totales += 1
        if self.etat is EtatPartie.GAGNEE:
            # Une partie gagnée ne se rejoue pas : le RESET la laisse gagnée.
            return self._resultat([self._grille()])
        self.curseur = DEPART
        self.clics_rates = 0
        self.etat = EtatPartie.EN_COURS
        return self._resultat([self._grille()])

    def jouer(self, action: str, ligne: int | None = None, colonne: int | None = None) -> Resultat:
        """Joue une action ordinaire. Deux frames : transitoire puis décision (§A3.2)."""
        if self.etat is not EtatPartie.EN_COURS:
            raise ValueError(
                f"action « {action} » impossible dans l'état {self.etat.value} : "
                "seul RESET est disponible."
            )
        self.actions_niveau += 1
        self.actions_totales += 1

        if action in DEPLACEMENTS:
            return self._deplacer(action)
        if action == CLIC:
            if ligne is None or colonne is None:
                raise ValueError(f"{CLIC} exige des coordonnées (ligne, colonne).")
            return self._cliquer(ligne, colonne)
        raise ValueError(f"action inconnue : « {action} »")

    def _deplacer(self, action: str) -> Resultat:
        dl, dc = DEPLACEMENTS[action]
        ligne, colonne = self.curseur
        cible_ligne, cible_colonne = ligne + dl, colonne + dc
        # La bordure bloque : le curseur reste sur place, mais l'action est comptée.
        if 1 <= cible_ligne <= COTE - 2 and 1 <= cible_colonne <= COTE - 2:
            self.curseur = (cible_ligne, cible_colonne)
        transitoire = self._grille(curseur_transitoire=True)
        return self._resultat([transitoire, self._grille()])

    def _cliquer(self, ligne: int, colonne: int) -> Resultat:
        transitoire = self._grille(curseur_transitoire=True)
        reussi = (ligne, colonne) == self.curseur and self.curseur in cellules_cible(self.niveau)
        if reussi:
            self.actions_par_niveau[self.niveau] = self.actions_niveau
            self.score += 1
            if self.niveau >= self.niveaux:
                self.etat = EtatPartie.GAGNEE
            else:
                self.niveau += 1
                self.curseur = DEPART
                self.clics_rates = 0
                self.actions_niveau = 0
            return self._resultat([transitoire, self._grille()])

        self.clics_rates += 1
        if self.clics_rates >= CLICS_RATES_MAX:
            self.etat = EtatPartie.PERDUE
        return self._resultat([transitoire, self._grille()])

    # ---------------------------------------------------------------- lectures
    def actions_disponibles_test(self) -> list[str]:
        """Actions offertes dans l'état courant. Lecture pure, employée par les tests."""
        return self._actions_disponibles()

    def baselines(self) -> list[int]:
        """Baselines humaines de tous les niveaux, pour `/api/games` (§A6.2)."""
        return [baseline_humaine(niveau) for niveau in range(1, self.niveaux + 1)]

    def chemin_optimal(self) -> list[tuple[str, int | None, int | None]]:
        """Suite d'actions parfaite du niveau courant. Sert aux preuves exactes.

        Le harnais ne l'emploie jamais : c'est un outil de test, qui permet de
        vérifier qu'une partie parfaite consomme exactement la baseline.
        """
        ligne, colonne = self.curseur
        cible = min(
            cellules_cible(self.niveau),
            key=lambda cellule: abs(ligne - cellule[0]) + abs(colonne - cellule[1]),
        )
        actions: list[tuple[str, int | None, int | None]] = []
        while ligne != cible[0]:
            pas = 1 if cible[0] > ligne else -1
            actions.append(("ACTION2" if pas > 0 else "ACTION1", None, None))
            ligne += pas
        while colonne != cible[1]:
            pas = 1 if cible[1] > colonne else -1
            actions.append(("ACTION4" if pas > 0 else "ACTION3", None, None))
            colonne += pas
        actions.append((CLIC, cible[0], cible[1]))
        return actions
