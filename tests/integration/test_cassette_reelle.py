"""Le contrat RÉELLEMENT enregistré se rejoue-t-il fidèlement ?

@verifies docs/BACKLOG.md U4 — llm-replay
@verifies docs/SPEC_HARNAIS.md §H4.7 (aller-retour enregistrement → rejeu)

Ce test ne fabrique aucune donnée : il rejoue la cassette capturée sur le vrai
endpoint par « make record-llm ». Il tourne hors ligne et sans secret — la cassette
est expurgée — et prouve que le contrat mesuré est exploitable par les tests.
"""

from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from llm_replay.cassette import AUTH_ABSENTE, AUTH_INVALIDE, AUTH_VALIDE, Cassette
from llm_replay.record import CLE_INVALIDE, SCENARIOS
from llm_replay.server import creer_serveur

CASSETTE = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")
CLE = "cle-de-rejeu"


class TestCassetteReelle(unittest.TestCase):
    serveur: ThreadingHTTPServer
    fil: threading.Thread
    base: str
    enregistre: Cassette

    @classmethod
    def setUpClass(cls) -> None:
        if not CASSETTE.exists():
            raise unittest.SkipTest(f"cassette absente ({CASSETTE}) : lancer « make record-llm »")
        cls.enregistre = Cassette.lire(CASSETTE)
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

    def _jouer(self, method: str, chemin: str, auth: str, corps: Any) -> tuple[int, Any]:
        donnees = json.dumps(corps).encode() if corps is not None else None
        requete = urllib.request.Request(self.base + chemin, data=donnees, method=method)  # noqa: S310
        if donnees is not None:
            requete.add_header("Content-Type", "application/json")
        if auth == AUTH_VALIDE:
            requete.add_header("Authorization", f"Bearer {CLE}")
        elif auth == AUTH_INVALIDE:
            requete.add_header("Authorization", f"Bearer {CLE_INVALIDE}")
        try:
            with urllib.request.urlopen(requete, timeout=30) as reponse:  # noqa: S310
                return int(reponse.status), json.loads(reponse.read())
        except urllib.error.HTTPError as erreur:
            return int(erreur.code), json.loads(erreur.read())

    def test_les_sept_scenarios_enregistres_se_rejouent_a_l_identique(self) -> None:
        self.assertEqual(len(self.enregistre), len(SCENARIOS))
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario.nom):
                attendu = self.enregistre.apparier(
                    scenario.method, scenario.path, scenario.auth, scenario.construire()
                )
                statut, corps = self._jouer(
                    scenario.method, scenario.path, scenario.auth, scenario.construire()
                )
                self.assertEqual(statut, attendu.response.status)
                self.assertEqual(corps, attendu.response.body)

    def test_le_refus_sans_cle_est_bien_celui_du_vrai_serveur(self) -> None:
        statut, corps = self._jouer("GET", "/api/version", AUTH_ABSENTE, None)
        self.assertEqual(statut, 401)
        self.assertIn("error", corps)

    def test_le_413_porte_le_plafond_par_cle_dont_le_harnais_depend(self) -> None:
        """H3.2 et H5.4 budgètent sur ces champs : ils doivent exister dans le contrat."""
        depassement = next(e for e in self.enregistre if e.response.status == 413)
        corps = depassement.response.body
        assert isinstance(corps, dict)
        self.assertIn("max_context_tokens", corps)
        self.assertIn("tokens_estimated", corps)
        self.assertGreater(int(corps["max_context_tokens"]), 0)

    def test_la_conversation_avec_outils_a_bien_produit_un_appel_d_outil(self) -> None:
        """Prérequis dur de la boucle agent (H8) : le contrat doit le montrer."""
        avec_outils = self.enregistre.apparier(
            "POST", "/api/chat", AUTH_VALIDE, SCENARIOS[4].construire()
        )
        corps = avec_outils.response.body
        assert isinstance(corps, dict)
        self.assertIn("tool_calls", corps["message"])
        self.assertTrue(corps["message"]["tool_calls"])

    def test_la_cassette_ne_contient_aucun_secret(self) -> None:
        contenu = CASSETTE.read_text(encoding="utf-8")
        for interdit in ("Authorization", "Bearer ", "sk-ollama-5b"):
            self.assertNotIn(interdit, contenu)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
