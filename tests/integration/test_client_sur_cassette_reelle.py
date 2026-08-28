"""Le client d'inférence face au contrat RÉELLEMENT enregistré.

@verifies docs/BACKLOG.md U7 — Client d'inférence
@verifies docs/SPEC_HARNAIS.md §H4.2 (le corps émis est bien celui enregistré),
          §H4.3 (réponse typée), §H4.4 (401 fatal, 413 avec champs réels), §H4.7 (rejeu)

C'est la preuve qui compte : le client parle au rejeu des échanges capturés sur le
vrai serveur. Si le corps qu'il émet divergeait de celui enregistré, l'appariement
échouerait — le test rougirait au lieu d'absorber la divergence.
"""

from __future__ import annotations

import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from avo.config import Config, Mode, charger
from avo.llm.client import AuthError, ContextOverflow, LLMClient
from llm_replay.record import (
    CLE_INVALIDE,
    OPTIONS_COURTES,
    OPTIONS_DEPASSEMENT,
    OPTIONS_OUTILS,
    OUTILS,
    _messages_chat_outils,
    _messages_chat_simple,
    _messages_chat_trop_grand,
)
from llm_replay.server import creer_serveur

CASSETTE = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")
CLE = "cle-de-rejeu"


class TestOptionsDesScenarios(unittest.TestCase):
    """Les valeurs employées ici doivent rester celles de l'enregistrement."""

    def test_les_options_correspondent_a_celles_des_scenarios(self) -> None:
        self.assertEqual(OPTIONS_COURTES, {"num_ctx": 8192, "num_predict": 64, "temperature": 0})
        self.assertEqual(OPTIONS_OUTILS, {"num_ctx": 8192, "num_predict": 256, "temperature": 0})
        self.assertEqual(
            OPTIONS_DEPASSEMENT, {"num_ctx": 8192, "num_predict": 16, "temperature": 0}
        )


class TestClientSurContratReel(unittest.TestCase):
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

    def _config(self, cle: str = CLE) -> Config:
        return charger(
            Mode.REJEU,
            env={"OLLAMA_HOST": self.base, "OLLAMA_API_KEY": cle},
            racine=Path("/inexistant"),
        )

    def _client(self, cle: str = CLE) -> LLMClient:
        return LLMClient(self._config(cle), dormir=lambda _: None)

    def test_conversation_simple_rejouee_de_bout_en_bout(self) -> None:
        resultat = self._client().chat(
            _messages_chat_simple(), num_ctx=8192, num_predict=64, temperature=0
        )
        self.assertEqual(resultat.modele, "qwen3.6:35b")
        self.assertGreater(resultat.prompt_eval_count, 0)
        self.assertGreater(resultat.eval_count, 0)
        self.assertIsNotNone(resultat.done_reason)

    def test_l_appel_d_outil_du_vrai_serveur_est_normalise(self) -> None:
        """Prérequis dur de la boucle agent (§H8) : éprouvé sur la vraie réponse."""
        resultat = self._client().chat(
            _messages_chat_outils(), list(OUTILS), num_ctx=8192, num_predict=256, temperature=0
        )
        # Contrat réel mesuré : la surface native rend « stop » même pour un appel
        # d'outil. La détection se fait donc sur la présence de tool_calls (§H4.3).
        self.assertEqual(resultat.done_reason, "stop")
        self.assertTrue(resultat.demande_outil)
        self.assertTrue(resultat.tool_calls)
        appel = resultat.tool_calls[0]
        self.assertEqual(appel.nom, "run_shell")
        self.assertTrue(appel.valide)
        self.assertIn("command", appel.arguments)

    def test_cle_invalide_donne_une_erreur_d_authentification_fatale(self) -> None:
        with self.assertRaises(AuthError):
            self._client(cle=CLE_INVALIDE).chat(
                _messages_chat_simple(), num_ctx=8192, num_predict=64, temperature=0
            )

    def test_depassement_de_contexte_porte_le_plafond_reel(self) -> None:
        """Les champs alimentent le budget appris (§H3.2) et la continuation (§H5.4)."""
        with self.assertRaises(ContextOverflow) as capture:
            self._client().chat(
                _messages_chat_trop_grand(), num_ctx=8192, num_predict=16, temperature=0
            )
        erreur = capture.exception
        self.assertIsNotNone(erreur.max_context_tokens)
        assert erreur.max_context_tokens is not None
        self.assertGreater(erreur.max_context_tokens, 0)
        self.assertIsNotNone(erreur.tokens_estimated)

    def test_le_plafond_appris_reduit_effectivement_le_budget(self) -> None:
        """Chaîne complète : le 413 du vrai serveur pilote la configuration."""
        config = charger(
            Mode.REJEU,
            env={
                "OLLAMA_HOST": self.base,
                "OLLAMA_API_KEY": CLE,
                "OLLAMA_CONTEXT_LENGTH": "1000000",
            },
            racine=Path("/inexistant"),
        )
        client = LLMClient(config, dormir=lambda _: None)
        with self.assertRaises(ContextOverflow) as capture:
            client.chat(_messages_chat_trop_grand(), num_ctx=8192, num_predict=16, temperature=0)
        plafond = capture.exception.max_context_tokens
        assert plafond is not None
        appris = config.avec_plafond_appris(plafond)
        self.assertEqual(appris.contexte_demande, plafond)
        self.assertLess(appris.budget_prompt, config.budget_prompt)

    def test_une_requete_non_enregistree_ne_rend_jamais_une_reponse_inventee(self) -> None:
        from avo.llm.client import ProtocolError

        with self.assertRaises((ProtocolError, Exception)) as capture:
            self._client().chat([{"role": "user", "content": "jamais enregistré"}])
        self.assertNotIsInstance(capture.exception, AssertionError)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
