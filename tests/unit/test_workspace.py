"""Preuves du workspace de run : arborescence, manifeste, métriques, transcripts.

@verifies docs/BACKLOG.md U8 — Comptabilité, journalisation, workspace de run
@verifies docs/SPEC_HARNAIS.md §H6.1 (arborescence), §H11.2 (métriques),
          §H11.3 (transcripts), §H4.6 (aucun secret persisté)
@verifies docs/BACKLOG.md U27 — persistance de Σ (§H15.5)
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

import avo
from avo.config import Config, Mode, charger
from avo.context.etat import Etat
from avo.memory.workspace import SOUS_DOSSIERS, Workspace

_SECRET = "sk-ollama-secret-de-test-du-workspace"


def _config() -> Config:
    return charger(
        Mode.LIVE,
        env={
            "OLLAMA_HOST": "https://exemple.test:1234",
            "OLLAMA_API_KEY": _SECRET,
            "OLLAMA_CONTEXT_LENGTH": "229376",
            "ARC_API_KEY": "00000000-0000-0000-0000-000000000000",
        },
        racine=Path("/inexistant"),
    )


class TestWorkspace(unittest.TestCase):
    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        self.espace = Workspace.ouvrir(_config(), "run-test", racine=self.racine)

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def test_l_arborescence_du_run_est_creee(self) -> None:
        for sous in SOUS_DOSSIERS:
            self.assertTrue((self.espace.chemin / sous).is_dir(), sous)
        self.assertTrue(self.espace.manifeste.is_file())

    def test_le_manifeste_porte_version_et_configuration(self) -> None:
        contenu = json.loads(self.espace.manifeste.read_text(encoding="utf-8"))
        self.assertEqual(contenu["run_id"], "run-test")
        self.assertEqual(contenu["version_harnais"], avo.__version__)
        self.assertEqual(contenu["config"]["mode"], "live")
        self.assertEqual(contenu["config"]["contexte_demande"], 229376)

    def test_le_manifeste_ne_contient_aucun_secret(self) -> None:
        """§H4.6 : le workspace est auditable, donc il ne porte pas les clés."""
        self.assertNotIn(_SECRET, self.espace.manifeste.read_text(encoding="utf-8"))

    def test_horodatage_injectable_pour_des_runs_reproductibles(self) -> None:
        instant = datetime(2026, 8, 28, 3, 0, 0, tzinfo=UTC)
        espace = Workspace.ouvrir(_config(), "run-fixe", racine=self.racine, horodatage=instant)
        contenu = json.loads(espace.manifeste.read_text(encoding="utf-8"))
        self.assertEqual(contenu["ouvert_le"], "2026-08-28T03:00:00+00:00")


class TestMetriques(unittest.TestCase):
    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.espace = Workspace.ouvrir(_config(), "run-m", racine=Path(self._dossier.name))

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def test_chaque_evenement_ajoute_une_ligne(self) -> None:
        self.espace.metrique("appel_llm", prompt_eval_count=24, eval_count=218)
        self.espace.metrique("continuation", segment=2)
        lignes = self.espace.lire_metriques()
        self.assertEqual([ligne["type"] for ligne in lignes], ["appel_llm", "continuation"])
        self.assertEqual(lignes[0]["prompt_eval_count"], 24)

    def test_les_metriques_sont_cumulables(self) -> None:
        for tokens in (10, 20, 30):
            self.espace.metrique("appel_llm", eval_count=tokens)
        total = sum(ligne["eval_count"] for ligne in self.espace.lire_metriques())
        self.assertEqual(total, 60)

    def test_metriques_absentes_donnent_une_liste_vide(self) -> None:
        self.assertEqual(Workspace(Path("/inexistant"), "x").lire_metriques(), [])


class TestTranscripts(unittest.TestCase):
    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.espace = Workspace.ouvrir(_config(), "run-t", racine=Path(self._dossier.name))

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def test_les_segments_sont_numerotes_dans_l_ordre(self) -> None:
        self.assertEqual(self.espace.nouveau_segment(), 1)
        self.assertEqual(self.espace.nouveau_segment(), 2)
        self.assertTrue(self.espace.chemin_segment(1).is_file())
        self.assertEqual(self.espace.chemin_segment(2).name, "segment_002.jsonl")

    def test_le_transcript_est_append_only(self) -> None:
        segment = self.espace.nouveau_segment()
        self.espace.ajouter_au_transcript(segment, {"role": "user", "content": "un"})
        self.espace.ajouter_au_transcript(segment, {"role": "assistant", "content": "deux"})
        lignes = self.espace.chemin_segment(segment).read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(ligne)["content"] for ligne in lignes], ["un", "deux"])

    def test_deux_segments_ne_se_melangent_pas(self) -> None:
        a, b = self.espace.nouveau_segment(), self.espace.nouveau_segment()
        self.espace.ajouter_au_transcript(a, {"x": 1})
        self.espace.ajouter_au_transcript(b, {"x": 2})
        self.assertIn('"x": 1', self.espace.chemin_segment(a).read_text(encoding="utf-8"))
        self.assertNotIn('"x": 1', self.espace.chemin_segment(b).read_text(encoding="utf-8"))


class TestEtatPersiste(unittest.TestCase):
    """§H15.5 : Σ survit à une écriture puis une relecture, aller-retour exact."""

    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.espace = Workspace.ouvrir(_config(), "run-etat", racine=Path(self._dossier.name))

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def test_aucun_etat_avant_la_premiere_ecriture(self) -> None:
        self.assertIsNone(self.espace.lire_etat())

    def test_ecrire_puis_lire_rend_un_etat_egal(self) -> None:
        etat = Etat.initial().fusionner({"essai": 2, "hypotheses": ["h1"]})
        self.espace.ecrire_etat(etat)
        self.assertEqual(self.espace.lire_etat(), etat)

    def test_une_reecriture_remplace_la_precedente(self) -> None:
        self.espace.ecrire_etat(Etat.initial())
        etat = Etat.initial().fusionner({"essai": 3})
        self.espace.ecrire_etat(etat)
        self.assertEqual(self.espace.lire_etat(), etat)

    def test_le_fichier_vit_sous_state(self) -> None:
        self.espace.ecrire_etat(Etat.initial())
        self.assertEqual(self.espace.etat_json, self.espace.chemin / "state" / "etat.json")
        self.assertTrue(self.espace.etat_json.is_file())


class TestRapport(unittest.TestCase):
    def test_le_rapport_porte_le_run_et_ses_sections(self) -> None:
        with tempfile.TemporaryDirectory() as dossier:
            espace = Workspace.ouvrir(_config(), "run-r", racine=Path(dossier))
            espace.ecrire_rapport("Campagne", [("Résultats", "tout vert"), ("Limites", "aucune")])
            texte = espace.rapport.read_text(encoding="utf-8")
            self.assertIn("# Campagne", texte)
            self.assertIn("run-r", texte)
            self.assertIn("## Résultats", texte)
            self.assertIn("tout vert", texte)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
