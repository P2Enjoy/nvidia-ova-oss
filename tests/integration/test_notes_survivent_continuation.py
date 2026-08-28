"""Les notes survivent-elles réellement au renouvellement du contexte ?

@verifies docs/BACKLOG.md U11 — Notes persistantes
@verifies docs/SPEC_HARNAIS.md §H6.2 (les notes survivent), §H5.3 (injection en tête
          de segment frais), §H6.1 (elles vivent dans le workspace du run)

C'est la promesse centrale du mécanisme : quand le contexte conversationnel est jeté,
ce que l'agent a écrit dans ses notes lui revient. Éprouvé sur la chaîne réelle —
workspace, notes, contexte, et un échange contre le rejeu du contrat enregistré.
"""

from __future__ import annotations

import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from avo.config import Config, Mode, charger
from avo.context.contexte import Contexte
from avo.llm.client import LLMClient
from avo.memory.notes import GUIDE, WORKING, Notes, note_write
from avo.memory.workspace import Workspace
from llm_replay.record import _messages_chat_simple
from llm_replay.server import creer_serveur

CASSETTE = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")
CLE = "sk-cle-de-rejeu-des-notes"


class TestNotesEtContinuation(unittest.TestCase):
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

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def _config(self, **surcharges: str) -> Config:
        env = {"OLLAMA_HOST": self.base, "OLLAMA_API_KEY": CLE, **surcharges}
        return charger(Mode.REJEU, env=env, racine=Path("/inexistant"))

    def _monter_run(self, **surcharges: str) -> tuple[Workspace, Notes, Contexte]:
        config = self._config(**surcharges)
        espace = Workspace.ouvrir(config, "run-notes", racine=self.racine)
        return espace, Notes(espace.notes), Contexte(config=config, systeme="tu es un agent")

    def test_les_notes_vivent_dans_le_workspace_du_run(self) -> None:
        espace, notes, _ = self._monter_run()
        note_write(notes, GUIDE, "les verts sautent par-dessus les rouges")
        self.assertTrue((espace.chemin / "notes" / "GUIDE.md").is_file())
        self.assertIn("notes/GUIDE.md", espace.arborescence())

    def test_le_contenu_des_notes_reapparait_dans_le_segment_frais(self) -> None:
        """La promesse centrale : ce qui est noté revient après la continuation."""
        _, notes, contexte = self._monter_run()
        note_write(notes, GUIDE, "RÈGLE : cliquer sur la cible termine le niveau")
        note_write(notes, WORKING, "essai en cours : explorer le bord gauche")

        contexte.ajouter_observation("observation initiale, longue" * 100)
        avant = contexte.transcript
        self.assertNotIn("RÈGLE", avant.texte_integral())

        contexte.continuer("j'ai compris le mécanisme", notes.pour_segment_frais(), "grille")

        frais = contexte.transcript.texte_integral()
        self.assertIn("RÈGLE : cliquer sur la cible termine le niveau", frais)
        self.assertIn("essai en cours : explorer le bord gauche", frais)
        self.assertNotIn("observation initiale", frais)

    def test_les_notes_survivent_a_plusieurs_continuations(self) -> None:
        _, notes, contexte = self._monter_run()
        note_write(notes, GUIDE, "acquis durable")
        for tour in range(3):
            contexte.continuer(f"état {tour}", notes.pour_segment_frais(), f"observation {tour}")
            self.assertIn("acquis durable", contexte.transcript.texte_integral())
        self.assertEqual(contexte.segment, 4)

    def test_une_note_revisee_est_celle_qui_revient(self) -> None:
        _, notes, contexte = self._monter_run()
        note_write(notes, GUIDE, "hypothèse initiale fausse")
        contexte.continuer("état", notes.pour_segment_frais(), "obs")
        note_write(notes, GUIDE, "hypothèse corrigée")
        contexte.continuer("état", notes.pour_segment_frais(), "obs")
        frais = contexte.transcript.texte_integral()
        self.assertIn("hypothèse corrigée", frais)
        self.assertNotIn("hypothèse initiale fausse", frais)

    def test_le_segment_frais_avec_notes_reste_utilisable_par_le_client(self) -> None:
        """Le bloc de notes n'empêche pas l'échange suivant d'aboutir."""
        espace, notes, contexte = self._monter_run()
        note_write(notes, GUIDE, "acquis")
        contexte.continuer("état", notes.pour_segment_frais(), "observation")
        resultat = LLMClient(contexte.config, dormir=lambda _: None).chat(
            _messages_chat_simple(), num_ctx=8192, num_predict=64, temperature=0
        )
        contexte.enregistrer_reponse(resultat)
        espace.metrique("continuation", segment=contexte.segment, notes=notes.resume())
        self.assertEqual(contexte.depassements_consecutifs, 0)
        derniere = espace.lire_metriques()[-1]
        self.assertEqual(derniere["notes"]["guide_caracteres"], len("acquis"))

    def test_aucun_contenu_de_note_dans_les_metriques(self) -> None:
        """§H4.6 : les métriques comptent, elles ne divulguent pas."""
        espace, notes, _ = self._monter_run()
        note_write(notes, GUIDE, "contenu confidentiel du guide")
        espace.metrique("notes", notes=notes.resume())
        self.assertNotIn("confidentiel", espace.metriques.read_text(encoding="utf-8"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
