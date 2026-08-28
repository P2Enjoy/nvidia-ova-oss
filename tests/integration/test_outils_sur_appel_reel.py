"""Le routage d'outils face à l'appel RÉELLEMENT demandé par le modèle.

@verifies docs/BACKLOG.md U12 — Registre d'outils et dispatch
@verifies docs/SPEC_HARNAIS.md §H7.1 (exposition au modèle), §H7.2 (exécution,
          messages `role: tool`, garde), §H7.4 (erreurs rendues au modèle),
          §H4.3 (détection sur la présence de `tool_calls`)

L'appel d'outil n'est pas fabriqué : c'est celui que le vrai serveur a demandé,
rejoué depuis la cassette. Le registre le route jusqu'à un vrai outil de notes.
"""

from __future__ import annotations

import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from avo.config import Config, Mode, charger
from avo.context.transcript import Transcript
from avo.llm.client import LLMClient, ToolCall
from avo.memory.notes import (
    GUIDE,
    SCHEMA_NOTE_READ,
    SCHEMA_NOTE_WRITE,
    Notes,
    note_read,
    note_write,
)
from avo.tools.registre import PREFIXE_ERREUR, RegistreOutils, outil_depuis_schema
from llm_replay.record import OUTILS, _messages_chat_outils
from llm_replay.server import creer_serveur

CASSETTE = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")
CLE = "sk-cle-de-rejeu-des-outils"


class TestOutilsSurAppelReel(unittest.TestCase):
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
        self.notes = Notes(Path(self._dossier.name) / "notes")
        self.commandes: list[str] = []

        def run_shell(command: str) -> str:
            self.commandes.append(command)
            return f"(sortie simulée de « {command} »)"

        self.registre = RegistreOutils(
            [
                # Construit depuis le schéma ENREGISTRÉ, jamais retapé : c'est ce
                # qui garantit que le modèle reçoit le contrat sur lequel il a été
                # mesuré. Une description recopiée à la main diverge tôt ou tard.
                outil_depuis_schema(OUTILS[0], run_shell, ["action"]),
                outil_depuis_schema(
                    SCHEMA_NOTE_READ, lambda name: note_read(self.notes, name), ["notes"]
                ),
                outil_depuis_schema(
                    SCHEMA_NOTE_WRITE,
                    lambda name, content: note_write(self.notes, name, content),
                    ["notes"],
                ),
            ]
        )

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def _config(self) -> Config:
        return charger(
            Mode.REJEU,
            env={"OLLAMA_HOST": self.base, "OLLAMA_API_KEY": CLE},
            racine=Path("/inexistant"),
        )

    def _appel_reel(self) -> tuple[Config, list[ToolCall]]:
        config = self._config()
        resultat = LLMClient(config, dormir=lambda _: None).chat(
            _messages_chat_outils(), list(OUTILS), num_ctx=8192, num_predict=256, temperature=0
        )
        self.assertTrue(resultat.demande_outil, "le contrat enregistré porte un appel d'outil")
        return config, list(resultat.tool_calls)

    def test_l_appel_demande_par_le_vrai_modele_est_route_et_execute(self) -> None:
        config, appels = self._appel_reel()
        resultat = self.registre.executer(appels, Transcript.ouvrir("sys"), config.tool_steps_max)
        self.assertEqual(resultat.executes, 1)
        self.assertFalse(resultat.garde_franchie)
        self.assertEqual(self.commandes, ["ls /tmp"])
        message = resultat.transcript.pour_api()[-1]
        self.assertEqual(message["role"], "tool")
        self.assertEqual(message["name"], "run_shell")
        self.assertIn("ls /tmp", message["content"])

    def test_le_registre_expose_au_modele_le_meme_schema_qu_enregistre(self) -> None:
        """Le schéma envoyé doit être celui sur lequel le contrat a été mesuré."""
        expose = self.registre.schemas(["action"])
        self.assertEqual(expose, [dict(OUTILS[0])])

    def test_plusieurs_appels_produisent_plusieurs_messages_dans_l_ordre(self) -> None:
        config, appels = self._appel_reel()
        multiples = [
            *appels,
            ToolCall(nom="note_write", arguments={"name": GUIDE, "content": "acquis"}),
            ToolCall(nom="note_read", arguments={"name": GUIDE}),
        ]
        resultat = self.registre.executer(
            multiples, Transcript.ouvrir("sys"), config.tool_steps_max
        )
        messages = resultat.transcript.pour_api()[1:]
        self.assertEqual([m["name"] for m in messages], ["run_shell", "note_write", "note_read"])
        self.assertEqual(messages[-1]["content"], "acquis")
        self.assertEqual(self.notes.lire(GUIDE), "acquis")

    def test_un_appel_fautif_au_milieu_n_interrompt_pas_les_suivants(self) -> None:
        """§H7.4 : rien de ce que fait un outil n'interrompt le run."""
        config, appels = self._appel_reel()
        melange = [
            ToolCall(nom="note_read", arguments={"name": "INEXISTANTE"}),
            *appels,
            ToolCall(nom="outil_fantome", arguments={}),
            ToolCall(nom="note_write", arguments={"name": GUIDE, "content": "malgré tout"}),
        ]
        resultat = self.registre.executer(melange, Transcript.ouvrir("sys"), config.tool_steps_max)
        contenus = [m["content"] for m in resultat.transcript.pour_api()[1:]]
        self.assertEqual(len(contenus), 4)
        self.assertTrue(contenus[0].startswith(PREFIXE_ERREUR))
        self.assertIn("ls /tmp", contenus[1])
        self.assertTrue(contenus[2].startswith(f"{PREFIXE_ERREUR}: outil_inconnu"))
        self.assertEqual(self.notes.lire(GUIDE), "malgré tout")

    def test_la_garde_configuree_s_applique_a_l_execution(self) -> None:
        config = charger(
            Mode.REJEU,
            env={"OLLAMA_HOST": self.base, "OLLAMA_API_KEY": CLE, "AVO_TOOL_STEPS_MAX": "2"},
            racine=Path("/inexistant"),
        )
        self.assertEqual(config.tool_steps_max, 2)
        appels = [ToolCall(nom="note_read", arguments={"name": GUIDE}) for _ in range(5)]
        resultat = self.registre.executer(appels, Transcript.ouvrir("sys"), config.tool_steps_max)
        self.assertTrue(resultat.garde_franchie)
        self.assertEqual(resultat.executes, 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
