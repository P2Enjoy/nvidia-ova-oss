"""E2E : parties complètes sur rejeu local, par la CLI réelle, pile compose debout.

@verifies docs/BACKLOG.md U21 — E2E : partie complète sur rejeu local
@verifies docs/SPEC_ARCAGI3.md §A8.3 (preuve cœur : victoire 3 niveaux au RHAE exact,
          échec → RESET → victoire), §A8.5 (contrat d'implémentation), §A7.3 (rapport)
@verifies docs/SPEC_HARNAIS.md §H6.1 (artefacts du run), §H9.3 (lignée isolée),
          §H13.2 (reprise sans nouvel appel au modèle)

La pile compose sert les cassettes de scénario seedées (`make seed-e2e`) ; l'agent
complet joue le jeu `cible` de bout en bout. Les valeurs attendues sont en forme
fermée : baselines [39, 19, 18], partie parfaite à 76 actions → RHAE 100.00 ;
échec puis victoire à 80 actions (43 au niveau 1) → RHAE min((100·(39/43)²+500)/6, 100).
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from avo import cli
from avo.arc.campagne import EtatCampagne
from avo.memory.workspace import Workspace
from tests.e2e.scenarios import DOSSIER_CASSETTES, ECHEC, JEU, PLAFONDS_CLI, SCENARIOS, VICTOIRE

HOTE_LLM = "http://127.0.0.1:11435"
BASE_ARC = "http://127.0.0.1:8765"

#: RHAE attendu du scénario d'échec, recalculé indépendamment du module rhae (§A8.5).
RHAE_ECHEC = min((1 * min(115.0, 100.0 * (39 / 43) ** 2) + 2 * 100.0 + 3 * 100.0) / 6, 100.0)


def setUpModule() -> None:  # noqa: N802 — contrat unittest
    """La pile et les cassettes sont des préconditions NOMMÉES, pas des surprises."""
    for scenario in SCENARIOS:
        if not (DOSSIER_CASSETTES / scenario.cassette).exists():
            raise RuntimeError(
                f"cassette {scenario.cassette} absente — lancez « make seed-e2e » "
                "puis relancez la pile (make down && make up)"
            )
    for nom, url in (("llm-replay", f"{HOTE_LLM}/_health"), ("arc-replay", f"{BASE_ARC}/_health")):
        try:
            with urllib.request.urlopen(url, timeout=5) as reponse:
                if reponse.status != 200:
                    raise RuntimeError(f"{nom} répond {reponse.status}")
        except Exception as erreur:  # noqa: BLE001 — le message opérateur prime
            raise RuntimeError(
                f"pile compose injoignable ({nom} : {erreur}) — lancez « make up » (§A8.5)"
            ) from erreur


class TestVictoireParCliReelle(unittest.TestCase):
    """Scénario victoire : sous-processus `python -m avo` réel (MASTER_PLAN §5)."""

    RUN_ID = "e2e-victoire"

    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        self.env = {
            **os.environ,
            **VICTOIRE.environnement(HOTE_LLM, BASE_ARC),
            "AVO_RUNS_DIR": str(self.racine),
        }

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def _cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "avo", *arguments],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )

    def test_partie_parfaite_rhae_100_artefacts_et_reprise(self) -> None:
        execution = self._cli(
            "run-arc", "--mode", "replay", "--games", JEU, "--run-id", self.RUN_ID, *PLAFONDS_CLI
        )
        self.assertEqual(execution.returncode, 0, execution.stderr)
        self.assertIn(f"{JEU} : 3/3 niveaux, 76 actions, RHAE 100.00", execution.stdout)
        self.assertIn("score global : 100.00", execution.stdout)

        espace = Workspace(self.racine, self.RUN_ID)

        # Rapport (§A7.3) : présent, sections attendues, cohérent avec les compteurs.
        rapport = espace.rapport.read_text(encoding="utf-8")
        for section in ("Par jeu", "Détail par niveau", "Coûts", "Événements", "Limites"):
            with self.subTest(section=section):
                self.assertIn(section, rapport)
        self.assertIn("pas comparable", rapport)

        # Frames typées par niveau (§H6.1).
        for niveau in (1, 2, 3):
            with self.subTest(frames=niveau):
                self.assertTrue((espace.frames / JEU / f"niveau_{niveau:02d}.jsonl").exists())

        # Lignée git isolée, portant les trois complétions (§H9.3, §A8.5).
        lignee = espace.chemin / "lineage" / JEU
        self.assertTrue((lignee / ".git").is_dir())
        journal_lignee = (
            subprocess.run(
                ["git", "--git-dir", str(lignee / ".git"), "log", "--format=%s"],
                capture_output=True,
                text=True,
                check=True,
            )
            .stdout.strip()
            .splitlines()
        )
        self.assertEqual(len(journal_lignee), 3, journal_lignee)

        # Métriques : une par action jouée, et le rapport annonce le même compte.
        types = [ligne["type"] for ligne in espace.lire_metriques()]
        self.assertEqual(types.count("action"), 76)
        appels_llm = types.count("llm")
        self.assertGreater(appels_llm, 0)
        self.assertIn(f"appels au modèle : **{appels_llm}**", rapport)

        # État de campagne : la forme fermée jusque dans le détail par niveau.
        etat = EtatCampagne.lire(espace)
        jeu = etat.resultats[0]
        self.assertEqual([niveau.actions for niveau in jeu.niveaux], [39, 19, 18])
        self.assertTrue(all(niveau.complete for niveau in jeu.niveaux))
        self.assertEqual(jeu.rhae.valeur, 100.0)

        # Reprise par la CLI réelle : même bilan, aucun nouvel appel au modèle (§H13.2).
        reprise = self._cli("resume", self.RUN_ID)
        self.assertEqual(reprise.returncode, 0, reprise.stderr)
        self.assertIn(f"{JEU} : 3/3 niveaux, 76 actions, RHAE 100.00", reprise.stdout)
        types_apres = [ligne["type"] for ligne in espace.lire_metriques()]
        self.assertEqual(
            types_apres.count("llm"), appels_llm, "la reprise ne rappelle pas le modèle"
        )
        self.assertEqual(types_apres.count("action"), 76, "la reprise ne rejoue rien")


class TestEchecResetVictoire(unittest.TestCase):
    """Scénario échec : GAME_OVER après trois clics manqués, RESET, puis victoire."""

    RUN_ID = "e2e-echec"

    def test_game_over_reset_puis_victoire_au_rhae_exact(self) -> None:
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            environnement = {
                **ECHEC.environnement(HOTE_LLM, BASE_ARC),
                "AVO_RUNS_DIR": str(racine),
            }
            sortie = io.StringIO()
            with (
                mock.patch.dict(os.environ, environnement, clear=False),
                contextlib.redirect_stdout(sortie),
            ):
                code = cli.main(
                    [
                        "run-arc",
                        "--mode",
                        "replay",
                        "--games",
                        JEU,
                        "--run-id",
                        self.RUN_ID,
                        *PLAFONDS_CLI,
                    ]
                )

            self.assertEqual(code, 0)
            texte = sortie.getvalue()
            self.assertIn(f"{JEU} : 3/3 niveaux, 80 actions, RHAE {RHAE_ECHEC:.2f}", texte)

            espace = Workspace(racine, self.RUN_ID)
            etat = EtatCampagne.lire(espace)
            jeu = etat.resultats[0]
            self.assertEqual(jeu.game_overs, 1, "un seul GAME_OVER, celui du scénario")
            self.assertEqual([niveau.actions for niveau in jeu.niveaux], [43, 19, 18])
            self.assertTrue(all(niveau.complete for niveau in jeu.niveaux))
            self.assertAlmostEqual(jeu.rhae.valeur, RHAE_ECHEC, places=9)

            # Le RESET et le GAME_OVER sont des événements du rapport (§A7.3).
            rapport = espace.rapport.read_text(encoding="utf-8")
            self.assertIn("Événements", rapport)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
