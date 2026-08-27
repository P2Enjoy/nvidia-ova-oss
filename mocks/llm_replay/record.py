"""Enregistreur : appelle le VRAI endpoint et capture ses échanges.

@spec docs/BACKLOG.md U4
@spec docs/SPEC_HARNAIS.md §H4.7 (enregistrement, expurgation), §H4.6 (aucun secret)

Les scénarios ci-dessous sont exactement les échanges déjà mesurés à la main le
2026-08-27 (docs/JOURNAL.md) : ils fixent le contrat sur lequel le client U7 sera
éprouvé. Rien n'est fabriqué — le serveur réel répond, on note ce qu'il dit.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llm_replay.cassette import (
    AUTH_ABSENTE,
    AUTH_INVALIDE,
    AUTH_VALIDE,
    ENTETES_RETENUS,
    Cassette,
    Exchange,
    RequestRecord,
    ResponseRecord,
)

#: Clé volontairement invalide, utilisée pour enregistrer un vrai refus du serveur.
CLE_INVALIDE = "sk-ollama-cle-deliberement-invalide-pour-enregistrement"

#: Longueur du prompt de dépassement, calibrée pour franchir le plafond par clé
#: mesuré le 2026-08-27 (229 376 tokens, marge de 15 % appliquée par le proxy).
LIGNES_DEPASSEMENT = 40000


@dataclass(frozen=True)
class Scenario:
    """Un échange à enregistrer contre le vrai serveur."""

    nom: str
    method: str
    path: str
    auth: str
    corps: Callable[[], Any] | None = None

    def construire(self) -> Any:
        return self.corps() if self.corps is not None else None


def _corps_chat_simple() -> dict[str, Any]:
    return {
        "model": "qwen3.6:35b",
        "stream": False,
        "think": False,
        "options": {"num_ctx": 8192, "num_predict": 64, "temperature": 0},
        "messages": [{"role": "user", "content": "Réponds exactement par le jeton : OK-AVO"}],
    }


def _corps_chat_outils() -> dict[str, Any]:
    return {
        "model": "qwen3.6:35b",
        "stream": False,
        "think": False,
        "options": {"num_ctx": 8192, "num_predict": 256, "temperature": 0},
        "messages": [{"role": "user", "content": "Liste /tmp en utilisant l'outil disponible."}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "run_shell",
                    "description": "Exécute une commande shell et renvoie sa sortie",
                    "parameters": {
                        "type": "object",
                        "properties": {"command": {"type": "string"}},
                        "required": ["command"],
                    },
                },
            }
        ],
    }


def _corps_chat_trop_grand() -> dict[str, Any]:
    lignes = [
        f"ENTREE {n}: parametre alpha={n % 97} statut=nominal." for n in range(LIGNES_DEPASSEMENT)
    ]
    return {
        "model": "qwen3.6:35b",
        "stream": False,
        "think": False,
        "options": {"num_ctx": 8192, "num_predict": 16},
        "messages": [{"role": "user", "content": "\n".join(lignes)}],
    }


#: Contrat de référence de l'endpoint. Chaque entrée produit un échange réel.
SCENARIOS: tuple[Scenario, ...] = (
    Scenario("version_sans_cle", "GET", "/api/version", AUTH_ABSENTE),
    Scenario("version_avec_cle", "GET", "/api/version", AUTH_VALIDE),
    Scenario("tags", "GET", "/api/tags", AUTH_VALIDE),
    Scenario("chat_simple", "POST", "/api/chat", AUTH_VALIDE, _corps_chat_simple),
    Scenario("chat_outils", "POST", "/api/chat", AUTH_VALIDE, _corps_chat_outils),
    Scenario("chat_cle_invalide", "POST", "/api/chat", AUTH_INVALIDE, _corps_chat_simple),
    Scenario("chat_contexte_trop_grand", "POST", "/api/chat", AUTH_VALIDE, _corps_chat_trop_grand),
)


def _entete_auth(nature: str, cle: str) -> str | None:
    if nature == AUTH_ABSENTE:
        return None
    if nature == AUTH_INVALIDE:
        return f"Bearer {CLE_INVALIDE}"
    return f"Bearer {cle}"


def enregistrer_scenario(
    scenario: Scenario, hote: str, cle: str, timeout: float = 900.0
) -> Exchange:
    """Exécute un scénario contre le VRAI serveur et rend l'échange capturé."""
    corps = scenario.construire()
    donnees = json.dumps(corps).encode() if corps is not None else None
    requete = urllib.request.Request(  # noqa: S310 — hôte fourni par la configuration
        url=f"{hote.rstrip('/')}{scenario.path}",
        data=donnees,
        method=scenario.method,
    )
    if donnees is not None:
        requete.add_header("Content-Type", "application/json")
    entete = _entete_auth(scenario.auth, cle)
    if entete is not None:
        requete.add_header("Authorization", entete)

    debut = time.monotonic()
    try:
        with urllib.request.urlopen(requete, timeout=timeout) as reponse:  # noqa: S310
            statut = int(reponse.status)
            entetes = {
                k.lower(): v for k, v in reponse.headers.items() if k.lower() in ENTETES_RETENUS
            }
            brut = reponse.read()
    except urllib.error.HTTPError as erreur:
        statut = int(erreur.code)
        entetes = {k.lower(): v for k, v in erreur.headers.items() if k.lower() in ENTETES_RETENUS}
        brut = erreur.read()
    duree_ms = int((time.monotonic() - debut) * 1000)

    try:
        corps_reponse: Any = json.loads(brut)
        texte: str | None = None
    except json.JSONDecodeError:
        corps_reponse = None
        texte = brut.decode(errors="replace")

    return Exchange(
        request=RequestRecord.depuis(scenario.method, scenario.path, scenario.auth, corps),
        response=ResponseRecord(status=statut, headers=entetes, body=corps_reponse, text=texte),
        recorded_at=datetime.now(UTC).isoformat(timespec="seconds"),
        duration_ms=duree_ms,
    )


def enregistrer_tout(hote: str, cle: str, destination: Path) -> Cassette:
    """Enregistre tous les scénarios du contrat et écrit la cassette."""
    cassette = Cassette()
    for scenario in SCENARIOS:
        echange = enregistrer_scenario(scenario, hote, cle)
        cassette.ajouter(echange)
        print(
            f"  {scenario.nom:28s} → HTTP {echange.response.status} en {echange.duration_ms} ms",
            flush=True,
        )
    cassette.ecrire(destination)
    return cassette
