"""Serveur de rejeu : sert les échanges enregistrés, et rien d'autre.

@spec docs/BACKLOG.md U4
@spec docs/SPEC_HARNAIS.md §H4.7 (rejeu, erreur explicite, injection de fautes)

Le serveur ne fabrique jamais de réponse. Il rejoue une entrée de cassette ou rend
une erreur nommant l'écart. Seules les fautes que le vrai serveur ne produit pas à
la demande (500, latence, coupure) sont injectables, via `/_fault`.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from llm_replay.cassette import AUTH_ABSENTE, AUTH_INVALIDE, AUTH_VALIDE, Cassette, RequeteInconnue

#: Chemin de pilotage des fautes. Hors contrat Ollama : préfixé pour ne jamais
#: entrer en collision avec une route réelle.
ROUTE_FAUTE = "/_fault"


@dataclass
class Faute:
    """Faute armée pour les prochaines requêtes appariées."""

    status: int | None = None
    delay_ms: int = 0
    cut: bool = False
    count: int = 0

    def consommer(self) -> Faute | None:
        if self.count <= 0:
            return None
        self.count -= 1
        return self


class EtatRejeu:
    """État partagé du serveur : cassette chargée et faute éventuellement armée."""

    def __init__(self, cassette: Cassette, cle_attendue: str | None = None) -> None:
        self.cassette = cassette
        self.cle_attendue = cle_attendue
        self.faute: Faute | None = None
        self.verrou = threading.Lock()

    def armer(self, faute: Faute) -> None:
        with self.verrou:
            self.faute = faute

    def prochaine_faute(self) -> Faute | None:
        with self.verrou:
            if self.faute is None:
                return None
            active = self.faute.consommer()
            if active is not None and self.faute.count <= 0:
                self.faute = None
            return active

    def nature_auth(self, entete: str | None) -> str:
        """Classe l'en-tête d'autorisation SANS jamais conserver la clé."""
        if not entete or not entete.startswith("Bearer "):
            return AUTH_ABSENTE
        jeton = entete.removeprefix("Bearer ").strip()
        if self.cle_attendue is None:
            return AUTH_VALIDE
        return AUTH_VALIDE if jeton == self.cle_attendue else AUTH_INVALIDE


class GestionnaireRejeu(BaseHTTPRequestHandler):
    """Gestionnaire HTTP du rejeu."""

    protocol_version = "HTTP/1.1"
    etat: EtatRejeu

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Silencieux : les tests n'ont pas besoin du journal d'accès."""

    def _repondre(self, status: int, corps: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def _erreur(self, status: int, message: str) -> None:
        corps = json.dumps({"error": message}, ensure_ascii=False).encode()
        self._repondre(status, corps, "application/json")

    def _corps_requete(self) -> Any:
        longueur = int(self.headers.get("Content-Length") or 0)
        if longueur == 0:
            return None
        brut = self.rfile.read(longueur)
        try:
            return json.loads(brut)
        except json.JSONDecodeError:
            return brut.decode(errors="replace")

    def do_GET(self) -> None:  # noqa: N802 — nom imposé par BaseHTTPRequestHandler
        self._servir("GET", None)

    def do_POST(self) -> None:  # noqa: N802 — nom imposé par BaseHTTPRequestHandler
        corps = self._corps_requete()
        if self.path == ROUTE_FAUTE:
            self._armer_faute(corps)
            return
        self._servir("POST", corps)

    def _armer_faute(self, corps: Any) -> None:
        if not isinstance(corps, dict):
            self._erreur(400, "corps de pilotage attendu : objet JSON")
            return
        self.etat.armer(
            Faute(
                status=corps.get("status"),
                delay_ms=int(corps.get("delay_ms", 0)),
                cut=bool(corps.get("cut", False)),
                count=int(corps.get("count", 1)),
            )
        )
        self._repondre(200, b'{"armed":true}', "application/json")

    def _servir(self, methode: str, corps: Any) -> None:
        faute = self.etat.prochaine_faute()
        if faute is not None:
            if faute.delay_ms:
                time.sleep(faute.delay_ms / 1000.0)
            if faute.cut:
                self.close_connection = True
                return
            if faute.status is not None:
                self._erreur(faute.status, "faute injectée par llm-replay")
                return
        auth = self.etat.nature_auth(self.headers.get("Authorization"))
        try:
            echange = self.etat.cassette.apparier(methode, self.path, auth, corps)
        except RequeteInconnue as erreur:
            self._erreur(599, str(erreur))
            return
        content_type = echange.response.headers.get("content-type", "application/json")
        self._repondre(echange.response.status, echange.response.corps_octets(), content_type)


def creer_serveur(
    dossier_cassettes: Path, port: int = 0, cle_attendue: str | None = None
) -> ThreadingHTTPServer:
    """Crée un serveur de rejeu. `port=0` alloue un port éphémère (tests)."""
    cassette = Cassette.lire_dossier(dossier_cassettes)
    etat = EtatRejeu(cassette, cle_attendue)
    gestionnaire = type("GestionnaireLie", (GestionnaireRejeu,), {"etat": etat})
    return ThreadingHTTPServer(("127.0.0.1", port), gestionnaire)
