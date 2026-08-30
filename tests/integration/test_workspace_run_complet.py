"""Un échange complet produit-il un workspace conforme et sans secret ?

@verifies docs/BACKLOG.md U8 — Comptabilité, journalisation, workspace de run
@verifies docs/SPEC_HARNAIS.md §H6.1 (arborescence du run), §H11.1 (journalisation),
          §H11.2 (métriques), §H11.3 (transcripts), §H5.2 (comptabilité),
          §H4.6 (aucun secret ni dans les journaux ni dans les artefacts)

La chaîne entière est éprouvée : configuration, journalisation, client contre le rejeu
du contrat RÉEL, comptabilité des tokens, et écriture des artefacts.
"""

from __future__ import annotations

import io
import json
import logging
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from avo.config import Config, Mode, charger
from avo.context.tokens import TokenLedger
from avo.llm.client import LLMClient
from avo.memory.workspace import SOUS_DOSSIERS, Workspace
from avo.runlog import configurer_journalisation
from llm_replay.record import _messages_chat_simple
from llm_replay.server import creer_serveur

CASSETTE = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")
CLE = "sk-cle-de-rejeu-suffisamment-longue"


class TestRunComplet(unittest.TestCase):
    serveur: ThreadingHTTPServer
    fil: threading.Thread
    base: str

    @classmethod
    def setUpClass(cls) -> None:
        if not CASSETTE.exists():
            raise unittest.SkipTest(f"cassette absente ({CASSETTE}) : lancer « make record-llm »")
        cls.serveur = creer_serveur(CASSETTE.parent, port=0, cle_attendue=CLE)
        hote, port = cls.serveur.server_address[0], cls.serveur.server_address[1]
        cls.base = f"http://{hote!s}:{port}"
        cls.fil = threading.Thread(target=cls.serveur.serve_forever, daemon=True)
        cls.fil.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.serveur.shutdown()
        cls.serveur.server_close()
        cls.fil.join(timeout=5)

    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        self.journal = io.StringIO()
        configurer_journalisation(run_id="run-integration", secrets=(CLE,), flux=self.journal)

    def tearDown(self) -> None:
        configurer_journalisation(flux=io.StringIO())
        self._dossier.cleanup()

    def _config(self) -> Config:
        return charger(
            Mode.REJEU,
            env={"OLLAMA_HOST": self.base, "OLLAMA_API_KEY": CLE},
            racine=Path("/inexistant"),
        )

    def _executer_un_echange(self) -> tuple[Workspace, TokenLedger]:
        config = self._config()
        espace = Workspace.ouvrir(config, "run-integration", racine=self.racine)
        registre = TokenLedger()
        client = LLMClient(config, dormir=lambda _: None)

        segment = espace.nouveau_segment()
        messages = _messages_chat_simple()
        estime = registre.estimer_messages(messages)
        for message in messages:
            espace.ajouter_au_transcript(segment, message)

        resultat = client.chat(messages, num_ctx=8192, num_predict=64, temperature=0)

        registre.enregistrer(estime, resultat.prompt_eval_count, resultat.eval_count)
        espace.ajouter_au_transcript(segment, {"role": "assistant", "content": resultat.content})
        espace.metrique("appel_llm", segment=segment, **resultat.resume())
        espace.ecrire_rapport(
            "Run d'intégration",
            [("Comptabilité", json.dumps(registre.resume(), ensure_ascii=False))],
        )
        return espace, registre

    def test_l_arborescence_est_conforme(self) -> None:
        espace, _ = self._executer_un_echange()
        arborescence = espace.arborescence()
        for attendu in (*SOUS_DOSSIERS, "manifest.json", "metrics.jsonl", "report.md"):
            self.assertIn(attendu, arborescence, attendu)
        self.assertIn("transcripts/segment_001.jsonl", arborescence)

    def test_le_transcript_porte_l_echange_reel(self) -> None:
        espace, _ = self._executer_un_echange()
        lignes = [
            json.loads(ligne)
            for ligne in espace.chemin_segment(1).read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(lignes[0]["role"], "user")
        self.assertEqual(lignes[-1]["role"], "assistant")

    def test_les_metriques_portent_les_compteurs_du_vrai_serveur(self) -> None:
        espace, _ = self._executer_un_echange()
        appels = [ligne for ligne in espace.lire_metriques() if ligne["type"] == "appel_llm"]
        self.assertEqual(len(appels), 1)
        self.assertGreater(appels[0]["prompt_eval_count"], 0)
        self.assertEqual(appels[0]["modele"], "qwen3.6:35b")

    def test_la_comptabilite_se_calibre_sur_le_compte_reel(self) -> None:
        _, registre = self._executer_un_echange()
        self.assertEqual(registre.appels, 1)
        self.assertGreater(registre.reel_cumule, 0)
        self.assertNotEqual(registre.facteur_correction, 1.0)

    def test_aucun_secret_dans_les_journaux(self) -> None:
        self._executer_un_echange()
        self.assertNotIn(CLE, self.journal.getvalue())
        self.assertTrue(
            self.journal.getvalue().strip(), "la journalisation doit produire des lignes"
        )

    def test_aucun_secret_dans_aucun_artefact_du_run(self) -> None:
        """La preuve qui compte : on cherche la clé dans TOUS les fichiers produits."""
        espace, _ = self._executer_un_echange()
        for fichier in espace.chemin.rglob("*"):
            if fichier.is_file():
                with self.subTest(fichier=str(fichier.relative_to(espace.chemin))):
                    self.assertNotIn(CLE, fichier.read_text(encoding="utf-8"))

    def test_les_lignes_de_journal_sont_du_json_correle(self) -> None:
        self._executer_un_echange()
        lignes = [
            json.loads(ligne) for ligne in self.journal.getvalue().splitlines() if ligne.strip()
        ]
        self.assertTrue(lignes)
        self.assertTrue(all(ligne["run_id"] == "run-integration" for ligne in lignes))
        self.assertTrue(any(ligne["journal"] == "avo.llm" for ligne in lignes))


class TestJournalisationDuClient(unittest.TestCase):
    """Le client journalise ses compteurs, jamais son contenu (§H4.6)."""

    def tearDown(self) -> None:
        configurer_journalisation(flux=io.StringIO())
        logging.getLogger("avo").handlers.clear()

    def test_le_journal_porte_les_compteurs_et_pas_le_contenu(self) -> None:
        if not CASSETTE.exists():
            self.skipTest("cassette absente")
        flux = io.StringIO()
        configurer_journalisation(run_id="run-j", secrets=(CLE,), flux=flux)
        serveur = creer_serveur(CASSETTE.parent, port=0, cle_attendue=CLE)
        hote, port = serveur.server_address[0], serveur.server_address[1]
        fil = threading.Thread(target=serveur.serve_forever, daemon=True)
        fil.start()
        try:
            config = charger(
                Mode.REJEU,
                env={"OLLAMA_HOST": f"http://{hote!s}:{port}", "OLLAMA_API_KEY": CLE},
                racine=Path("/inexistant"),
            )
            resultat = LLMClient(config, dormir=lambda _: None).chat(
                _messages_chat_simple(), num_ctx=8192, num_predict=64, temperature=0
            )
        finally:
            serveur.shutdown()
            serveur.server_close()
            fil.join(timeout=5)
        trace = flux.getvalue()
        self.assertIn("prompt_eval_count", trace)
        if resultat.content.strip():
            self.assertNotIn(resultat.content.strip(), trace)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
