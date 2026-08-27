"""Détection de dérive : le vrai serveur répond-il encore comme la cassette le dit ?

@verifies docs/BACKLOG.md U4 — llm-replay
@verifies docs/SPEC_HARNAIS.md §H4.7 point 3 (un écart est un défaut, pas une cassette
          à réécrire en silence)

Exécuté par `make test-int-live` uniquement : exige OLLAMA_HOST et OLLAMA_API_KEY, et
appelle réellement l'endpoint. N'entre jamais dans `make check`.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from llm_replay.cassette import Cassette
from llm_replay.record import SCENARIOS, enregistrer_scenario

CASSETTE = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")

#: Champs dont la valeur varie légitimement d'un appel à l'autre : contenu généré,
#: durées, horodatages. La dérive se mesure sur la FORME du contrat, pas sur le texte
#: produit par un modèle non déterministe.
CHAMPS_VOLATILS = {
    "message",
    "created_at",
    "total_duration",
    "load_duration",
    "eval_duration",
    "prompt_eval_duration",
    "eval_count",
    "prompt_eval_count",
    "done_reason",
}


class TestDeriveDuContrat(unittest.TestCase):
    hote: str
    cle: str
    enregistre: Cassette

    @classmethod
    def setUpClass(cls) -> None:
        cls.hote = os.environ.get("OLLAMA_HOST", "")
        cls.cle = os.environ.get("OLLAMA_API_KEY", "")
        if not cls.hote or not cls.cle:
            raise unittest.SkipTest("OLLAMA_HOST/OLLAMA_API_KEY absents : test [LIVE] ignoré")
        if not CASSETTE.exists():
            raise unittest.SkipTest(f"cassette absente ({CASSETTE}) : lancer « make record-llm »")
        cls.enregistre = Cassette.lire(CASSETTE)

    def test_chaque_scenario_rend_le_meme_statut_et_la_meme_forme(self) -> None:
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario.nom):
                attendu = self.enregistre.apparier(
                    scenario.method, scenario.path, scenario.auth, scenario.construire()
                )
                obtenu = enregistrer_scenario(scenario, self.hote, self.cle)
                self.assertEqual(
                    obtenu.response.status,
                    attendu.response.status,
                    f"le statut du scénario « {scenario.nom} » a changé : "
                    f"{attendu.response.status} enregistré, {obtenu.response.status} obtenu. "
                    "C'est un défaut à traiter, pas une cassette à réécrire.",
                )
                if isinstance(attendu.response.body, dict) and isinstance(
                    obtenu.response.body, dict
                ):
                    cles_attendues = set(attendu.response.body) - CHAMPS_VOLATILS
                    cles_obtenues = set(obtenu.response.body) - CHAMPS_VOLATILS
                    self.assertEqual(
                        cles_attendues,
                        cles_obtenues,
                        f"la forme de la réponse du scénario « {scenario.nom} » a changé.",
                    )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
