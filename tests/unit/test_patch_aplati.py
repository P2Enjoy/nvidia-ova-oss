"""Patch aplati : enveloppe « state_patch » levée par les seuls noms de champs du schéma.

@verifies docs/BACKLOG.md U31 — amélioration générique sur mesures (journal
          2026-09-30, run `u31-h1511-cd82` : 2 appels sur 26 perdus à redemander
          la même réponse enveloppée ; re86, 1 appel)
@verifies docs/SPEC_HARNAIS.md §H15.4 (patch aplati : normalisé quand chaque clé
          autre qu'« action » est un champ du schéma effectif ; clé étrangère ou
          schéma absent = refus nommé inchangé ; bloc aplati sans « action » =
          refus nommant « action » ; archive `patch_aplati` et métrique),
          §H15.9 (les noms de champs viennent du schéma déclaré), §H15.10
          (archive des pas), §H18.2 (action vide tolérée sur le pas d'idéation)

Aucun réseau : décodeur pur, puis boucle au transport scripté et environnement
factice (même patron que `test_pas_refuse.py`).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from avo.config import Config, Mode, charger
from avo.context.contexte import Contexte
from avo.context.etat import (
    ARC_V1,
    LISTE_CHAINES,
    POSITION,
    ChampEtat,
    Etat,
    PatchMalforme,
    SchemaEtat,
    appliquer,
    decoder_pas,
)
from avo.llm.client import LLMClient, ReponseHTTP
from avo.loop import prompts
from avo.loop.boucle import BoucleAgent
from avo.loop.etats import Evenement
from avo.memory.notes import Notes
from avo.memory.workspace import Workspace
from avo.tools.registre import Outil, RegistreOutils


def _bloc(objet: dict[str, Any]) -> str:
    return f"raisonnement...\n```json\n{json.dumps(objet)}\n```"


class TestDecodeurPatchAplati(unittest.TestCase):
    """§H15.4 : l'enveloppe se lève par le schéma, jamais par devinette."""

    def test_champs_du_schema_a_la_racine_forment_le_patch(self) -> None:
        pas = decoder_pas(_bloc({"essai": 2, "action": "ACTION1"}), schema=ARC_V1)
        self.assertEqual(pas.patch, {"essai": 2})
        self.assertEqual(pas.action, "ACTION1")
        self.assertTrue(pas.aplati, "l'écart est nommé sur le pas rendu")

    def test_un_bloc_enveloppe_n_est_pas_marque_aplati(self) -> None:
        pas = decoder_pas(_bloc({"state_patch": {"essai": 2}, "action": "ACTION1"}), schema=ARC_V1)
        self.assertEqual(pas.patch, {"essai": 2})
        self.assertFalse(pas.aplati)

    def test_sans_schema_le_contrat_strict_s_applique(self) -> None:
        with self.assertRaises(PatchMalforme) as refus:
            decoder_pas(_bloc({"essai": 2, "action": "ACTION1"}))
        self.assertIn("exactement les clés", str(refus.exception))

    def test_une_cle_etrangere_au_schema_laisse_le_refus_nomme(self) -> None:
        with self.assertRaises(PatchMalforme) as refus:
            decoder_pas(_bloc({"essai": 2, "commentaire": "x", "action": "ACTION1"}), schema=ARC_V1)
        self.assertIn("commentaire", str(refus.exception))

    def test_state_patch_present_avec_une_cle_en_trop_reste_refuse(self) -> None:
        with self.assertRaises(PatchMalforme):
            decoder_pas(_bloc({"state_patch": {}, "essai": 2, "action": "ACTION1"}), schema=ARC_V1)

    def test_bloc_aplati_sans_action_est_refuse_en_nommant_action(self) -> None:
        with self.assertRaises(PatchMalforme) as refus:
            decoder_pas(_bloc({"essai": 8, "hypotheses": ["h"]}), schema=ARC_V1)
        self.assertIn("« action » manquante", str(refus.exception))
        self.assertIn("essai", str(refus.exception))

    def test_action_seule_sans_champ_reste_refusee(self) -> None:
        with self.assertRaises(PatchMalforme) as refus:
            decoder_pas(_bloc({"action": "ACTION1"}), schema=ARC_V1)
        self.assertIn("exactement les clés", str(refus.exception))

    def test_les_valeurs_aplaties_restent_validees_par_le_schema(self) -> None:
        with self.assertRaises(ValueError) as refus:
            appliquer(Etat.initial(), _bloc({"essai": "deux", "action": "ACTION1"}))
        self.assertIn("essai", str(refus.exception))

    def test_appliquer_fusionne_un_patch_aplati_par_le_schema_de_l_etat(self) -> None:
        etat, action = appliquer(
            Etat.initial(), _bloc({"essai": 3, "hypotheses": ["h"], "action": "ACTION2"})
        )
        self.assertEqual(etat.champs["essai"], 3)
        self.assertEqual(etat.champs["hypotheses"], ("h",))
        self.assertEqual(action, "ACTION2")

    def test_action_vide_aplatie_toleree_sur_le_pas_d_ideation_seul(self) -> None:
        pas = decoder_pas(
            _bloc({"hypotheses": ["a", "b"], "action": ""}), action_optionnelle=True, schema=ARC_V1
        )
        self.assertTrue(pas.aplati)
        self.assertEqual(pas.action, "")
        with self.assertRaises(PatchMalforme):
            decoder_pas(_bloc({"hypotheses": ["a", "b"], "action": ""}), schema=ARC_V1)

    def test_le_schema_declare_fait_foi_pas_arc_v1(self) -> None:
        schema = SchemaEtat(
            "domaine-test",
            (
                ChampEtat("hypotheses", LISTE_CHAINES, "ce que tu tiens pour vrai"),
                ChampEtat("ou", POSITION, "où tu en es"),
            ),
        )
        pas = decoder_pas(_bloc({"ou": {"x": 1, "y": 2}, "action": "go"}), schema=schema)
        self.assertEqual(pas.patch, {"ou": {"x": 1, "y": 2}})
        with self.assertRaises(PatchMalforme):
            decoder_pas(_bloc({"essai": 2, "action": "go"}), schema=schema)


