"""Verdicts de la garde d'évaluation écrits dans la métrique `garde`, chemin nominal compris.

@verifies docs/BACKLOG.md U31 — amélioration de l'observation sur mesure acquise
          (journal des 2026-09-29 et 2026-09-30 : répartition des verdicts
          comptée à la main dans les pas archivés sur tr87, re86 et cd82)
@verifies docs/SPEC_HARNAIS.md §H16.5 (une ligne `garde` par prédiction qualifiée :
          confirmee, contredite, caduque pour un verdict explicite, forcee pour
          l'issue prudente — jamais deux lignes pour une même prédiction ; le
          premier pas, sans prédiction, n'écrit rien), §H16.3 (les trois issues)
@verifies docs/SPEC_ARCAGI3.md §A7.3 (le rapport porte la répartition : confirmées,
          contredites dont forcées, caduques, redemandes)

Aucun réseau : boucle au transport scripté, environnement factice, workspace en
répertoire temporaire relu après coup — dans les deux modes de contexte.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from avo.arc.rapport import inference_par_appel
from avo.config import Config, Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP
from avo.loop.boucle import BoucleAgent
from avo.loop.etats import Evenement
from avo.memory.notes import WORKING, Notes
from avo.memory.workspace import Workspace
from avo.tools.registre import Outil, RegistreOutils


def _config(racine: Path, **env: str) -> Config:
    return charger(
        Mode.REJEU,
        env={
            "OLLAMA_HOST": "http://capture.invalide",
            "OLLAMA_API_KEY": "sk-cle-verdicts",
            "AVO_IDEATION_OUVERTURE": "false",
            "AVO_PLAN_LEDGER": "false",
            **env,
        },
        racine=racine,
    )


@dataclass
class _Issue:
    observation: str
    evenement: Evenement


class _Environnement:
    def __init__(self) -> None:
        self.jouees: list[tuple[str, dict[str, Any]]] = []
        self._derniere: _Issue | None = None

    def observation(self) -> str:
        return f"grille-{len(self.jouees)}"

    def actions_disponibles(self) -> list[str]:
        return ["avance"]

    def derniere_issue(self) -> _Issue | None:
        return self._derniere

    def etat_terminal(self) -> str | None:
        return None

    def jouer(self, action: str, **parametres: Any) -> _Issue:
        self.jouees.append((action, parametres))
        self._derniere = _Issue(f"grille-{len(self.jouees)}", Evenement.PREDICTION_CONFIRMEE)
        return self._derniere


def _corps(contenu: str, tool_calls: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": contenu}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {
        "message": message,
        "done_reason": "stop",
        "prompt_eval_count": 10,
        "eval_count": 5,
        "total_duration": 1_000_000,
    }


def _appel(nom: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {"function": {"name": nom, "arguments": arguments}}


class _TransportScripte:
    def __init__(self, reponses: list[dict[str, Any]]) -> None:
        self.reponses = list(reponses)

    def __call__(self, url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
        if not self.reponses:
            raise AssertionError("plus de réponse scriptée : appel LLM de trop")
        return ReponseHTTP(200, json.dumps(self.reponses.pop(0)).encode())


class _Decor(unittest.TestCase):
    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        self.notes = Notes(self.racine / "notes")
        self.environnement = _Environnement()

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def _registre(self) -> RegistreOutils:
        def avance(prediction: str | None = None) -> str:
            self.environnement.jouer("avance", prediction=prediction)
            return "action jouée"

        return RegistreOutils(
            [
                Outil(
                    nom="avance",
                    description="Joue une action d'environnement",
                    parametres={
                        "type": "object",
                        "properties": {"prediction": {"type": "string"}},
                    },
                    fonction=avance,
                    etiquettes=frozenset({"action"}),
                )
            ]
        )

    def _boucle(self, reponses: list[dict[str, Any]], **env: str) -> tuple[BoucleAgent, Workspace]:
        config = _config(self.racine, **env)
        workspace = Workspace.ouvrir(config, "run-test", racine=self.racine)
        client = LLMClient(config, transport=_TransportScripte(reponses), dormir=lambda _: None)
        boucle = BoucleAgent(
            config, client, self._registre(), self.environnement, self.notes, workspace=workspace
        )
        return boucle, workspace

    @staticmethod
    def _verdicts(workspace: Workspace) -> list[str]:
        chemin = workspace.chemin / "metrics.jsonl"
        if not chemin.exists():
            return []
        return [
            str(ligne["issue"])
            for ligne in (json.loads(brut) for brut in chemin.read_text().splitlines())
            if ligne.get("type") == "garde" and ligne.get("garde") == "evaluation"
        ]


class TestVerdictsModeEtat(_Decor):
    """§H16.5 en mode `state` : une ligne par prédiction qualifiée, rien au premier pas."""

    @staticmethod
    def _pas(texte_avant: str) -> dict[str, Any]:
        bloc = json.dumps({"state_patch": {"hypotheses": ["h"]}, "action": "avance"})
        return _corps(f"{texte_avant}\n```json\n{bloc}\n```")

    def test_chaque_verdict_explicite_s_ecrit_et_le_premier_pas_n_ecrit_rien(self) -> None:
        boucle, workspace = self._boucle(
            [
                self._pas("PREDICTION: p1"),
                self._pas("VERDICT: confirmee\nPREDICTION: p2"),
                self._pas("VERDICT: contredite\nPREDICTION: p3"),
                self._pas("VERDICT: non applicable\nPREDICTION: p4"),
            ],
            AVO_CONTEXT_MODE="state",
        )
        for numero in range(1, 5):
            self.assertEqual(boucle.jouer_tour(numero).action, "avance")
        self.assertEqual(
            self._verdicts(workspace),
            ["confirmee", "contredite", "caduque"],
            "une ligne par prédiction qualifiée, dans l'ordre, et aucune au premier pas",
        )

    def test_l_issue_prudente_s_ecrit_forcee_et_une_seule_fois(self) -> None:
        boucle, workspace = self._boucle(
            [
                self._pas("PREDICTION: p1"),
                self._pas("PREDICTION: p2"),
                self._pas("PREDICTION: p3"),
            ],
            AVO_CONTEXT_MODE="state",
            AVO_GARDE_RETRIES="1",
        )
        boucle.jouer_tour(1)
        self.assertIsNone(boucle.jouer_tour(2).action, "verdict manquant : redemandé")
        troisieme = boucle.jouer_tour(3)
        self.assertIs(troisieme.evenement, Evenement.CONTRADICTION)
        self.assertEqual(
            self._verdicts(workspace),
            ["redemandee", "forcee"],
            "la prédiction réputée contredite s'écrit « forcee », jamais aussi « contredite »",
        )


class TestVerdictsModeTranscript(_Decor):
    """§H16.5 en mode `transcript` : le verdict de l'Evaluation s'écrit, nominal compris."""

    def setUp(self) -> None:
        super().setUp()
        self.notes.ecrire(WORKING, "artefact documentaire présent")

    def _tour(self, *evaluations: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            _corps("je planifie"),
            _corps("j'agis", [_appel("avance", {"prediction": "la case s'allume"})]),
            *evaluations,
        ]

    def test_verdict_confirme_puis_contredit_puis_caduque(self) -> None:
        boucle, workspace = self._boucle(
            [
                *self._tour(_corps("conforme.\nVERDICT: confirmee")),
                *self._tour(_corps("inattendu.\nVERDICT: contredite"), _corps("je révise")),
                *self._tour(_corps("sans objet.\nVERDICT: caduque")),
            ],
            AVO_CONTEXT_MODE="transcript",
        )
        self.assertIs(boucle.jouer_tour(1).evenement, Evenement.PREDICTION_CONFIRMEE)
        self.assertIs(boucle.jouer_tour(2).evenement, Evenement.CONTRADICTION)
        self.assertIs(boucle.jouer_tour(3).evenement, Evenement.PREDICTION_CONFIRMEE)
        self.assertEqual(self._verdicts(workspace), ["confirmee", "contredite", "caduque"])

    def test_sans_verdict_la_redemande_puis_l_issue_prudente_s_ecrivent(self) -> None:
        boucle, workspace = self._boucle(
            self._tour(_corps("je décris"), _corps("toujours rien"), _corps("je révise")),
            AVO_CONTEXT_MODE="transcript",
            AVO_GARDE_RETRIES="1",
        )
        self.assertIs(boucle.jouer_tour(1).evenement, Evenement.CONTRADICTION)
        self.assertEqual(self._verdicts(workspace), ["redemandee", "forcee"])


class TestRapportVerdicts(unittest.TestCase):
    """§A7.3 : la ligne des gardes porte la répartition, forcées comprises aux contredites."""

    def test_la_repartition_est_portee(self) -> None:
        metriques = [
            {"type": "garde", "garde": "evaluation", "issue": "confirmee"},
            {"type": "garde", "garde": "evaluation", "issue": "confirmee"},
            {"type": "garde", "garde": "evaluation", "issue": "contredite"},
            {"type": "garde", "garde": "evaluation", "issue": "forcee"},
            {"type": "garde", "garde": "evaluation", "issue": "caduque"},
            {"type": "garde", "garde": "prediction", "issue": "redemandee"},
        ]
        rendu = inference_par_appel(metriques)
        self.assertIn(
            "verdicts confirmées **2**, contredites **2** (dont forcées **1**), "
            "caduques **1**, redemandes **1**",
            rendu,
        )

    def test_sans_metrique_garde_la_ligne_dit_aucune(self) -> None:
        self.assertIn("gardes d'évaluation : aucune métrique", inference_par_appel([]))


if __name__ == "__main__":
    unittest.main()
