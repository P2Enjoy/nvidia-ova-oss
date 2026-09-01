"""E2E : un épisode du banc a joué par la CLI réelle, pile compose debout.

@verifies docs/BACKLOG.md U29a2 — adaptateur harnais + CLI `banc`
@verifies docs/SPEC_BANCS.md §S6.3 (CLI `banc` : boucle complète, relevé §S5.3
          écrit dans le workspace), §S6.4 (E2E : scénario rejoué par cassette,
          épisode court, score attendu exact)
@verifies docs/SPEC_HARNAIS.md §H6.1 (artefacts du run), §H15.5 (Σ persisté)
@verifies docs/MASTER_PLAN.md §5 (vérification dans la peau de l'utilisateur :
          la commande documentée, exécutée réellement, artefacts lus)

La pile compose sert la cassette du scénario (`make seed-e2e`) ; la CLI réelle
joue l'épisode de bout en bout, en sous-processus, comme l'opérateur.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path

from tests.e2e.generer_cassette_banc import CASSETTE_NOM, DOSSIER_CASSETTES, HORIZON, SEED
from tests.e2e.scenarios_banc import ENV_EPINGLE_BANC, JETON

HOTE_LLM = "http://127.0.0.1:11435"


def setUpModule() -> None:  # noqa: N802 — contrat unittest
    """La pile et la cassette sont des préconditions NOMMÉES, pas des surprises."""
    if not (DOSSIER_CASSETTES / CASSETTE_NOM).exists():
        raise RuntimeError(
            f"cassette {CASSETTE_NOM} absente — lancez « make seed-e2e » "
            "puis relancez la pile (make down && make up)"
        )
    try:
        with urllib.request.urlopen(f"{HOTE_LLM}/_health", timeout=5) as reponse:
            if reponse.status != 200:
                raise RuntimeError(f"llm-replay répond {reponse.status}")
    except Exception as erreur:  # noqa: BLE001 — le message opérateur prime
        raise RuntimeError(
            f"pile compose injoignable (llm-replay : {erreur}) — lancez « make up »"
        ) from erreur


class TestBancParCliReelle(unittest.TestCase):
    """Scénario banc : sous-processus `python -m avo banc` réel (MASTER_PLAN §5)."""

    RUN_ID = "e2e-banc-entrepot"

    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        self.env = {
            **os.environ,
            **ENV_EPINGLE_BANC,
            "OLLAMA_HOST": HOTE_LLM,
            "OLLAMA_API_KEY": JETON,
            "AVO_RUNS_DIR": str(self.racine),
        }

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def test_episode_parfait_score_exact_et_artefacts(self) -> None:
        execution = subprocess.run(
            [
                sys.executable,
                "-m",
                "avo",
                "banc",
                "skillexec",
                "--env",
                "entrepot",
                "--seed",
                str(SEED),
                "--horizon",
                str(HORIZON),
                "--run-id",
                self.RUN_ID,
            ],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        self.assertEqual(execution.returncode, 0, execution.stderr)
        self.assertIn(f"seed {SEED}, horizon {HORIZON}, bruit 0 — score 1.00", execution.stdout)
        self.assertIn(f"{HORIZON} correctes, 0 incorrectes, 0 invalides", execution.stdout)

        espace = self.racine / self.RUN_ID

        # Relevé §S5.3 : écrit, exact, auto-porteur.
        releve = json.loads((espace / "banc.json").read_text(encoding="utf-8"))
        self.assertEqual(releve["score"], 1.0)
        self.assertEqual(releve["seed"], SEED)
        self.assertEqual(releve["horizon"], HORIZON)
        self.assertEqual(releve["banc"], "skillexec")
        self.assertEqual(releve["environnement"], "entrepot")
        self.assertEqual(releve["mode_contexte"], "state")
        self.assertGreater(releve["tokens_consommes"], 0)

        # Artefacts du run (§H6.1, §H15.5) : manifeste, métriques, Σ persisté.
        self.assertTrue((espace / "manifest.json").exists())
        self.assertTrue((espace / "state" / "etat.json").exists())
        types = [
            json.loads(ligne)["type"]
            for ligne in (espace / "metrics.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(types.count("action"), HORIZON)
        self.assertEqual(types.count("llm"), HORIZON)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
