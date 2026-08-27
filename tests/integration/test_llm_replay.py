"""Preuves d'intégration du serveur de rejeu : vrai HTTP, port éphémère.

@verifies docs/BACKLOG.md U4 — llm-replay : enregistrement et rejeu
@verifies docs/SPEC_HARNAIS.md §H4.7 (rejeu fidèle, erreur explicite, injection de fautes)

Aucun réseau externe, aucun secret : le serveur ne sert que des échanges déjà
enregistrés, et refuse explicitement tout ce qu'il n'a pas.
"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from llm_replay.cassette import (
    AUTH_ABSENTE,
    AUTH_VALIDE,
    Cassette,
    Exchange,
    RequestRecord,
    ResponseRecord,
)
from llm_replay.server import creer_serveur

_CLE = "cle-de-test"
_CORPS_CHAT = {"model": "m", "messages": [{"role": "user", "content": "bonjour"}]}


def _cassette_de_reference() -> Cassette:
    return Cassette(
        [
            Exchange(
                request=RequestRecord.depuis("GET", "/api/version", AUTH_ABSENTE, None),
                response=ResponseRecord(
                    status=401,
                    headers={"content-type": "application/json"},
                    body={"error": "clé API manquante"},
                ),
                recorded_at="2026-08-27T00:00:00+00:00",
                duration_ms=3,
            ),
            Exchange(
                request=RequestRecord.depuis("GET", "/api/version", AUTH_VALIDE, None),
                response=ResponseRecord(
                    status=200,
                    headers={"content-type": "application/json"},
                    body={"version": "0.32.14"},
                ),
                recorded_at="2026-08-27T00:00:00+00:00",
                duration_ms=4,
            ),
            Exchange(
                request=RequestRecord.depuis("POST", "/api/chat", AUTH_VALIDE, _CORPS_CHAT),
                response=ResponseRecord(
                    status=200,
                    headers={"content-type": "application/json"},
                    body={"message": {"role": "assistant", "content": "OK-AVO"}, "done": True},
                ),
                recorded_at="2026-08-27T00:00:00+00:00",
                duration_ms=6600,
            ),
        ]
    )


class TestRejeu(unittest.TestCase):
    serveur: ThreadingHTTPServer
    fil: threading.Thread
    dossier: tempfile.TemporaryDirectory[str]
    base: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.dossier = tempfile.TemporaryDirectory()
        racine = Path(cls.dossier.name)
        _cassette_de_reference().ecrire(racine / "contrat.jsonl")
        cls.serveur = creer_serveur(racine, port=0, cle_attendue=_CLE)
        hote, port = cls.serveur.server_address[0], cls.serveur.server_address[1]
        cls.base = f"http://{hote!s}:{port}"
        cls.fil = threading.Thread(target=cls.serveur.serve_forever, daemon=True)
        cls.fil.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.serveur.shutdown()
        cls.serveur.server_close()
        cls.fil.join(timeout=5)
        cls.dossier.cleanup()

    def _appeler(
        self,
        method: str,
        chemin: str,
        corps: Any = None,
        cle: str | None = _CLE,
        timeout: float = 10.0,
    ) -> tuple[int, Any]:
        donnees = json.dumps(corps).encode() if corps is not None else None
        requete = urllib.request.Request(self.base + chemin, data=donnees, method=method)  # noqa: S310
        if donnees is not None:
            requete.add_header("Content-Type", "application/json")
        if cle is not None:
            requete.add_header("Authorization", f"Bearer {cle}")
        try:
            with urllib.request.urlopen(requete, timeout=timeout) as reponse:  # noqa: S310
                return int(reponse.status), json.loads(reponse.read())
        except urllib.error.HTTPError as erreur:
            return int(erreur.code), json.loads(erreur.read())

    def test_rejoue_la_reponse_enregistree(self) -> None:
        statut, corps = self._appeler("GET", "/api/version")
        self.assertEqual(statut, 200)
        self.assertEqual(corps, {"version": "0.32.14"})

    def test_rejoue_le_refus_reel_sans_cle(self) -> None:
        statut, corps = self._appeler("GET", "/api/version", cle=None)
        self.assertEqual(statut, 401)
        self.assertEqual(corps["error"], "clé API manquante")

    def test_une_cle_differente_est_une_autre_nature_d_authentification(self) -> None:
        statut, corps = self._appeler("GET", "/api/version", cle="mauvaise-cle")
        self.assertEqual(statut, 599)
        self.assertIn("aucun échange enregistré", corps["error"])

    def test_rejoue_un_echange_de_conversation(self) -> None:
        statut, corps = self._appeler("POST", "/api/chat", _CORPS_CHAT)
        self.assertEqual(statut, 200)
        self.assertEqual(corps["message"]["content"], "OK-AVO")

    def test_requete_non_enregistree_rend_une_erreur_explicite(self) -> None:
        statut, corps = self._appeler("POST", "/api/chat", {"model": "m", "messages": []})
        self.assertEqual(statut, 599)
        self.assertIn("aucun échange enregistré ne correspond", corps["error"])
        self.assertIn("make record-llm", corps["error"])


class TestInjectionDeFautes(unittest.TestCase):
    serveur: ThreadingHTTPServer
    fil: threading.Thread
    dossier: tempfile.TemporaryDirectory[str]
    base: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.dossier = tempfile.TemporaryDirectory()
        racine = Path(cls.dossier.name)
        _cassette_de_reference().ecrire(racine / "contrat.jsonl")
        cls.serveur = creer_serveur(racine, port=0, cle_attendue=_CLE)
        hote, port = cls.serveur.server_address[0], cls.serveur.server_address[1]
        cls.base = f"http://{hote!s}:{port}"
        cls.fil = threading.Thread(target=cls.serveur.serve_forever, daemon=True)
        cls.fil.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.serveur.shutdown()
        cls.serveur.server_close()
        cls.fil.join(timeout=5)
        cls.dossier.cleanup()

    def _armer(self, **faute: Any) -> None:
        requete = urllib.request.Request(  # noqa: S310
            self.base + "/_fault", data=json.dumps(faute).encode(), method="POST"
        )
        requete.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(requete, timeout=10) as reponse:  # noqa: S310
            self.assertEqual(int(reponse.status), 200)

    def _version(self) -> int:
        requete = urllib.request.Request(self.base + "/api/version", method="GET")  # noqa: S310
        requete.add_header("Authorization", f"Bearer {_CLE}")
        try:
            with urllib.request.urlopen(requete, timeout=10) as reponse:  # noqa: S310
                return int(reponse.status)
        except urllib.error.HTTPError as erreur:
            return int(erreur.code)

    def test_faute_500_puis_retour_a_la_normale(self) -> None:
        self._armer(status=500, count=1)
        self.assertEqual(self._version(), 500)
        self.assertEqual(self._version(), 200)

    def test_faute_appliquee_le_nombre_de_fois_demande(self) -> None:
        self._armer(status=500, count=2)
        self.assertEqual(self._version(), 500)
        self.assertEqual(self._version(), 500)
        self.assertEqual(self._version(), 200)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
