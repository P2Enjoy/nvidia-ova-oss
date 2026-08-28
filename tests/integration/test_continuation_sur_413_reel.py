"""Continuation et dépassement, éprouvés sur le `413` RÉEL du serveur.

@verifies docs/BACKLOG.md U10 — Budget et continuation en contexte frais
@verifies docs/SPEC_HARNAIS.md §H5.3 (seuil, segment frais), §H5.4 (`413` nominal,
          double dépassement fatal), §H3.2 (plafond appris)

Le refus pour contexte trop grand n'est pas simulé : c'est celui que le vrai serveur
a rendu, rejoué depuis la cassette, avec son corps de quota authentique.
"""

from __future__ import annotations

import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from avo.config import Config, Mode, charger
from avo.context.contexte import BudgetIncoherent, Contexte
from avo.llm.client import ContextOverflow, LLMClient
from llm_replay.record import _messages_chat_simple, _messages_chat_trop_grand
from llm_replay.server import creer_serveur

CASSETTE = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")
CLE = "sk-cle-de-rejeu-de-la-continuation"


class TestContinuationSurServeurRejoue(unittest.TestCase):
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

    def _config(self, **surcharges: str) -> Config:
        env = {"OLLAMA_HOST": self.base, "OLLAMA_API_KEY": CLE, **surcharges}
        return charger(Mode.REJEU, env=env, racine=Path("/inexistant"))

    def _client(self, config: Config) -> LLMClient:
        return LLMClient(config, dormir=lambda _: None)

    def _provoquer_413(self, contexte: Contexte) -> ContextOverflow:
        """Envoie la requête surdimensionnée réellement enregistrée."""
        with self.assertRaises(ContextOverflow) as capture:
            self._client(contexte.config).chat(
                _messages_chat_trop_grand(), num_ctx=8192, num_predict=16, temperature=0
            )
        return capture.exception

    def test_le_413_du_vrai_serveur_porte_bien_son_plafond(self) -> None:
        contexte = Contexte(config=self._config(), systeme="sys")
        erreur = self._provoquer_413(contexte)
        self.assertIsNotNone(erreur.max_context_tokens)
        self.assertIsNotNone(erreur.tokens_estimated)

    def test_un_413_reel_est_absorbe_et_apprend_le_plafond(self) -> None:
        contexte = Contexte(config=self._config(OLLAMA_CONTEXT_LENGTH="1000000"), systeme="sys")
        budget_avant = contexte.budget_prompt
        contexte.absorber_depassement(self._provoquer_413(contexte))
        self.assertEqual(contexte.depassements_consecutifs, 1)
        self.assertLess(contexte.budget_prompt, budget_avant)
        self.assertEqual(
            contexte.config.contexte_demande,
            self._provoquer_413(contexte).max_context_tokens,
        )

    def test_deux_413_reels_consecutifs_sont_fatals(self) -> None:
        contexte = Contexte(config=self._config(OLLAMA_CONTEXT_LENGTH="1000000"), systeme="sys")
        contexte.absorber_depassement(self._provoquer_413(contexte))
        with self.assertRaises(BudgetIncoherent):
            contexte.absorber_depassement(self._provoquer_413(contexte))

    def test_un_echange_reussi_entre_deux_413_evite_l_abandon(self) -> None:
        """Ce sont les dépassements CONSÉCUTIFS qui condamnent (§H5.4)."""
        config = self._config(OLLAMA_CONTEXT_LENGTH="1000000")
        contexte = Contexte(config=config, systeme="sys")
        contexte.absorber_depassement(self._provoquer_413(contexte))
        resultat = self._client(contexte.config).chat(
            _messages_chat_simple(), num_ctx=8192, num_predict=64, temperature=0
        )
        contexte.enregistrer_reponse(resultat)
        self.assertEqual(contexte.depassements_consecutifs, 0)
        contexte.absorber_depassement(self._provoquer_413(contexte))
        self.assertEqual(contexte.depassements_consecutifs, 1)

    def test_petit_budget_force_le_seuil_puis_la_continuation(self) -> None:
        """Le cycle préventif complet, avec un budget volontairement étroit."""
        contexte = Contexte(
            config=self._config(OLLAMA_CONTEXT_LENGTH="6000", AVO_NUM_PREDICT="1000"),
            systeme="sys",
        )
        resultat = self._client(contexte.config).chat(
            _messages_chat_simple(), num_ctx=8192, num_predict=64, temperature=0
        )
        contexte.enregistrer_reponse(resultat)
        self.assertFalse(contexte.seuil_atteint())

        contexte.ajouter_observation("g" * 60000)
        self.assertTrue(contexte.seuil_atteint())

        avant = contexte.transcript
        contexte.continuer("état repris", "notes", "observation courante")
        self.assertEqual(contexte.segment, 2)
        self.assertFalse(contexte.seuil_atteint())
        self.assertEqual(contexte.segments_archives[-1].empreinte(), avant.empreinte())

    def test_le_segment_frais_reste_utilisable_avec_le_vrai_serveur(self) -> None:
        """Après continuation, un échange réel repart normalement."""
        contexte = Contexte(config=self._config(), systeme="sys")
        contexte.continuer("état", "notes", "observation")
        resultat = self._client(contexte.config).chat(
            _messages_chat_simple(), num_ctx=8192, num_predict=64, temperature=0
        )
        contexte.enregistrer_reponse(resultat)
        self.assertEqual(contexte.depassements_consecutifs, 0)
        # Segment frais = système + continuation + notes + observation, puis la
        # réponse enregistrée : cinq messages. Le client n'écrit pas dans le
        # transcript — c'est la boucle agent (U13) qui reliera les deux.
        self.assertEqual(len(contexte.transcript), 5)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
