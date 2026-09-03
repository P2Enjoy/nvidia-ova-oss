"""E2E : un épisode de chaque banc joué par la CLI réelle, pile compose debout.

@verifies docs/BACKLOG.md U29a2 — adaptateur harnais + CLI `banc` ; U29a4 —
          branchement du Dépôt logiciel (scénario CLI du dépôt, résolution
          §S4.4) ; U29b2 — scénario CLI du banc CTF (capture attendue, §S12.5) ;
          U29c2 — scénario CLI du banc τ (réussite attendue, §S18.5)
@verifies docs/SPEC_BANCS.md §S6.3 (CLI `banc` : boucle complète, relevé §S5.3
          écrit dans le workspace), §S6.4 (E2E : scénario rejoué par cassette,
          épisode court, score attendu exact), §S12.4 (CLI `banc ctf`,
          `--executeur` paramètre d'infrastructure)
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

from tests.e2e.generer_cassette_banc import (
    DOSSIER_CASSETTES,
    SCENARIO_CTF,
    SCENARIO_DEPOT,
    SCENARIO_ENTREPOT,
    SCENARIO_TAU,
    SCENARIOS,
)
from tests.e2e.scenarios_banc import ENV_EPINGLE_BANC, JETON

HORIZON = SCENARIO_ENTREPOT.horizon
SEED = SCENARIO_ENTREPOT.seed

HOTE_LLM = "http://127.0.0.1:11435"


def setUpModule() -> None:  # noqa: N802 — contrat unittest
    """La pile et la cassette sont des préconditions NOMMÉES, pas des surprises."""
    cassettes = [scenario.cassette for scenario in SCENARIOS]
    cassettes += [SCENARIO_CTF.cassette, SCENARIO_TAU.cassette]
    for cassette in cassettes:
        if not (DOSSIER_CASSETTES / cassette).exists():
            raise RuntimeError(
                f"cassette {cassette} absente — lancez « make seed-e2e » "
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


class TestBancDepotParCliReelle(unittest.TestCase):
    """Scénario dépôt : sous-processus `python -m avo banc --env depot` réel.

    Même parcours opérateur que l'Entrepôt (MASTER_PLAN §5) ; s'y ajoute la
    résolution B.1 du relevé (§S4.4) : les deux demandes jugées de l'épisode
    sont correctement résolues sous jeu parfait.
    """

    RUN_ID = "e2e-banc-depot"

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

    def test_episode_parfait_score_resolution_et_artefacts(self) -> None:
        execution = subprocess.run(
            [
                sys.executable,
                "-m",
                "avo",
                "banc",
                "skillexec",
                "--env",
                "depot",
                "--seed",
                str(SCENARIO_DEPOT.seed),
                "--horizon",
                str(SCENARIO_DEPOT.horizon),
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
        self.assertIn(
            f"seed {SCENARIO_DEPOT.seed}, horizon {SCENARIO_DEPOT.horizon}, bruit 0 — score 1.00",
            execution.stdout,
        )
        self.assertIn(
            f"{SCENARIO_DEPOT.horizon} correctes, 0 incorrectes, 0 invalides",
            execution.stdout,
        )

        espace = self.racine / self.RUN_ID

        # Relevé §S5.3 : écrit, exact, résolution B.1 comprise (§S4.4).
        releve = json.loads((espace / "banc.json").read_text(encoding="utf-8"))
        self.assertEqual(releve["score"], 1.0)
        self.assertEqual(releve["seed"], SCENARIO_DEPOT.seed)
        self.assertEqual(releve["horizon"], SCENARIO_DEPOT.horizon)
        self.assertEqual(releve["banc"], "skillexec")
        self.assertEqual(releve["environnement"], "depot")
        self.assertEqual(releve["mode_contexte"], "state")
        self.assertEqual(releve["resolution"], 1.0)
        self.assertEqual(releve["demandes_resolues"], 2)
        self.assertEqual(releve["demandes_jugees"], 2)
        self.assertGreater(releve["tokens_consommes"], 0)

        # Artefacts du run (§H6.1, §H15.5) : manifeste, métriques, Σ persisté.
        self.assertTrue((espace / "manifest.json").exists())
        self.assertTrue((espace / "state" / "etat.json").exists())
        types = [
            json.loads(ligne)["type"]
            for ligne in (espace / "metrics.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(types.count("action"), SCENARIO_DEPOT.horizon)
        self.assertEqual(types.count("llm"), SCENARIO_DEPOT.horizon)


class TestBancCtfParCliReelle(unittest.TestCase):
    """Scénario CTF : sous-processus `python -m avo banc ctf` réel (§S12.4).

    Même parcours opérateur que le banc a (MASTER_PLAN §5) ; l'exécuteur
    `processus` est celui des preuves (§S10.3 : la suite tourne déjà en
    conteneur, sans démon Docker), les commandes du recouvrement canonique
    s'exécutent réellement.
    """

    RUN_ID = "e2e-banc-ctf"

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

    def test_capture_par_la_cli_et_artefacts(self) -> None:
        execution = subprocess.run(
            [
                sys.executable,
                "-m",
                "avo",
                "banc",
                "ctf",
                "--env",
                "fouille",
                "--seed",
                str(SCENARIO_CTF.seed),
                "--horizon",
                str(SCENARIO_CTF.horizon),
                "--executeur",
                "processus",
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
        self.assertIn(
            f"seed {SCENARIO_CTF.seed}, famille fouille, horizon {SCENARIO_CTF.horizon}",
            execution.stdout,
        )
        self.assertIn("drapeau capturé", execution.stdout)

        espace = self.racine / self.RUN_ID

        # Relevé §S11.2 : écrit, exact, auto-porteur.
        releve = json.loads((espace / "banc.json").read_text(encoding="utf-8"))
        self.assertTrue(releve["reussi"])
        self.assertEqual(releve["seed"], SCENARIO_CTF.seed)
        self.assertEqual(releve["famille"], "fouille")
        self.assertEqual(releve["horizon"], SCENARIO_CTF.horizon)
        self.assertEqual(releve["actions"], 2)
        self.assertEqual(releve["arret"], "drapeau capturé")
        self.assertEqual(releve["banc"], "ctf")
        self.assertEqual(releve["schema_etat"], "ctf")
        self.assertEqual(releve["executeur"], "processus")
        self.assertEqual(releve["mode_contexte"], "state")
        self.assertGreater(releve["tokens_consommes"], 0)

        # Artefacts du run (§H6.1, §H15.5) : manifeste, métriques, Σ persisté.
        self.assertTrue((espace / "manifest.json").exists())
        self.assertTrue((espace / "state" / "etat.json").exists())
        types = [
            json.loads(ligne)["type"]
            for ligne in (espace / "metrics.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(types.count("action"), 2)
        self.assertEqual(types.count("llm"), 2)

    def test_refus_nomme_d_un_parametre_sans_objet(self) -> None:
        """§S12.4 : `--derive` sur le banc ctf est refusé par une erreur nommée."""
        execution = subprocess.run(
            [
                sys.executable,
                "-m",
                "avo",
                "banc",
                "ctf",
                "--env",
                "fouille",
                "--seed",
                "1",
                "--horizon",
                "3",
                "--derive",
            ],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        self.assertEqual(execution.returncode, 2, execution.stdout)
        self.assertIn("banc refusé", execution.stderr)
        self.assertIn("--derive", execution.stderr)


class TestBancTauParCliReelle(unittest.TestCase):
    """Scénario τ : sous-processus `python -m avo banc tau` réel (§S18.4).

    Même parcours opérateur que les bancs a et b (MASTER_PLAN §5) ;
    l'utilisateur simulé est `scripte` — le mode replay le choisit (§S18.4).
    """

    RUN_ID = "e2e-banc-tau"

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

    def test_episode_conforme_par_la_cli_et_artefacts(self) -> None:
        execution = subprocess.run(
            [
                sys.executable,
                "-m",
                "avo",
                "banc",
                "tau",
                "--env",
                "detail",
                "--seed",
                str(SCENARIO_TAU.seed),
                "--horizon",
                str(SCENARIO_TAU.horizon),
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
        self.assertIn(f"seed {SCENARIO_TAU.seed}, domaine detail", execution.stdout)
        self.assertIn("— réussi", execution.stdout)
        self.assertIn("clos par l'agent", execution.stdout)

        espace = self.racine / self.RUN_ID

        # Relevé §S17.2 : écrit, exact, auto-porteur.
        releve = json.loads((espace / "banc.json").read_text(encoding="utf-8"))
        self.assertTrue(releve["reussi"])
        self.assertEqual(releve["seed"], SCENARIO_TAU.seed)
        self.assertEqual(releve["domaine"], "detail")
        self.assertEqual(releve["actions"], 5)
        self.assertEqual(releve["repliques"], 2)
        self.assertEqual(releve["transactions"], 1)
        self.assertEqual(releve["violations"], 0)
        self.assertEqual(releve["arret"], "clos par l'agent")
        self.assertEqual(releve["banc"], "tau")
        self.assertEqual(releve["schema_etat"], "service")
        self.assertEqual(releve["utilisateur"], "scripte")
        self.assertEqual(releve["mode_contexte"], "state")
        self.assertGreater(releve["tokens_consommes"], 0)

        # Artefacts du run (§H6.1, §H15.5) : manifeste, métriques, Σ persisté.
        self.assertTrue((espace / "manifest.json").exists())
        self.assertTrue((espace / "state" / "etat.json").exists())
        types = [
            json.loads(ligne)["type"]
            for ligne in (espace / "metrics.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(types.count("action"), 5)
        self.assertEqual(types.count("llm"), 5)

    def test_refus_nomme_d_un_parametre_sans_objet(self) -> None:
        """§S18.4 : `--executeur` sur le banc tau est refusé par une erreur nommée."""
        execution = subprocess.run(
            [
                sys.executable,
                "-m",
                "avo",
                "banc",
                "tau",
                "--env",
                "detail",
                "--seed",
                "1",
                "--horizon",
                "5",
                "--executeur",
                "conteneur",
            ],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        self.assertEqual(execution.returncode, 2, execution.stdout)
        self.assertIn("banc refusé", execution.stderr)
        self.assertIn("--executeur", execution.stderr)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