def _config(**env: str) -> Config:
    return charger(
        Mode.REJEU,
        env={
            "OLLAMA_HOST": "http://capture.invalide",
            "OLLAMA_API_KEY": "sk-cle-patch-aplati",
            "AVO_CONTEXT_MODE": "state",
            "AVO_GARDES": "false",
            "AVO_IDEATION_OUVERTURE": "false",
            "AVO_PLAN_LEDGER": "false",
            **env,
        },
        racine=Path("/inexistant"),
    )


class _Issue:
    def __init__(self, observation: str) -> None:
        self.observation = observation
        self.evenement = Evenement.PREDICTION_CONFIRMEE


class _Environnement:
    def __init__(self) -> None:
        self.jouees: list[str] = []
        self._derniere: Any = None

    def observation(self) -> str:
        return f"observation-{len(self.jouees)}"

    def actions_disponibles(self) -> list[str]:
        return ["avance"]

    def derniere_issue(self) -> Any:
        return self._derniere

    def etat_terminal(self) -> str | None:
        return None

    def jouer(self) -> str:
        self.jouees.append("avance")
        self._derniere = _Issue("action jouée.")
        return "action jouée."


class _TransportScripte:
    def __init__(self, reponses: list[str]) -> None:
        self.reponses = list(reponses)

    def __call__(self, url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
        if not self.reponses:
            raise AssertionError("plus de réponse scriptée : appel LLM de trop")
        reponse = {
            "message": {"role": "assistant", "content": self.reponses.pop(0)},
            "done_reason": "stop",
            "prompt_eval_count": 10,
            "eval_count": 5,
            "total_duration": 1_000_000,
        }
        return ReponseHTTP(200, json.dumps(reponse).encode())


_SCHEMA = SchemaEtat(
    "test-aplati-v1",
    (
        ChampEtat("hypotheses", LISTE_CHAINES, "ce que tu tiens pour vrai"),
        ChampEtat("position", POSITION, "où tu en es"),
    ),
)


class TestBouclePatchAplati(unittest.TestCase):
    """§H15.4 dans la boucle : un seul appel, Σ mis à jour, écart archivé et compté."""

    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def _boucle(
        self, reponses: list[str], **env: str
    ) -> tuple[BoucleAgent, Workspace, _Environnement]:
        config = _config(**env)
        environnement = _Environnement()
        registre = RegistreOutils(
            [
                Outil(
                    nom="avance",
                    description="Joue une action d'environnement.",
                    parametres={"type": "object", "properties": {}},
                    fonction=environnement.jouer,
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
            environnement,
            Notes(self.racine / "notes"),
            contexte=contexte,
            workspace=workspace,
        )
        return boucle, workspace, environnement

    def _pas_archives(self, workspace: Workspace) -> list[dict[str, Any]]:
        chemin = workspace.chemin / "state" / "pas.jsonl"
        return [json.loads(ligne) for ligne in chemin.read_text().splitlines()]

    def _metriques(self, workspace: Workspace, type_evenement: str) -> list[dict[str, Any]]:
        chemin = workspace.chemin / "metrics.jsonl"
        return [
            ligne
            for ligne in (json.loads(brut) for brut in chemin.read_text().splitlines())
            if ligne.get("type") == type_evenement
        ]

    def test_un_pas_aplati_est_joue_en_un_seul_appel_et_archive(self) -> None:
        boucle, workspace, environnement = self._boucle(
            [_bloc({"hypotheses": ["h"], "position": {"x": 3, "y": 4}, "action": "avance"})]
        )
        tour = boucle.jouer_tour(1)
        self.assertEqual(tour.action, "avance")
        self.assertEqual(tour.retries_patch, 0, "aucune redemande : l'enveloppe est levée")
        self.assertEqual(environnement.jouees, ["avance"])
        assert boucle.etat is not None
        self.assertEqual(dict(boucle.etat.champs["position"]), {"x": 3, "y": 4})
        archives = self._pas_archives(workspace)
        self.assertEqual(len(archives), 1)
        self.assertTrue(archives[0].get("patch_aplati"), "l'écart est archivé (§H15.10)")
        self.assertEqual(archives[0]["patch"], {"hypotheses": ["h"], "position": {"x": 3, "y": 4}})
        self.assertEqual(len(self._metriques(workspace, "patch_aplati")), 1)
        self.assertEqual(self._metriques(workspace, "retry_patch"), [])

    def test_un_pas_enveloppe_ne_porte_ni_archive_ni_metrique_d_aplatissement(self) -> None:
        boucle, workspace, _ = self._boucle(
            [_bloc({"state_patch": {"hypotheses": ["h"]}, "action": "avance"})]
        )
        boucle.jouer_tour(1)
        self.assertNotIn("patch_aplati", self._pas_archives(workspace)[0])
        self.assertEqual(self._metriques(workspace, "patch_aplati"), [])

    def test_un_bloc_aplati_sans_action_est_redemande_en_nommant_action(self) -> None:
        boucle, workspace, _ = self._boucle(
            [
                _bloc({"hypotheses": ["h"], "position": {"x": 1, "y": 1}}),
                _bloc({"state_patch": {"hypotheses": ["h"]}, "action": "avance"}),
            ]
        )
        tour = boucle.jouer_tour(1)
        self.assertEqual(tour.retries_patch, 1)
        erreurs = [p["erreur"] for p in self._pas_archives(workspace) if "erreur" in p]
        self.assertEqual(len(erreurs), 1)
        self.assertIn("« action » manquante", erreurs[0])

    def test_le_pas_d_ideation_leve_aussi_l_enveloppe(self) -> None:
        boucle, workspace, environnement = self._boucle(
            [
                _bloc({"hypotheses": ["a", "b"], "action": ""}),
                _bloc({"state_patch": {}, "action": "avance"}),
            ],
            AVO_IDEATION_OUVERTURE="true",
        )
        boucle.jouer_tour(1)
        self.assertEqual(environnement.jouees, [], "le pas d'idéation ne joue rien (§H18.2)")
        assert boucle.etat is not None
        self.assertEqual(boucle.etat.champs["hypotheses"], ("a", "b"))
        archives = self._pas_archives(workspace)
        self.assertTrue(archives[0].get("ideation"))
        self.assertTrue(archives[0].get("patch_aplati"))
        self.assertEqual(len(self._metriques(workspace, "patch_aplati")), 1)


if __name__ == "__main__":
    unittest.main()
