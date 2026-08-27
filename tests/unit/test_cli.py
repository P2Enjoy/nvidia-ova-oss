"""Preuves de la CLI du harnais.

@verifies docs/BACKLOG.md U3 — Squelette Python et outillage
@verifies docs/SPEC_HARNAIS.md §H2.2 (point d'entrée ``python -m avo``), §H2.3 (contrat)
@verifies docs/MASTER_PLAN.md §5 (le produit est piloté par ces commandes)

Écrit avec ``unittest`` (bibliothèque standard) : s'exécute sous
``python -m unittest`` comme sous ``pytest``, sans qu'aucun outil externe soit requis.
"""

from __future__ import annotations

import io
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import avo
from avo.cli import _A_VENIR, main

_RACINE = Path(__file__).resolve().parents[2]
_SRC = _RACINE / "src"


class TestVersion(unittest.TestCase):
    """La version est unique, exposée par le paquet et par la CLI."""

    def test_version_du_paquet_est_semantique(self) -> None:
        morceaux = avo.__version__.split(".")
        self.assertEqual(len(morceaux), 3, avo.__version__)
        for morceau in morceaux:
            self.assertTrue(morceau.isdigit(), avo.__version__)

    def test_option_version_affiche_la_version_et_sort_en_zero(self) -> None:
        sortie = io.StringIO()
        with self.assertRaises(SystemExit) as capture, redirect_stdout(sortie):
            main(["--version"])
        self.assertEqual(capture.exception.code, 0)
        self.assertEqual(sortie.getvalue().strip(), avo.__version__)

    def test_pyproject_porte_la_meme_version(self) -> None:
        texte = (_RACINE / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn(f'version = "{avo.__version__}"', texte)


class TestInvocationReelle(unittest.TestCase):
    """``python -m avo`` fonctionne réellement, dans un processus séparé."""

    def _executer(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "avo", *args],
            capture_output=True,
            text=True,
            cwd=_RACINE,
            env={"PYTHONPATH": str(_SRC), "PATH": "/usr/bin:/bin"},
            timeout=60,
            check=False,
        )

    def test_module_executable_avec_version(self) -> None:
        resultat = self._executer("--version")
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertEqual(resultat.stdout.strip(), avo.__version__)

    def test_sans_argument_affiche_l_aide_et_sort_en_zero(self) -> None:
        resultat = self._executer()
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertIn("usage:", resultat.stdout)


class TestCommandesNonLivrees(unittest.TestCase):
    """Une commande déclarée mais non livrée refuse explicitement (CLAUDE.md §18)."""

    def test_chaque_commande_a_venir_nomme_son_unite(self) -> None:
        for commande, (unite, _objet) in _A_VENIR.items():
            with self.subTest(commande=commande):
                erreur = io.StringIO()
                with redirect_stderr(erreur):
                    code = main([commande])
                self.assertEqual(code, 2)
                message = erreur.getvalue()
                self.assertIn(commande, message)
                self.assertIn(unite, message)
                self.assertIn("n'est pas encore livrée", message)

    def test_l_aide_liste_les_commandes_a_venir(self) -> None:
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            code = main([])
        self.assertEqual(code, 0)
        for commande in _A_VENIR:
            self.assertIn(commande, sortie.getvalue())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
