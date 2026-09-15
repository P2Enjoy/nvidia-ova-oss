"""Idéation d'ouverture et curation du superviseur dans la boucle (mode `state`).

@verifies docs/BACKLOG.md U37 — Intégration du patron ledger dans la boucle et
          l'état existants
@verifies docs/SPEC_HARNAIS.md §H18.2 (pas d'idéation : patch appliqué, action
          non jouée, une fois par boucle, interrupteur, Σ rechargé non vide,
          invite du mode `transcript`), §H18.3 (curation à l'intervention :
          remplacement validé, dégradation hors `AuthError`, `AuthError`
          propagée, interrupteur), §H18.4 (interrupteurs indépendants),
          §H18.5 (métriques `ideation`/`curation`, bilan, événement
          `superviseur.curation`, résumé du superviseur), §H18.1 (schéma dérivé
          `+plan` de la boucle)

Aucun réseau : clients au transport scripté (§H4.3), environnement factice.
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
from avo.context.etat import CHAMP_PLAN, LISTE_CHAINES, ChampEtat, Etat, SchemaEtat, avec_plan
from avo.llm.client import AuthError, LLMClient, ReponseHTTP
from avo.loop import prompts
from avo.loop.boucle import BoucleAgent
from avo.loop.etats import Evenement
from avo.memory.notes import Notes
from avo.memory.workspace import Workspace
from avo.supervisor import Superviseur
from avo.tools.registre import Outil, RegistreOutils


def _config(**env: str) -> Config:
    return charger(
        Mode.REJEU,
        env={
            "OLLAMA_HOST": "http://capture.invalide",
            "OLLAMA_API_KEY": "sk-cle-ideation-curation",
            "AVO_CONTEXT_MODE": "state",
            "AVO_GARDES": "false",
            "AVO_SUP_SONDE_FRAICHE": "false",
            **env,
        },
        racine=Path("/inexistant"),
    )


@dataclass
class _Issue:
    observation: str
    evenement: Evenement


class _Environnement:
    """Environnement factice : chaque action rendue confirme, sans jeu."""

    def __init__(self) -> None:
        self.jouees: list[str] = []
        self._derniere: _Issue | None = None

    def observation(self) -> str:
        return f"observation-{len(self.jouees)}"

    def actions_disponibles(self) -> list[str]:
        return ["avance"]

    def derniere_issue(self) -> _Issue | None:
        return self._derniere

    def etat_terminal(self) -> str | None:
        return None

    def jouer(self) -> str:
        self.jouees.append("avance")
        self._derniere = _Issue(f"issue-{len(self.jouees)}", Evenement.PREDICTION_CONFIRMEE)
        return "action jouée."


class _TransportScripte:
    def __init__(self, reponses: list[Any]) -> None:
        self.reponses = list(reponses)
        self.corps: list[dict[str, Any]] = []

    def __call__(self, url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
        if not self.reponses:
            raise AssertionError("plus de réponse scriptée : appel LLM de trop")
        self.corps.append(json.loads(corps))
        reponse = self.reponses.pop(0)
        if isinstance(reponse, int):
            return ReponseHTTP(reponse, b'{"error": "scripte"}')
        return ReponseHTTP(200, json.dumps(reponse).encode())


def _reponse(contenu: str) -> dict[str, Any]:
    return {
        "message": {"role": "assistant", "content": contenu},
        "done_reason": "stop",
        "prompt_eval_count": 10,
        "eval_count": 5,
        "total_duration": 1_000_000,
    }


def _pas(patch: dict[str, Any], action: str = "avance") -> dict[str, Any]:
    bloc = json.dumps({"state_patch": patch, "action": action})
    return _reponse(f"```json\n{bloc}\n```")


def _tache(ident: str, statut: str = "a_faire") -> dict[str, str]:
    return {"id": ident, "description": f"tâche {ident}", "statut": statut}


_SCHEMA = SchemaEtat("test-idc-v1", (ChampEtat("hypotheses", LISTE_CHAINES, "acquis"),))


class _Socle(unittest.TestCase):
    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def _boucle(
        self,
        reponses: list[Any],
        config: Config | None = None,
        reponses_superviseur: list[Any] | None = None,
    ) -> tuple[BoucleAgent, _Environnement, Workspace]:
        config = config or _config()
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
        superviseur = None
        if reponses_superviseur is not None:
            self.transport_superviseur = _TransportScripte(reponses_superviseur)
            superviseur = Superviseur(
                config,
                LLMClient(config, transport=self.transport_superviseur, dormir=lambda _: None),
            )
        contexte = Contexte(config=config, systeme=prompts.SYSTEME, schema_etat=_SCHEMA)
        boucle = BoucleAgent(
            config,
            client,
            registre,
            environnement,
            Notes(self.racine / "notes"),
            contexte=contexte,
            workspace=workspace,
            superviseur=superviseur,
        )
        return boucle, environnement, workspace

    def _metriques(self, workspace: Workspace) -> list[dict[str, Any]]:
        return workspace.lire_metriques()

    def _pas_archives(self, workspace: Workspace) -> list[dict[str, Any]]:
        chemin = workspace.chemin / "state" / "pas.jsonl"
        if not chemin.exists():
            return []
        return [json.loads(ligne) for ligne in chemin.read_text().splitlines()]


class TestPasIdeation(_Socle):
    """§H18.2 : le premier pas énumère les approches — patch acquis, action non jouée."""

    def test_le_pas_d_ideation_acquiert_le_patch_sans_jouer_l_action(self) -> None:
        boucle, environnement, workspace = self._boucle(
            [
                _pas({"hypotheses": ["a1", "a2"], CHAMP_PLAN: [_tache("t1")]}),
                _pas({}),
            ]
        )
        tour = boucle.jouer_tour(1)
        self.assertIsNone(tour.action)
        self.assertEqual(environnement.jouees, [], "l'action du pas d'idéation n'est pas jouée")
        assert boucle.etat is not None
        self.assertEqual(boucle.etat.champs["hypotheses"], ("a1", "a2"))
        self.assertEqual(len(boucle.etat.champs[CHAMP_PLAN]), 1)
        self.assertEqual(boucle.bilan.ideations, 1)
        # L'invite dédiée ouvre le message, à la place de l'amorce documentaire.
        message = self.transport.corps[0]["messages"][1]["content"]
        self.assertIn(prompts.IDEATION, message)
        # Le tour suivant est un pas ordinaire : l'action se joue.
        boucle.jouer_tour(2)
        self.assertEqual(environnement.jouees, ["avance"])
        self.assertNotIn(prompts.IDEATION, self.transport.corps[1]["messages"][1]["content"])

    def test_l_ideation_ecrit_sa_metrique_et_son_archive(self) -> None:
        boucle, _environnement, workspace = self._boucle(
            [_pas({"hypotheses": ["a1"], CHAMP_PLAN: [_tache("t1"), _tache("t2")]})]
        )
        boucle.jouer_tour(1)
        (ideation,) = [m for m in self._metriques(workspace) if m["type"] == "ideation"]
        self.assertEqual(ideation["hypotheses"], 1)
        self.assertEqual(ideation["taches"], 2)
        (ligne,) = self._pas_archives(workspace)
        self.assertTrue(ligne["ideation"])

    def test_le_schema_effectif_de_la_boucle_est_derive_plus_plan(self) -> None:
        boucle, _environnement, _workspace = self._boucle([])
        assert boucle.etat is not None
        self.assertEqual(boucle.etat.schema.nom, "test-idc-v1+plan")
        # Le protocole du pas est engendré du schéma effectif (§H18.1).
        boucle2, _env2, _ws2 = self._boucle([_pas({"hypotheses": ["a"]})])
        boucle2.jouer_tour(1)
        self.assertIn("fusionne par « id »", self.transport.corps[0]["messages"][1]["content"])

    def test_sans_ledger_le_schema_reste_le_declare(self) -> None:
        boucle, _environnement, _workspace = self._boucle(
            [], config=_config(AVO_PLAN_LEDGER="false")
        )
        assert boucle.etat is not None
        self.assertEqual(boucle.etat.schema.nom, "test-idc-v1")

    def test_interrupteur_inactif_aucun_pas_d_ideation(self) -> None:
        boucle, environnement, _workspace = self._boucle(
            [_pas({"hypotheses": ["a1"]})],
            config=_config(AVO_IDEATION_OUVERTURE="false"),
        )
        boucle.jouer_tour(1)
        self.assertEqual(environnement.jouees, ["avance"], "premier tour ordinaire")
        self.assertEqual(boucle.bilan.ideations, 0)

    def test_un_sigma_recharge_non_vide_n_ouvre_pas_d_ideation(self) -> None:
        config = _config()
        workspace = Workspace.ouvrir(config, "run-test", racine=self.racine)
        workspace.ecrire_etat(
            Etat.initial(avec_plan(_SCHEMA)).fusionner({"hypotheses": ["déjà là"]})
        )
        boucle, environnement, _workspace = self._boucle([_pas({})], config=config)
        boucle.jouer_tour(1)
        self.assertEqual(environnement.jouees, ["avance"])
        self.assertEqual(boucle.bilan.ideations, 0)

    def test_l_ideation_est_une_fois_par_boucle_meme_si_hypotheses_reste_vide(self) -> None:
        boucle, environnement, _workspace = self._boucle([_pas({}), _pas({})])
        boucle.jouer_tour(1)
        self.assertEqual(boucle.bilan.ideations, 1)
        boucle.jouer_tour(2)
        self.assertEqual(boucle.bilan.ideations, 1, "pas de seconde idéation")
        self.assertEqual(environnement.jouees, ["avance"], "le second pas est ordinaire")


class TestIdeationTranscript(_Socle):
    """§H18.2 : en mode `transcript`, l'invite précède la demande documentaire."""

    def _config_transcript(self, **env: str) -> Config:
        # Une seule redemande de garde par tour : WORKING.md reste vide dans ces
        # scénarios, chaque tour consomme donc Planning + une redemande, puis clôt.
        return _config(
            AVO_CONTEXT_MODE="transcript",
            AVO_GARDES="true",
            AVO_GARDE_RETRIES="1",
            **env,
        )

    def test_l_invite_precede_la_demande_documentaire_du_premier_planning(self) -> None:
        boucle, _environnement, _workspace = self._boucle(
            [_reponse("je planifie"), _reponse("je planifie encore")],
            config=self._config_transcript(),
        )
        boucle.jouer_tour(1)
        premier = self.transport.corps[0]["messages"][-1]["content"]
        self.assertIn(prompts.IDEATION, premier)
        self.assertLess(
            premier.index(prompts.IDEATION),
            premier.index("[GARDE]"),
            "l'idéation précède la demande documentaire",
        )

    def test_l_invite_ne_se_repete_pas_au_tour_suivant(self) -> None:
        boucle, _environnement, _workspace = self._boucle(
            [_reponse(f"réponse {i}") for i in range(4)],
            config=self._config_transcript(),
        )
        boucle.jouer_tour(1)
        appels_tour_1 = len(self.transport.corps)
        boucle.jouer_tour(2)
        # Le Planning du second tour est le premier appel après ceux du tour 1.
        seconde = self.transport.corps[appels_tour_1]["messages"][-1]["content"]
        self.assertIn("[GARDE]", seconde, "la demande documentaire persiste")
        self.assertNotIn(prompts.IDEATION, seconde)

    def test_interrupteur_inactif_l_invite_n_apparait_pas(self) -> None:
        boucle, _environnement, _workspace = self._boucle(
            [_reponse("je planifie"), _reponse("je planifie encore")],
            config=self._config_transcript(AVO_IDEATION_OUVERTURE="false"),
        )
        boucle.jouer_tour(1)
        self.assertNotIn(prompts.IDEATION, self.transport.corps[0]["messages"][-1]["content"])


