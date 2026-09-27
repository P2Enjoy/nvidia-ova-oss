"""Durées de préremplissage et de génération du serveur dans la métrique `llm` (§H11.2).

@verifies docs/BACKLOG.md U31 — `prefill_ms` et `generation_ms` dans la métrique
          `llm`, seule lecture de l'effet de l'ordre du message (§H15.11)
@verifies docs/SPEC_HARNAIS.md §H11.2 (métrique `llm` : `duree_ms`, `prefill_ms`
          = `prompt_eval_duration`, `generation_ms` = `eval_duration`), §H4.3
          (compteurs et durées lus dans la réponse native)

Aucun réseau : transport scripté rendant les compteurs du serveur, workspace en
répertoire temporaire pour lire `metrics.jsonl`.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from avo.config import Config, Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP
from avo.loop.boucle import BoucleAgent
from avo.memory.notes import Notes
from avo.memory.workspace import Workspace
from avo.tools.registre import Outil, RegistreOutils


def _config(mode_contexte: str) -> Config:
    return charger(
        Mode.REJEU,
        env={
            "OLLAMA_HOST": "http://capture.invalide",
            "OLLAMA_API_KEY": "cle-de-test",
            "AVO_CONTEXT_MODE": mode_contexte,
            "AVO_GARDES": "false",
            "AVO_IDEATION_OUVERTURE": "false",
            "AVO_PLAN_LEDGER": "false",
        },
        racine=Path("/inexistant"),
    )


class _Environnement:
    def __init__(self) -> None:
        self.jouees: list[str] = []

    def observation(self) -> str:
        return "grille"

    def actions_disponibles(self) -> list[str]:
        return ["avance"]

    def derniere_issue(self) -> Any:
        return None

    def etat_terminal(self) -> str | None:
        return None

    def jouer(self, action: str, **parametres: Any) -> Any:
        self.jouees.append(action)
        return None


class _Transport:
    def __init__(self, reponses: list[dict[str, Any]]) -> None:
        self.reponses = list(reponses)

    def __call__(self, url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
        if not self.reponses:
            raise AssertionError("appel LLM de trop")
        return ReponseHTTP(200, json.dumps(self.reponses.pop(0)).encode())


def _reponse(contenu: str, tool_calls: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": contenu}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {
        "message": message,
        "done_reason": "stop",
        "prompt_eval_count": 9000,
        "eval_count": 120,
        "total_duration": 50_000_000_000,
        "prompt_eval_duration": 4_900_000_000,
        "eval_duration": 12_000_000_000,
    }


class TestDureesServeur(unittest.TestCase):
    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        self.environnement = _Environnement()

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def _boucle(self, mode: str, reponses: list[dict[str, Any]]) -> tuple[BoucleAgent, Workspace]:
        config = _config(mode)
        registre = RegistreOutils(
            [
                Outil(
                    nom="avance",
                    description="Joue une action d'environnement.",
                    parametres={"type": "object", "properties": {}},
                    fonction=self.environnement.jouer,
                    etiquettes=frozenset({"action"}),
                )
            ]
        )
        workspace = Workspace.ouvrir(config, "run-durees", racine=self.racine)
        client = LLMClient(config, transport=_Transport(reponses), dormir=lambda _: None)
        boucle = BoucleAgent(
            config,
            client,
            registre,
            self.environnement,
            Notes(self.racine / "notes"),
            workspace=workspace,
        )
        return boucle, workspace

    def _lignes_llm(self, workspace: Workspace) -> list[dict[str, Any]]:
        return [dict(ligne) for ligne in workspace.lire_metriques() if ligne.get("type") == "llm"]

    def test_mode_state_porte_prefill_et_generation(self) -> None:
        bloc = json.dumps({"state_patch": {"hypotheses": ["h"]}, "action": "avance"})
        boucle, workspace = self._boucle("state", [_reponse(f"```json\n{bloc}\n```")])
        boucle.jouer_tour(1)
        (ligne,) = self._lignes_llm(workspace)
        self.assertEqual(ligne["duree_ms"], 50_000)
        self.assertEqual(ligne["prefill_ms"], 4_900)
        self.assertEqual(ligne["generation_ms"], 12_000)

    def test_mode_transcript_porte_prefill_et_generation(self) -> None:
        appel = [{"function": {"name": "avance", "arguments": {}}}]
        boucle, workspace = self._boucle(
            "transcript",
            [_reponse("je planifie"), _reponse("j'agis", tool_calls=appel), _reponse("j'évalue")],
        )
        boucle.jouer_tour(1)
        lignes = self._lignes_llm(workspace)
        self.assertGreaterEqual(len(lignes), 2)
        for ligne in lignes:
            self.assertEqual(ligne["prefill_ms"], 4_900)
            self.assertEqual(ligne["generation_ms"], 12_000)


if __name__ == "__main__":
    unittest.main()
