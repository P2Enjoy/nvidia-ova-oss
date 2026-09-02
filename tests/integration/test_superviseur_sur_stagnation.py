"""Le superviseur face à une stagnation, contre le rejeu HTTP réel.

@verifies docs/BACKLOG.md U15 — Superviseur
@verifies docs/SPEC_HARNAIS.md §H10.2 (déclencheurs), §H10.3 (intervention, cooldown,
          journalisation dans metrics.jsonl), §H5.1 (injection append-only)
@verifies docs/SPEC_HARNAIS.md §H6.1 (le run porte la trace de l'intervention)

L'appel du superviseur passe par le vrai client et le vrai serveur de rejeu : c'est
un appel LLM séparé, avec son propre contexte, comme en production.
"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from collections.abc import Callable, Mapping
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from avo.config import Config, Mode, charger
from avo.context.transcript import Transcript
from avo.llm.client import LLMClient, ReponseHTTP
from avo.memory.notes import GUIDE, Notes, note_write
from avo.memory.workspace import Workspace
from avo.supervisor import BALISE, Superviseur
from llm_replay.cassette import (
    AUTH_VALIDE,
    Cassette,
    Exchange,
    RequestRecord,
    ResponseRecord,
    premiere_conversation,
)
from llm_replay.server import creer_serveur

CASSETTE_REELLE = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")
CLE = "sk-cle-de-rejeu-du-superviseur"
DIRECTIVE = "Tu répètes la même action : explore le bord opposé de la grille."


def _gabarit() -> dict[str, Any]:
    return premiere_conversation(Cassette.lire(CASSETTE_REELLE))


class TestSuperviseurSurStagnation(unittest.TestCase):
    serveur: ThreadingHTTPServer | None = None

    def setUp(self) -> None:
        if not CASSETTE_REELLE.exists():
            self.skipTest("cassette absente : lancer « make record-llm »")
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)

    def tearDown(self) -> None:
        if self.serveur is not None:
            self.serveur.shutdown()
            self.serveur.server_close()
            self.fil.join(timeout=5)
            self.serveur = None
        self._dossier.cleanup()

    def _config(self, base: str, **surcharges: str) -> Config:
        env = {"OLLAMA_HOST": base, "OLLAMA_API_KEY": CLE, **surcharges}
        return charger(Mode.REJEU, env=env, racine=Path("/inexistant"))

    def _monter(self, corps_attendus: list[dict[str, Any]]) -> str:
        """Sert une réponse de superviseur pour chaque requête attendue."""
        cassette = Cassette()
        for corps in corps_attendus:
            reponse = _gabarit()
            reponse["message"]["content"] = DIRECTIVE
            reponse["message"].pop("tool_calls", None)
            cassette.ajouter(
                Exchange(
                    request=RequestRecord.depuis("POST", "/api/chat", AUTH_VALIDE, corps),
                    response=ResponseRecord(
                        status=200, headers={"content-type": "application/json"}, body=reponse
                    ),
                    recorded_at="2026-08-28T00:00:00+00:00",
                    duration_ms=1,
                )
            )
        chemin = self.racine / "superviseur.jsonl"
        cassette.ecrire(chemin)
        self.serveur = creer_serveur(chemin.parent, port=0, cle_attendue=CLE)
        hote, port = self.serveur.server_address[0], self.serveur.server_address[1]
        self.fil = threading.Thread(target=self.serveur.serve_forever, daemon=True)
        self.fil.start()
        return f"http://{hote!s}:{port}"

    def _rejouer(
        self,
        scenario: Callable[[Superviseur, Notes], None],
        stagnation: int = 5,
        cooldown: int = 10,
    ) -> tuple[Superviseur, Workspace, Notes]:
        """Exécute le MÊME scénario deux fois : capture des corps, puis service HTTP.

        Faire exécuter aux deux passes exactement le même enchaînement est la seule
        façon d'obtenir des corps identiques : un motif ou une note qui différerait
        suffirait à ce qu'aucun échange ne s'apparie.
        """
        emis: list[dict[str, Any]] = []

        def capture(
            url: str, corps: bytes, entetes: Mapping[str, str], timeout: float
        ) -> ReponseHTTP:
            emis.append(json.loads(corps))
            reponse = _gabarit()
            reponse["message"]["content"] = DIRECTIVE
            reponse["message"].pop("tool_calls", None)
            return ReponseHTTP(200, json.dumps(reponse).encode())

        surcharges = {
            "AVO_SUP_STALL_ACTIONS": str(stagnation),
            "AVO_SUP_COOLDOWN": str(cooldown),
        }
        config_capture = charger(
            Mode.REJEU,
            env={"OLLAMA_HOST": "http://capture.invalide", "OLLAMA_API_KEY": CLE, **surcharges},
            racine=Path("/inexistant"),
        )
        espace_temoin = Workspace.ouvrir(config_capture, "capture", racine=self.racine)
        notes_temoin = Notes(espace_temoin.notes)
        note_write(notes_temoin, GUIDE, "mes acquis")
        scenario(
            Superviseur(
                config_capture,
                LLMClient(config_capture, transport=capture, dormir=lambda _: None),
            ),
            notes_temoin,
        )

        base = self._monter(emis)
        config = self._config(base, **surcharges)
        espace = Workspace.ouvrir(config, "run-superviseur", racine=self.racine)
        notes = Notes(espace.notes)
        note_write(notes, GUIDE, "mes acquis")
        return Superviseur(config, LLMClient(config, dormir=lambda _: None)), espace, notes

    def _stagner(self, superviseur: Superviseur, actions: int) -> None:
        for n in range(actions):
            superviseur.trajectoire.enregistrer("avance", f"frame{n}")

    def _scenario_stagnation(self, superviseur: Superviseur, notes: Notes) -> None:
        """Stagner jusqu'au déclenchement, puis intervenir sur le motif calculé."""
        self._stagner(superviseur, 5)
        motif = superviseur.doit_intervenir()
        assert motif is not None
        superviseur.intervenir(
            Transcript.ouvrir("sys").utilisateur("observation"),
            motif,
            notes.pour_segment_frais(),
            "grille",
        )

    def test_la_stagnation_declenche_une_intervention_reelle(self) -> None:
        superviseur, espace, notes = self._rejouer(self._scenario_stagnation)
        self._stagner(superviseur, 5)
        motif = superviseur.doit_intervenir()
        self.assertIsNotNone(motif)

        transcript = Transcript.ouvrir("sys").utilisateur("observation")
        avant = transcript
        transcript, intervention = superviseur.intervenir(
            transcript, str(motif), notes.pour_segment_frais(), "grille"
        )
        self.assertEqual(intervention.directive, DIRECTIVE)
        self.assertTrue(transcript.prolonge(avant))
        self.assertTrue(transcript.pour_api()[-1]["content"].startswith(BALISE))

        espace.metrique("superviseur", superviseur=superviseur.resume())
        derniere = espace.lire_metriques()[-1]
        self.assertEqual(derniere["superviseur"]["interventions"], 1)
        self.assertIn("stagnation", derniere["superviseur"]["motifs"][0])

    def test_le_cooldown_est_respecte_sur_une_trajectoire_reelle(self) -> None:
        superviseur, _, notes = self._rejouer(self._scenario_stagnation)
        self._stagner(superviseur, 5)
        motif = str(superviseur.doit_intervenir())
        superviseur.intervenir(
            Transcript.ouvrir("sys").utilisateur("observation"),
            motif,
            notes.pour_segment_frais(),
            "grille",
        )
        self._stagner(superviseur, 4)
        self.assertIsNone(superviseur.doit_intervenir(), "le cooldown doit bloquer")
        self.assertEqual(len(superviseur.interventions), 1)

    def test_le_motif_est_journalise_dans_les_metriques(self) -> None:
        superviseur, espace, notes = self._rejouer(self._scenario_stagnation)
        self._stagner(superviseur, 5)
        motif = str(superviseur.doit_intervenir())
        superviseur.intervenir(
            Transcript.ouvrir("sys").utilisateur("observation"),
            motif,
            notes.pour_segment_frais(),
            "grille",
        )
        espace.metrique("superviseur", motif=motif, superviseur=superviseur.resume())
        contenu = espace.metriques.read_text(encoding="utf-8")
        self.assertIn("stagnation", contenu)
        self.assertNotIn(DIRECTIVE, contenu, "la directive ne va pas dans les métriques")

    def test_les_notes_de_l_acteur_parviennent_au_superviseur(self) -> None:
        """§H10.3 : il reçoit un résumé factuel et les notes, pas l'historique."""
        superviseur, _, notes = self._rejouer(self._scenario_stagnation)
        self._stagner(superviseur, 5)
        motif = str(superviseur.doit_intervenir())
        transcript, _ = superviseur.intervenir(
            Transcript.ouvrir("sys").utilisateur("observation"),
            motif,
            notes.pour_segment_frais(),
            "grille",
        )
        self.assertEqual(len(superviseur.interventions), 1)
        self.assertIn(BALISE, transcript.pour_api()[-1]["content"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
