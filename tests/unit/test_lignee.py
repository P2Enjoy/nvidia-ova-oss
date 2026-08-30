"""Preuves de la lignée : politique de commit, scoring, et surtout ISOLATION.

@verifies docs/BACKLOG.md U14 — Lignée et fonction de score
@verifies docs/SPEC_HARNAIS.md §H9.1 (correct ∧ ≥ meilleur), §H9.2 (scorer ARC),
          §H9.3 (dépôt jetable, isolation absolue), §H9.4 (`Scorer` branchable)
@verifies CLAUDE.md §13 (le dépôt du projet ne doit JAMAIS être touché)
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from avo.lineage import (
    IDENTITE,
    Lignee,
    LigneeNonIsolee,
    Scorer,
    ScorerARC,
    ScorerConstant,
)


@dataclass
class _Evidence:
    """Bilan minimal, tel que la boucle en produit un."""

    niveaux_completes: int
    actions_jeu: int


class _Sous(unittest.TestCase):
    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def _lignee(self, scorer: Scorer | None = None) -> Lignee:
        return Lignee.ouvrir(self.racine / "lineage", scorer or ScorerConstant())


class TestOuverture(_Sous):
    def test_le_depot_jetable_est_cree(self) -> None:
        lignee = self._lignee()
        self.assertTrue(lignee.git_dir.is_dir())
        self.assertEqual(lignee.nombre_de_versions(), 0)

    def test_l_identite_est_posee_sur_le_depot_jetable(self) -> None:
        lignee = self._lignee()
        self.assertEqual(lignee._git("config", "user.name"), IDENTITE[0])
        self.assertEqual(lignee._git("config", "user.email"), IDENTITE[1])

    def test_reouvrir_ne_reinitialise_pas(self) -> None:
        lignee = self._lignee()
        lignee.proposer([1], {"GUIDE": "acquis"})
        self.assertEqual(Lignee.ouvrir(lignee.chemin, ScorerConstant()).nombre_de_versions(), 1)


class TestIsolation(_Sous):
    """CLAUDE.md §13 : la seule faute vraiment grave de ce module."""

    def test_le_depot_de_lignee_a_son_propre_git(self) -> None:
        lignee = self._lignee()
        interne = lignee._git("rev-parse", "--absolute-git-dir")
        self.assertEqual(Path(interne).resolve(), lignee.git_dir.resolve())

    def test_sans_depot_dedie_toute_commande_est_refusee(self) -> None:
        """Sans cette garde, git remonterait l'arborescence jusqu'au dépôt du projet."""
        lignee = Lignee(chemin=self.racine / "sans_git", scorer=ScorerConstant())
        with self.assertRaises(LigneeNonIsolee) as capture:
            lignee.verifier_isolation()
        self.assertIn("CLAUDE.md", str(capture.exception))
        with self.assertRaises(LigneeNonIsolee):
            lignee.proposer([1], {"GUIDE": "x"})

    def test_le_depot_du_projet_n_est_jamais_atteint(self) -> None:
        """Preuve directe : le dépôt de lignée ignore tout des commits du projet."""
        lignee = self._lignee()
        lignee.proposer([1], {"GUIDE": "acquis"})
        self.assertEqual(lignee.nombre_de_versions(), 1)
        # Le dépôt du projet, lui, a une longue histoire : si la lignée le touchait,
        # elle en verrait les commits.
        projet = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
            check=False,
        )
        if projet.returncode == 0:
            self.assertGreater(int(projet.stdout.strip()), 1)
            self.assertNotEqual(int(projet.stdout.strip()), lignee.nombre_de_versions())

    def test_le_repertoire_courant_n_influence_pas_la_lignee(self) -> None:
        """`--git-dir` explicite : git ne cherche jamais autour de lui."""
        lignee = self._lignee()
        lignee.proposer([1], {"GUIDE": "acquis"})
        self.assertEqual(lignee.nombre_de_versions(), 1)


class TestPolitiqueDeCommit(_Sous):
    """§H9.1 : commit si correct ET au moins aussi bon."""

    def test_une_amelioration_est_committee(self) -> None:
        lignee = self._lignee()
        self.assertTrue(lignee.proposer([1], {"GUIDE": "a"}).acceptee)
        decision = lignee.proposer([2], {"GUIDE": "b"})
        self.assertTrue(decision.acceptee)
        self.assertEqual(lignee.nombre_de_versions(), 2)
        self.assertIsNotNone(decision.sha)

    def test_une_egalite_est_committee(self) -> None:
        lignee = self._lignee()
        lignee.proposer([2], {"GUIDE": "a"})
        self.assertTrue(lignee.proposer([2], {"GUIDE": "b"}).acceptee)
        self.assertEqual(lignee.nombre_de_versions(), 2)

    def test_une_regression_est_refusee(self) -> None:
        lignee = self._lignee()
        lignee.proposer([5], {"GUIDE": "a"})
        decision = lignee.proposer([3], {"GUIDE": "b"})
        self.assertFalse(decision.acceptee)
        self.assertIn("régression", decision.motif)
        self.assertEqual(lignee.nombre_de_versions(), 1)

    def test_une_version_incorrecte_est_refusee_meme_si_elle_score_haut(self) -> None:
        lignee = self._lignee(ScorerConstant(valide=False))
        decision = lignee.proposer([99], {"GUIDE": "a"})
        self.assertFalse(decision.acceptee)
        self.assertIn("incorrecte", decision.motif)
        self.assertEqual(lignee.nombre_de_versions(), 0)

    def test_un_refus_ne_deplace_pas_le_meilleur_score(self) -> None:
        lignee = self._lignee()
        lignee.proposer([5], {"GUIDE": "a"})
        lignee.proposer([1], {"GUIDE": "b"})
        self.assertEqual(lignee.meilleur_score, (5,))
        self.assertTrue(lignee.proposer([5], {"GUIDE": "c"}).acceptee)


class TestContenuCommitte(_Sous):
    def test_le_score_figure_dans_le_message_de_commit(self) -> None:
        lignee = self._lignee()
        lignee.proposer([3, -12], {"GUIDE": "a"})
        self.assertEqual(lignee.versions(), ["v1 score=[3, -12]"])

    def test_les_notes_et_la_meta_sont_committees(self) -> None:
        lignee = self._lignee()
        lignee.proposer([1], {"GUIDE": "durable", "WORKING": "brouillon"}, {"run": "r1"})
        self.assertEqual((lignee.chemin / "GUIDE.md").read_text(encoding="utf-8"), "durable")
        meta = (lignee.chemin / "meta.json").read_text(encoding="utf-8")
        self.assertIn('"run": "r1"', meta)
        self.assertIn('"score"', meta)

    def test_les_versions_sont_rendues_dans_l_ordre(self) -> None:
        lignee = self._lignee()
        for valeur in (1, 2, 3):
            lignee.proposer([valeur], {"GUIDE": str(valeur)})
        self.assertEqual(lignee.versions(), ["v1 score=[1]", "v2 score=[2]", "v3 score=[3]"])

    def test_le_resume_compte_propositions_et_refus(self) -> None:
        lignee = self._lignee()
        lignee.proposer([5], {"GUIDE": "a"})
        lignee.proposer([1], {"GUIDE": "b"})
        resume = lignee.resume()
        self.assertEqual(resume["versions"], 1)
        self.assertEqual(resume["propositions"], 2)
        self.assertEqual(resume["refus"], 1)
        self.assertEqual(resume["meilleur_score"], [5])


class TestScorerARC(unittest.TestCase):
    """§H9.2 : progresser prime, puis économiser les actions."""

    def test_progresser_prime_sur_economiser(self) -> None:
        scorer = ScorerARC()
        self.assertGreater(scorer.score(_Evidence(2, 500)), scorer.score(_Evidence(1, 10)))

    def test_a_progression_egale_moins_d_actions_vaut_mieux(self) -> None:
        scorer = ScorerARC()
        self.assertGreater(scorer.score(_Evidence(2, 100)), scorer.score(_Evidence(2, 300)))

    def test_aucune_progression_n_est_pas_une_version_valide(self) -> None:
        """« Correct » = progression constatée par l'environnement (§H9.2)."""
        scorer = ScorerARC()
        self.assertFalse(scorer.est_valide(_Evidence(0, 50)))
        self.assertTrue(scorer.est_valide(_Evidence(1, 50)))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