def _liste_curee(taches: list[dict[str, str]]) -> dict[str, Any]:
    return _reponse("Liste curée :\n```json\n" + json.dumps(taches) + "\n```")


class TestCuration(_Socle):
    """§H18.3 : à l'intervention, le superviseur cure le ledger — et lui seul."""

    def _boucle_supervisee(
        self, reponses_superviseur: list[Any], **env: str
    ) -> tuple[BoucleAgent, _Environnement, Workspace]:
        # Seuil de stagnation à 1 : la première action déclenche l'intervention.
        config = _config(AVO_SUP_STALL_ACTIONS="1", AVO_IDEATION_OUVERTURE="false", **env)
        return self._boucle(
            [_pas({"hypotheses": ["h1"], CHAMP_PLAN: [_tache("t1"), _tache("t1bis")]})],
            config=config,
            reponses_superviseur=reponses_superviseur,
        )

    def test_la_curation_remplace_le_ledger_et_se_compte(self) -> None:
        boucle, _environnement, workspace = self._boucle_supervisee(
            [
                _reponse("diagnostic : élargis la recherche"),
                _liste_curee([_tache("t1", "en_cours")]),
            ]
        )
        boucle.jouer_tour(1)
        assert boucle.etat is not None and boucle.superviseur is not None
        self.assertEqual(
            [t["id"] for t in boucle.etat.champs[CHAMP_PLAN]],
            ["t1"],
            "les doublons sont fusionnés par remplacement",
        )
        self.assertEqual(boucle.bilan.curations, 1)
        self.assertTrue(boucle.superviseur.interventions[0].curation)
        self.assertEqual(boucle.superviseur.resume()["curations"], 1)
        (curation,) = [m for m in self._metriques(workspace) if m["type"] == "curation"]
        self.assertTrue(curation["appliquee"])
        self.assertEqual(curation["taches_avant"], 2)
        self.assertEqual(curation["taches_apres"], 1)
        (superviseur,) = [m for m in self._metriques(workspace) if m["type"] == "superviseur"]
        self.assertTrue(superviseur["curation"])
        # Σ curé est persisté (§H15.5).
        assert boucle.etat is not None
        recharge = workspace.lire_etat(boucle.etat.schema)
        assert recharge is not None
        self.assertEqual(len(recharge.champs[CHAMP_PLAN]), 1)

    def test_une_sortie_sans_bloc_degrade_sans_toucher_le_ledger(self) -> None:
        boucle, _environnement, workspace = self._boucle_supervisee(
            [
                _reponse("diagnostic"),
                _reponse("aucune liste ici"),
            ]
        )
        boucle.jouer_tour(1)
        assert boucle.etat is not None
        self.assertEqual(len(boucle.etat.champs[CHAMP_PLAN]), 2, "ledger inchangé")
        self.assertEqual(boucle.bilan.curations, 0)
        (curation,) = [m for m in self._metriques(workspace) if m["type"] == "curation"]
        self.assertFalse(curation["appliquee"])
        self.assertEqual(curation["erreur"], "bloc_absent")

    def test_une_liste_invalide_degrade_en_nommant_l_ecart(self) -> None:
        boucle, _environnement, workspace = self._boucle_supervisee(
            [
                _reponse("diagnostic"),
                _liste_curee([{"id": "t1", "description": "d", "statut": "bidon"}]),
            ]
        )
        boucle.jouer_tour(1)
        assert boucle.etat is not None
        self.assertEqual(len(boucle.etat.champs[CHAMP_PLAN]), 2)
        (curation,) = [m for m in self._metriques(workspace) if m["type"] == "curation"]
        self.assertFalse(curation["appliquee"])
        self.assertIn("EtatInvalide", curation["erreur"])

    def test_une_panne_serveur_degrade_l_intervention_survit(self) -> None:
        boucle, _environnement, workspace = self._boucle_supervisee(
            # Diagnostic, puis l'appel de curation meurt en 500 (retries du
            # client compris, §H4.5).
            [_reponse("diagnostic")] + [500] * 6
        )
        boucle.jouer_tour(1)
        self.assertEqual(boucle.bilan.interventions, 1, "l'intervention a bien eu lieu")
        self.assertEqual(boucle.bilan.curations, 0)
        (curation,) = [m for m in self._metriques(workspace) if m["type"] == "curation"]
        self.assertFalse(curation["appliquee"])
        self.assertEqual(curation["erreur"], "ServerError")

    def test_auth_error_se_propage(self) -> None:
        boucle, _environnement, _workspace = self._boucle_supervisee([_reponse("diagnostic"), 401])
        with self.assertRaises(AuthError):
            boucle.jouer_tour(1)

    def test_interrupteur_inactif_aucun_appel_de_curation(self) -> None:
        boucle, _environnement, workspace = self._boucle_supervisee(
            [_reponse("diagnostic")], AVO_SUP_CURATION="false"
        )
        boucle.jouer_tour(1)
        self.assertEqual(boucle.bilan.interventions, 1)
        self.assertEqual([m for m in self._metriques(workspace) if m["type"] == "curation"], [])
        (superviseur,) = [m for m in self._metriques(workspace) if m["type"] == "superviseur"]
        self.assertFalse(superviseur["curation"])

    def test_sans_ledger_aucun_appel_de_curation(self) -> None:
        boucle, _environnement, workspace = self._boucle(
            [_pas({"hypotheses": ["h1"]})],
            config=_config(
                AVO_SUP_STALL_ACTIONS="1",
                AVO_IDEATION_OUVERTURE="false",
                AVO_PLAN_LEDGER="false",
            ),
            reponses_superviseur=[_reponse("diagnostic")],
        )
        boucle.jouer_tour(1)
        self.assertEqual(boucle.bilan.interventions, 1)
        self.assertEqual([m for m in self._metriques(workspace) if m["type"] == "curation"], [])


if __name__ == "__main__":
    unittest.main()
