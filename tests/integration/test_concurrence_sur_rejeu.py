"""Le client réel sous limiteur de concurrence, contre le rejeu HTTP (§H4.9).

@verifies docs/BACKLOG.md U32 — Limitation de concurrence des requêtes LLM par endpoint
@verifies docs/SPEC_HARNAIS.md §H4.9 (jeton tenu pendant la requête HTTP réelle,
          libéré après ; répertoire par endpoint sous `AVO_LLM_SLOTS_DIR`)

La preuve passe par le VRAI chemin : configuration en mode live pointant le
rejoueur local (aucun réseau externe, garde A2.3), transport `urllib` réel, et
la cassette enregistrée sur le vrai endpoint (§H4.7).
"""

from __future__ import annotations

import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from avo.config import Config, Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP, transport_urllib
from avo.llm.concurrence import dossier_endpoint
from llm_replay.record import OUTILS, _messages_chat_outils
from llm_replay.server import creer_serveur

CASSETTE = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")
CLE = "sk-cle-de-rejeu-concurrence"


class TestConcurrenceSurRejeu(unittest.TestCase):
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
        self._tmp = tempfile.TemporaryDirectory()
        self.slots = Path(self._tmp.name) / "jetons"
        self.addCleanup(self._tmp.cleanup)

    def _config_live_sur_rejeu(self) -> Config:
        return charger(
            Mode.LIVE,
            env={
                "OLLAMA_HOST": self.base,
                "OLLAMA_API_KEY": CLE,
                "OLLAMA_CONTEXT_LENGTH": "8192",
                "ARC_API_KEY": "00000000-0000-0000-0000-000000000000",
                "AVO_LLM_SLOTS_DIR": str(self.slots),
            },
            racine=Path("/inexistant"),
        )

    def test_le_jeton_est_tenu_pendant_la_requete_reelle_puis_libere(self) -> None:
        config = self._config_live_sur_rejeu()
        dossier = dossier_endpoint(self.slots, config.ollama_host)
        pendant: list[int] = []

        def transport_espionne(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
            pendant.append(len(list(dossier.glob("slot-*"))))
            return transport_urllib(url, corps, entetes, timeout)

        client = LLMClient(config, transport=transport_espionne, dormir=lambda _s: None)
        resultat = client.chat(
            _messages_chat_outils(), list(OUTILS), num_ctx=8192, num_predict=256, temperature=0
        )
        self.assertTrue(resultat.demande_outil)
        self.assertEqual(pendant, [1], "exactement un jeton tenu pendant l'appel HTTP")
        self.assertEqual(list(dossier.glob("slot-*")), [], "jeton libéré après la réponse")


if __name__ == "__main__":
    unittest.main()
