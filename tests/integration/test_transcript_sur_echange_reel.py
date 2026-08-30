"""L'invariant append-only tient-il sur un échange RÉEL, et l'estimation se cale-t-elle ?

@verifies docs/BACKLOG.md U9 — Transcript append-only
@verifies docs/SPEC_HARNAIS.md §H5.1 (empreinte de préfixe stable), §H5.2 (calibration
          par `prompt_eval_count`), §H1.3.1 (motif : le cache de préfixe)

Les tests unitaires éprouvent l'invariant sur des messages fabriqués. Celui-ci le
tient sur l'échange enregistré chez le vrai serveur, et vérifie que le compte réel
qu'il rend recalibre effectivement l'estimation.
"""

from __future__ import annotations

import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from avo.config import Mode, charger
from avo.context.tokens import TokenLedger
from avo.context.transcript import Transcript
from avo.llm.client import LLMClient
from llm_replay.record import _messages_chat_simple
from llm_replay.server import creer_serveur

CASSETTE = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")
CLE = "sk-cle-de-rejeu-du-transcript"


class TestTranscriptSurEchangeReel(unittest.TestCase):
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

    def _client(self) -> LLMClient:
        config = charger(
            Mode.REJEU,
            env={"OLLAMA_HOST": self.base, "OLLAMA_API_KEY": CLE},
            racine=Path("/inexistant"),
        )
        return LLMClient(config, dormir=lambda _: None)

    def _echange_reel(self) -> tuple[Transcript, Transcript, TokenLedger, int]:
        """Joue l'échange enregistré et rend l'avant, l'après, le registre et l'estimé."""
        transcript = Transcript.ouvrir()
        for message in _messages_chat_simple():
            transcript = transcript.utilisateur(str(message["content"]))

        registre = TokenLedger()
        estime = registre.estimer(transcript.texte_integral())

        resultat = self._client().chat(
            transcript.pour_api(), num_ctx=8192, num_predict=64, temperature=0
        )
        registre.enregistrer(estime, resultat.prompt_eval_count, resultat.eval_count)
        apres = transcript.assistant(resultat.content)
        return transcript, apres, registre, estime

    def test_le_transcript_alimente_reellement_le_client(self) -> None:
        """Le corps émis vient du transcript : s'il divergeait, le rejeu refuserait."""
        _, apres, _, _ = self._echange_reel()
        self.assertEqual(len(apres), 2)
        self.assertEqual(apres.messages[-1].role, "assistant")

    def test_l_invariant_de_prefixe_tient_apres_la_reponse(self) -> None:
        avant, apres, _, _ = self._echange_reel()
        self.assertTrue(apres.prolonge(avant))
        apres.verifier_prolonge(avant)
        self.assertEqual(apres.empreinte_prefixe(len(avant)), avant.empreinte())

    def test_un_second_tour_prolonge_encore_le_meme_prefixe(self) -> None:
        """Trois tours simulés sur la base réelle : la tête ne bouge jamais."""
        _, apres, _, _ = self._echange_reel()
        tour2 = apres.utilisateur("observation suivante")
        tour3 = tour2.assistant("action suivante")
        for precedent in (apres, tour2):
            self.assertTrue(tour3.prolonge(precedent))
        self.assertEqual(tour3.empreinte_prefixe(len(apres)), apres.empreinte())

    def test_le_compte_reel_du_serveur_recalibre_l_estimation(self) -> None:
        _, _, registre, estime = self._echange_reel()
        self.assertEqual(registre.appels, 1)
        self.assertGreater(registre.reel_cumule, 0)
        self.assertGreater(estime, 0)
        # Après calibration, réestimer le même texte doit rendre le compte réel.
        self.assertNotEqual(registre.facteur_correction, 1.0)

    def test_apres_calibration_l_estimation_colle_au_compte_du_serveur(self) -> None:
        avant, _, registre, _ = self._echange_reel()
        reestime = registre.estimer(avant.texte_integral())
        self.assertAlmostEqual(reestime, registre.reel_cumule, delta=1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
