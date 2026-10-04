"""Action irrésoluble = patch annulé, comme un refus d'environnement (mode `state`).

@verifies docs/BACKLOG.md U31 — amélioration générique sur mesures (run
          `u31-h1511-bp35`, 2026-10-03 : 8 des 23 actions émises nommaient une
          commande paramétrée sans ses valeurs ; chaque refus de résolution
          laissait Σ acquérir le patch d'une action jamais jouée)
@verifies docs/SPEC_HARNAIS.md §H15.8 (action irrésoluble : Σ et workspace revenus
          à l'avant-pas, archive `patch_annule`, événements `action_invalide` et
          `patch_annule`, rappel verbatim du patch annulé À CÔTÉ de l'erreur de
          forme au pas suivant, patch vide sans rappel, action résoluble inchangée),
          §H15.10 (archive des pas), §H11.2 (événements)

Aucun réseau : client au transport scripté (forme des corps §H4.3), environnement
factice dont l'outil d'action à coordonnées déclare deux paramètres requis.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from avo.config import Config, Mode, charger
from avo.context.contexte import Contexte
from avo.context.etat import LISTE_CHAINES, POSITION, ChampEtat, SchemaEtat
from avo.llm.client import LLMClient, ReponseHTTP
from avo.loop import prompts
from avo.loop.boucle import BoucleAgent
from avo.loop.etats import Evenement
from avo.memory.notes import Notes
from avo.memory.workspace import Workspace
from avo.tools.registre import Outil, RegistreOutils


def _config(**env: str) -> Config:
    return charger(
        Mode.REJEU,
        env={
            "OLLAMA_HOST": "http://capture.invalide",
            "OLLAMA_API_KEY": "sk-cle-irresoluble",
            "AVO_CONTEXT_MODE": "state",
            "AVO_GARDES": "false",
            # Mécanismes H18 hors du périmètre : séquences d'appels scriptées exactes.
            "AVO_IDEATION_OUVERTURE": "false",
            "AVO_PLAN_LEDGER": "false",
            **env,
        },
        racine=Path("/inexistant"),
    )


@dataclass
class _Issue:
    observation: str
    evenement: Evenement
    refusee: bool = False


class _EnvironnementClic:
    """Environnement factice : une action à coordonnées, jamais refusée."""

    def __init__(self) -> None:
        self.jouees: list[tuple[int, int]] = []
        self._derniere: Any = None

    def observation(self) -> str:
        return f"observation-{len(self.jouees)}"

    def actions_disponibles(self) -> list[str]:
        return ["clic"]

    def derniere_issue(self) -> Any:
        return self._derniere

    def etat_terminal(self) -> str | None:
        return None

    def jouer(self, row: int, col: int) -> str:
        self.jouees.append((row, col))
        texte = f"clic joué en {row},{col}."
        self._derniere = _Issue(texte, Evenement.PREDICTION_CONFIRMEE)
        return texte


class _TransportScripte:
    def __init__(self, reponses: list[dict[str, Any]]) -> None:
        self.reponses = list(reponses)
        self.corps: list[dict[str, Any]] = []

    def __call__(self, url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
        if not self.reponses:
            raise AssertionError("plus de réponse scriptée : appel LLM de trop")
        self.corps.append(json.loads(corps))
        return ReponseHTTP(200, json.dumps(self.reponses.pop(0)).encode())


def _pas(patch: dict[str, Any], action: str) -> dict[str, Any]:
    bloc = json.dumps({"state_patch": patch, "action": action})
    return {
        "message": {"role": "assistant", "content": f"```json\n{bloc}\n```"},
        "done_reason": "stop",
        "prompt_eval_count": 10,
        "eval_count": 5,
        "total_duration": 1_000_000,
    }


_SCHEMA = SchemaEtat(
    "test-irresoluble-v1",
    (
        ChampEtat("hypotheses", LISTE_CHAINES, "ce que tu tiens pour vrai"),
        ChampEtat("position", POSITION, "où tu en es"),
    ),
)


class TestPatchAnnuleSousActionIrresoluble(unittest.TestCase):
    """§H15.8 : le patch d'un pas dont l'action n'est pas résoluble n'atteint pas Σ."""

    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def _boucle(self, reponses: list[dict[str, Any]]) -> tuple[BoucleAgent, Workspace]:
        config = _config()
        self.environnement = _EnvironnementClic()
        registre = RegistreOutils(
            [
                Outil(
                    nom="clic",
                    description="Clique une cellule.",
                    parametres={
                        "type": "object",
                        "properties": {
                            "row": {"type": "integer"},
                            "col": {"type": "integer"},
                        },
                        "required": ["row", "col"],
                    },
                    fonction=self.environnement.jouer,
                    etiquettes=frozenset({"action"}),
                )
            ]
        )
        workspace = Workspace.ouvrir(config, "run-test", racine=self.racine)
        self.transport = _TransportScripte(reponses)
        client = LLMClient(config, transport=self.transport, dormir=lambda _: None)
        contexte = Contexte(config=config, systeme=prompts.SYSTEME, schema_etat=_SCHEMA)
        boucle = BoucleAgent(
            config,
            client,
            registre,
            self.environnement,
            Notes(self.racine / "notes"),
            contexte=contexte,
            workspace=workspace,
        )
        return boucle, workspace

    def _pas_archives(self, workspace: Workspace) -> list[dict[str, Any]]:
        chemin = workspace.chemin / "state" / "pas.jsonl"
        return [json.loads(ligne) for ligne in chemin.read_text().splitlines()]

    def _metriques(self, workspace: Workspace) -> list[dict[str, Any]]:
        chemin = workspace.chemin / "metrics.jsonl"
        return [json.loads(ligne) for ligne in chemin.read_text().splitlines()]

    def test_une_commande_sans_valeurs_annule_le_patch(self) -> None:
        """Le relevé de bp35 : « clic » nu, deux valeurs requises, rien n'est joué."""
        boucle, workspace = self._boucle(
            [_pas({"hypotheses": ["h"], "position": {"x": 3, "y": 4}}, "clic")]
        )
        tour = boucle.jouer_tour(1)
        self.assertIsNone(tour.action, "aucune action n'est jouée")
        self.assertEqual(self.environnement.jouees, [], "l'environnement n'est jamais appelé")
        assert boucle.etat is not None
        self.assertIsNone(
            boucle.etat.champs["position"],
            "le patch de l'action irrésoluble n'atteint pas Σ (§H15.8)",
        )
        self.assertFalse(boucle.etat.champs["hypotheses"], "aucun champ du patch n'est acquis")
        etat_disque = json.loads((workspace.chemin / "state" / "etat.json").read_text())
        self.assertIsNone(etat_disque["position"], "le workspace revient à l'avant-pas")
        annulations = [p for p in self._pas_archives(workspace) if p.get("patch_annule")]
        self.assertEqual(len(annulations), 1, "l'archive porte le patch annulé (§H15.10)")
        self.assertEqual(
            annulations[0]["patch"], {"hypotheses": ["h"], "position": {"x": 3, "y": 4}}
        )
        types = [m["type"] for m in self._metriques(workspace)]
        self.assertIn("action_invalide", types, "le refus de résolution reste compté")
        self.assertIn("patch_annule", types, "l'annulation est un événement nommé (§H11.2)")
        annule = next(m for m in self._metriques(workspace) if m["type"] == "patch_annule")
        self.assertEqual(annule["action"], "clic")

    def test_un_nom_inconnu_annule_le_patch(self) -> None:
        boucle, workspace = self._boucle([_pas({"position": {"x": 1, "y": 2}}, "saute 1, 2")])
        boucle.jouer_tour(1)
        assert boucle.etat is not None
        self.assertIsNone(boucle.etat.champs["position"])
        self.assertTrue(any(p.get("patch_annule") for p in self._pas_archives(workspace)))

    def test_un_type_invalide_annule_le_patch(self) -> None:
        boucle, workspace = self._boucle([_pas({"position": {"x": 1, "y": 2}}, "clic a, b")])
        boucle.jouer_tour(1)
        assert boucle.etat is not None
        self.assertIsNone(boucle.etat.champs["position"])
        self.assertEqual(self.environnement.jouees, [])
        self.assertTrue(any(p.get("patch_annule") for p in self._pas_archives(workspace)))

    def test_le_pas_suivant_recoit_l_erreur_nommee_et_le_rappel(self) -> None:
        """§H15.8 : forme complète attendue ET patch annulé verbatim, dans le même message."""
        boucle, _workspace = self._boucle(
            [
                _pas({"hypotheses": ["h"], "position": {"x": 3, "y": 4}}, "clic"),
                _pas({"position": {"x": 3, "y": 4}}, "clic 3, 4"),
            ]
        )
        boucle.jouer_tour(1)
        boucle.jouer_tour(2)
        prompt_pas_2 = self.transport.corps[1]["messages"][1]["content"]
        self.assertIn("2 valeur(s) attendue(s) (row, col), 0 reçue(s)", prompt_pas_2)
        self.assertIn("Forme attendue : « clic row, col »", prompt_pas_2)
        self.assertIn("Patch annulé", prompt_pas_2, "le rappel figure au pas suivant (§H15.8)")
        self.assertIn("« clic »", prompt_pas_2, "le rappel nomme l'action irrésoluble")
        self.assertIn('"position": {"x": 3, "y": 4}', prompt_pas_2, "patch rappelé verbatim")
        self.assertEqual(self.environnement.jouees, [(3, 4)], "le pas corrigé est joué")
        assert boucle.etat is not None
        self.assertEqual(boucle.etat.champs["position"], {"x": 3, "y": 4})

    def test_le_rappel_est_omis_quand_le_patch_etait_vide(self) -> None:
        boucle, _workspace = self._boucle([_pas({}, "clic"), _pas({}, "clic 0, 0")])
        boucle.jouer_tour(1)
        boucle.jouer_tour(2)
        prompt_pas_2 = self.transport.corps[1]["messages"][1]["content"]
        self.assertNotIn("Patch annulé", prompt_pas_2)
        self.assertIn("2 valeur(s) attendue(s)", prompt_pas_2, "l'erreur nommée demeure")

    def test_une_action_resoluble_conserve_son_patch(self) -> None:
        boucle, workspace = self._boucle([_pas({"position": {"x": 5, "y": 6}}, "clic 5, 6")])
        tour = boucle.jouer_tour(1)
        self.assertEqual(tour.action, "clic")
        self.assertEqual(self.environnement.jouees, [(5, 6)])
        assert boucle.etat is not None
        self.assertEqual(boucle.etat.champs["position"], {"x": 5, "y": 6})
        self.assertFalse(any(p.get("patch_annule") for p in self._pas_archives(workspace)))
        types = [m["type"] for m in self._metriques(workspace)]
        self.assertNotIn("patch_annule", types)
        self.assertNotIn("action_invalide", types)


if __name__ == "__main__":
    unittest.main()
