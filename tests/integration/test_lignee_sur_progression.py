"""La lignée face à une progression réelle de la boucle.

@verifies docs/BACKLOG.md U14 — Lignée et fonction de score
@verifies docs/SPEC_HARNAIS.md §H9.1 (correct ∧ ≥ meilleur), §H9.2 (scorer ARC),
          §H9.3 (dépôt jetable dans le workspace du run), §H6.1 (arborescence)
@verifies CLAUDE.md §13 (le dépôt du projet n'est jamais touché)

La lignée est ouverte là où elle vivra réellement — `runs/<id>/lineage/` — et reçoit
les bilans que la boucle produit, y compris une régression qui doit être refusée.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from avo.config import Config, Mode, charger
from avo.lineage import Decision, Lignee, ScorerARC
from avo.memory.notes import GUIDE, WORKING, Notes, note_write
from avo.memory.workspace import Workspace

RACINE_PROJET = Path(__file__).resolve().parents[2]


@dataclass
class _Bilan:
    """Forme du bilan rendu par la boucle (§H8.3)."""

    niveaux_completes: int
    actions_jeu: int


def _config() -> Config:
    return charger(Mode.REJEU, env={}, racine=Path("/inexistant"))


class TestLigneeDansLeWorkspace(unittest.TestCase):
    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.espace = Workspace.ouvrir(_config(), "run-lignee", racine=Path(self._dossier.name))
        self.notes = Notes(self.espace.notes)
        self.lignee = Lignee.ouvrir(self.espace.chemin / "lineage", ScorerARC())

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def _proposer(self, bilan: _Bilan) -> Decision:
        return self.lignee.proposer(bilan, self.notes.toutes(), {"run_id": self.espace.run_id})

    def test_la_lignee_vit_dans_le_workspace_du_run(self) -> None:
        self.assertTrue((self.espace.chemin / "lineage" / ".git").is_dir())
        self.assertIn("lineage/.git", "\n".join(self.espace.arborescence()))

    def test_trois_progressions_donnent_trois_versions_scorees(self) -> None:
        """La preuve demandée : trois progressions, trois commits, scores exacts."""
        note_write(self.notes, GUIDE, "niveau 1 : cliquer termine")
        self.assertTrue(self._proposer(_Bilan(1, 20)).acceptee)
        note_write(self.notes, GUIDE, "niveau 2 : la même règle transfère")
        self.assertTrue(self._proposer(_Bilan(2, 45)).acceptee)
        note_write(self.notes, WORKING, "niveau 3 en cours")
        self.assertTrue(self._proposer(_Bilan(3, 70)).acceptee)

        self.assertEqual(self.lignee.nombre_de_versions(), 3)
        self.assertEqual(
            self.lignee.versions(),
            ["v1 score=[1, -20]", "v2 score=[2, -45]", "v3 score=[3, -70]"],
        )
        self.assertEqual(self.lignee.meilleur_score, (3, -70))

    def test_une_regression_intercalee_n_entre_pas_dans_la_lignee(self) -> None:
        self._proposer(_Bilan(2, 30))
        refus = self._proposer(_Bilan(1, 10))
        self.assertFalse(refus.acceptee)
        self.assertEqual(self.lignee.nombre_de_versions(), 1)
        self.assertTrue(self._proposer(_Bilan(3, 60)).acceptee)
        self.assertEqual(self.lignee.nombre_de_versions(), 2)

    def test_un_run_sans_progression_ne_commite_rien(self) -> None:
        """« Correct » = progression constatée par l'environnement (§H9.2)."""
        for actions in (10, 50, 200):
            self.assertFalse(self._proposer(_Bilan(0, actions)).acceptee)
        self.assertEqual(self.lignee.nombre_de_versions(), 0)

    def test_l_etat_de_connaissance_committe_est_bien_celui_du_moment(self) -> None:
        note_write(self.notes, GUIDE, "compréhension au niveau 1")
        self._proposer(_Bilan(1, 20))
        premier = (self.lignee.chemin / "GUIDE.md").read_text(encoding="utf-8")
        note_write(self.notes, GUIDE, "compréhension révisée au niveau 2")
        self._proposer(_Bilan(2, 40))
        second = (self.lignee.chemin / "GUIDE.md").read_text(encoding="utf-8")
        self.assertEqual(premier, "compréhension au niveau 1")
        self.assertEqual(second, "compréhension révisée au niveau 2")
        self.assertEqual(self.lignee.nombre_de_versions(), 2)

    def test_le_depot_du_projet_reste_intact(self) -> None:
        """CLAUDE.md §13 : rien de ce que fait la lignée n'atteint le projet."""
        avant = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=RACINE_PROJET,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for niveaux in (1, 2, 3):
            self._proposer(_Bilan(niveaux, niveaux * 20))
        apres = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=RACINE_PROJET,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        self.assertEqual(avant, apres, "le dépôt du projet a été modifié par la lignée")

    def test_les_decisions_alimentent_les_metriques_du_run(self) -> None:
        self._proposer(_Bilan(1, 20))
        self._proposer(_Bilan(0, 30))
        self.espace.metrique("lignee", lignee=self.lignee.resume())
        derniere = self.espace.lire_metriques()[-1]
        self.assertEqual(derniere["lignee"]["versions"], 1)
        self.assertEqual(derniere["lignee"]["refus"], 1)
        self.assertEqual(derniere["lignee"]["meilleur_score"], [1, -20])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
