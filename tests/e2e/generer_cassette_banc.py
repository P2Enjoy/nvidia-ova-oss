"""Générateur déterministe de la cassette E2E du banc a (épisode Entrepôt).

@verifies docs/BACKLOG.md U29a2 — adaptateur harnais + CLI `banc`
@verifies docs/SPEC_BANCS.md §S6.4 (E2E : scénario rejoué par cassette, épisode
          court, score attendu exact), §S1.4 (déterminisme : double génération
          comparée)
@verifies docs/SPEC_ARCAGI3.md §A8.5 (capture en deux passes, régénération
          identique octet à octet)

Même principe que `generer_cassette_etat.py` : une première passe capture les
corps réellement émis par la boucle complète sous gardes (transport scripté), la
seconde apparie chaque corps à la réponse de la politique parfaite. L'enveloppe
de réponse est celle réellement enregistrée sur le vrai endpoint (§H4.7).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from avo.bancs.skillexec.adaptateur import jouer_episode
from avo.bancs.skillexec.generation import generer_episode
from avo.config import Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP
from avo.memory.workspace import Workspace
from llm_replay.cassette import AUTH_VALIDE, Cassette, Exchange, RequestRecord, ResponseRecord
from tests.e2e.scenarios_banc import (
    ENV_EPINGLE_BANC,
    JETON,
    actions_parfaites,
    gabarit_reponse,
    reponse_pas,
)

#: Horodatage fixe : la régénération est identique octet à octet (§A8.5).
HORODATAGE = "2026-09-01T00:00:00+00:00"

CASSETTE_NOM = "e2e_banc_entrepot.jsonl"
DOSSIER_CASSETTES = Path("tests/fixtures/llm/cassettes")

#: Paramètres de l'épisode du scénario (§S2.2) — courts, score attendu exact 1.00.
SEED = 42
HORIZON = 6


def _capturer_corps(gabarit: dict[str, Any]) -> list[dict[str, Any]]:
    """Première passe : joue l'épisode et relève les corps réellement émis."""
    actions = actions_parfaites(generer_episode(SEED, HORIZON))
    corps_emis: list[dict[str, Any]] = []

    def transport(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
        corps_emis.append(json.loads(corps))
        reponse = reponse_pas(gabarit, actions[len(corps_emis) - 1])
        return ReponseHTTP(200, json.dumps(reponse).encode())

    environnement = {
        **ENV_EPINGLE_BANC,
        "OLLAMA_HOST": "http://capture.invalide",
        "OLLAMA_API_KEY": JETON,
    }
    config = charger(Mode.REJEU, env=environnement, racine=Path("/inexistant"))
    with tempfile.TemporaryDirectory() as dossier:
        espace = Workspace.ouvrir(config, "capture-banc", racine=Path(dossier))
        releve = jouer_episode(
            config,
            espace,
            seed=SEED,
            horizon=HORIZON,
            client_llm=LLMClient(config, transport=transport, dormir=lambda _: None),
        )
    if releve.score != 1.0 or releve.correctes != HORIZON:
        raise AssertionError(
            f"scénario banc : attendu {HORIZON}/{HORIZON} correctes (score 1.00), "
            f"obtenu {releve.correctes} correctes (score {releve.score:.2f})"
        )
    return corps_emis


def _cassette(gabarit: dict[str, Any], corps_emis: list[dict[str, Any]]) -> str:
    """Seconde passe : apparie chaque corps émis à la réponse de la politique."""
    actions = actions_parfaites(generer_episode(SEED, HORIZON))
    cassette = Cassette()
    for rang, corps in enumerate(corps_emis):
        cassette.ajouter(
            Exchange(
                request=RequestRecord.depuis("POST", "/api/chat", AUTH_VALIDE, corps),
                response=ResponseRecord(
                    status=200,
                    headers={"content-type": "application/json"},
                    body=reponse_pas(gabarit, actions[rang]),
                ),
                recorded_at=HORODATAGE,
                duration_ms=1,
            )
        )
    return "".join(json.dumps(echange.en_json(), ensure_ascii=False) + "\n" for echange in cassette)


def generer() -> str:
    """Génère deux fois, compare, et rend le contenu unique du scénario (§A8.5)."""
    gabarit = gabarit_reponse()
    premiere = _cassette(gabarit, _capturer_corps(gabarit))
    seconde = _cassette(gabarit, _capturer_corps(gabarit))
    if premiere != seconde:
        raise AssertionError(
            "scénario banc : deux générations diffèrent — le décor n'est pas "
            "déterministe, la cassette ne peut pas être seedée (§A8.5, §S1.4)"
        )
    return premiere


def main() -> int:
    contenu = generer()
    chemin = DOSSIER_CASSETTES / CASSETTE_NOM
    chemin.write_text(contenu, encoding="utf-8")
    print(f"  {CASSETTE_NOM} : {contenu.count(chr(10))} échanges, régénération vérifiée")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
