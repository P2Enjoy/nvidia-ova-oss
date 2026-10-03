"""Pas d'idéation : la clé « action » absente vaut vide, sur ce pas seul.

@verifies docs/BACKLOG.md U31 — amélioration générique sur mesure (journal
          2026-10-02, run `u31-h1511-ka59`, tour 1 : bloc d'idéation sans clé
          « action », refusé, un appel d'idéation entier perdu à redemander la
          même réponse avec `"action": ""`)
@verifies docs/SPEC_HARNAIS.md §H18.2 (sur le pas d'idéation, « action » vide OU
          absente — enveloppé comme aplati — est tolérée ; l'action rendue n'est
          jamais jouée ; hors de ce pas, le refus nommé est inchangé), §H15.4
          (bloc aplati sans « action » : refus nommant « action », sauf idéation),
          §H15.10 (archive des pas)

Aucun réseau : décodeur pur, puis la boucle au transport scripté et à
l'environnement factice de `test_patch_aplati.py`, dont les aides sont importées.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from avo.context.contexte import Contexte
from avo.context.etat import ARC_V1, PatchMalforme, decoder_pas
from avo.llm.client import LLMClient
from avo.loop import prompts
from avo.loop.boucle import BoucleAgent
from avo.memory.notes import Notes
from avo.memory.workspace import Workspace
from avo.tools.registre import Outil, RegistreOutils
from tests.unit.test_patch_aplati import (
    _SCHEMA,
    _bloc,
    _config,
    _Environnement,
    _TransportScripte,
)


class TestDecodeurActionAbsente(unittest.TestCase):
    """§H18.2 au décodeur : les deux formes de « pas d'action », sur le pas d'idéation seul."""

    def test_bloc_enveloppe_sans_action_vaut_action_vide_sur_le_pas_d_ideation(self) -> None:
        pas = decoder_pas(
            _bloc({"state_patch": {"hypotheses": ["a", "b"]}}), action_optionnelle=True
        )
        self.assertEqual(pas.action, "")
        self.assertEqual(dict(pas.patch), {"hypotheses": ["a", "b"]})
        self.assertFalse(pas.aplati)

    def test_bloc_aplati_sans_action_vaut_action_vide_sur_le_pas_d_ideation(self) -> None:
        pas = decoder_pas(_bloc({"hypotheses": ["a", "b"]}), action_optionnelle=True, schema=ARC_V1)
        self.assertEqual(pas.action, "")
        self.assertEqual(dict(pas.patch), {"hypotheses": ["a", "b"]})
        self.assertTrue(pas.aplati, "l'écart d'enveloppe reste nommé (§H15.4)")

    def test_hors_ideation_l_absence_reste_le_refus_nomme(self) -> None:
        with self.assertRaises(PatchMalforme) as enveloppe:
            decoder_pas(_bloc({"state_patch": {"hypotheses": ["a"]}}))
        self.assertIn("state_patch", str(enveloppe.exception))
        with self.assertRaises(PatchMalforme) as aplati:
            decoder_pas(_bloc({"hypotheses": ["a"]}), schema=ARC_V1)
        self.assertIn("« action » manquante", str(aplati.exception))

    def test_une_cle_etrangere_reste_refusee_meme_sur_le_pas_d_ideation(self) -> None:
        with self.assertRaises(PatchMalforme):
            decoder_pas(
                _bloc({"state_patch": {"hypotheses": ["a"]}, "commentaire": "x"}),
                action_optionnelle=True,
                schema=ARC_V1,
            )
        with self.assertRaises(PatchMalforme):
            decoder_pas(
                _bloc({"hypotheses": ["a"], "inconnu": 1}), action_optionnelle=True, schema=ARC_V1
            )

    def test_un_bloc_sans_state_patch_ni_action_reste_refuse(self) -> None:
        with self.assertRaises(PatchMalforme):
            decoder_pas(_bloc({}), action_optionnelle=True, schema=ARC_V1)


class TestBoucleIdeationActionAbsente(unittest.TestCase):
    """§H18.2 dans la boucle : un seul appel, le patch s'acquiert, rien n'est joué."""

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

    def test_le_pas_d_ideation_sans_cle_action_s_acquiert_en_un_appel(self) -> None:
        boucle, workspace, environnement = self._boucle(
            [
                _bloc({"state_patch": {"hypotheses": ["a", "b"]}}),
                _bloc({"state_patch": {}, "action": "avance"}),
            ],
            AVO_IDEATION_OUVERTURE="true",
        )
        tour = boucle.jouer_tour(1)
        self.assertEqual(tour.retries_patch, 0, "aucune redemande : l'absence vaut vide")
        self.assertEqual(environnement.jouees, [], "le pas d'idéation ne joue rien (§H18.2)")
        assert boucle.etat is not None
        self.assertEqual(boucle.etat.champs["hypotheses"], ("a", "b"))
        archives = self._pas_archives(workspace)
        self.assertEqual(len(archives), 1)
        self.assertTrue(archives[0]["ideation"])
        self.assertEqual(archives[0]["action"], "")
        self.assertNotIn("erreur", archives[0])
        self.assertEqual(self._metriques(workspace, "retry_patch"), [])
        self.assertEqual(len(self._metriques(workspace, "ideation")), 1)
        self.assertEqual(len(self.transport.reponses), 1, "la seconde réponse n'est pas consommée")

    def test_le_pas_d_ideation_aplati_sans_cle_action_s_acquiert_et_nomme_l_ecart(self) -> None:
        boucle, workspace, environnement = self._boucle(
            [
                _bloc({"hypotheses": ["a", "b"]}),
                _bloc({"state_patch": {}, "action": "avance"}),
            ],
            AVO_IDEATION_OUVERTURE="true",
        )
        tour = boucle.jouer_tour(1)
        self.assertEqual(tour.retries_patch, 0)
        self.assertEqual(environnement.jouees, [])
        archives = self._pas_archives(workspace)
        self.assertEqual(len(archives), 1)
        self.assertTrue(archives[0]["patch_aplati"])
        self.assertEqual(archives[0]["action"], "")
        self.assertEqual(len(self._metriques(workspace, "patch_aplati")), 1)

    def test_hors_ideation_un_pas_sans_cle_action_est_toujours_redemande(self) -> None:
        boucle, workspace, _ = self._boucle(
            [
                _bloc({"state_patch": {"hypotheses": ["h"]}}),
                _bloc({"state_patch": {"hypotheses": ["h"]}, "action": "avance"}),
            ]
        )
        tour = boucle.jouer_tour(1)
        self.assertEqual(tour.retries_patch, 1)
        erreurs = [p["erreur"] for p in self._pas_archives(workspace) if "erreur" in p]
        self.assertEqual(len(erreurs), 1)
        self.assertIn("state_patch", erreurs[0])


if __name__ == "__main__":
    unittest.main()
