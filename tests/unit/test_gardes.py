"""Preuves des gardes de méthode dans les phases (U30).

@verifies docs/BACKLOG.md U30 — Spécification H16 et gardes de méthode
@verifies docs/SPEC_HARNAIS.md §H16.0 (jamais fatales, bornées, débrayables),
          §H16.1 (garde documentaire : WORKING vide verrouille l'action),
          §H16.2 (garde de prédiction : refus nommé sans prédiction, aucune
          action dépensée), §H16.3 (verdict exigé, trois issues dont
          « caduque », jetons lus où qu'ils soient, issue prudente), §H16.4
          (garde de persistance armée par complétion et game over), §H16.5
          (redemandes comptées au bilan), §H16.0.6 (la redemande du mode
          `state` énonce la forme complète attendue) — dans les deux modes de
          contexte
@verifies docs/SPEC_HARNAIS.md §H3.1 (`AVO_GARDES`, `AVO_GARDE_RETRIES`)

Le transport du client est injecté (aucun réseau, aucune cassette) : chaque test
scripte la suite exacte des réponses du modèle et observe ce que la boucle en
fait — l'artefact manquant refuse d'avancer, l'artefact présent déverrouille.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from avo.config import Config, Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP
from avo.loop import prompts
from avo.loop.boucle import BoucleAgent, _verdict_dans
from avo.loop.etats import Evenement, Phase
from avo.memory.notes import GUIDE, SCHEMA_NOTE_WRITE, WORKING, Notes, note_write
from avo.tools.registre import Outil, RegistreOutils, outil_depuis_schema

CLE = "sk-cle-gardes"


def _config(**env: str) -> Config:
    # Le mode est épinglé : les scénarios scriptés ci-dessous encodent les
    # échanges du chemin `transcript` ; les preuves du portage `state` le
    # surchargent explicitement. Le défaut du produit est prouvé par
    # tests/unit/test_config.py, pas ici.
    return charger(
        Mode.REJEU,
        env={
            "OLLAMA_HOST": "http://capture.invalide",
            "OLLAMA_API_KEY": CLE,
            "AVO_CONTEXT_MODE": "transcript",
            **env,
        },
        racine=Path("/inexistant"),
    )


@dataclass
class _Issue:
    observation: str
    evenement: Evenement


class _EnvironnementFactice:
    """Environnement en mémoire, sans aucune connaissance de jeu (§H8.2)."""

    def __init__(self, scenario: list[Evenement] | None = None) -> None:
        self.scenario = scenario or [Evenement.PREDICTION_CONFIRMEE]
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
        index = min(len(self.jouees) - 1, len(self.scenario) - 1)
        self._derniere = _Issue(f"grille-{len(self.jouees)}", self.scenario[index])
        return self._derniere


def _corps(contenu: str, tool_calls: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Corps de réponse minimal de la surface `/api/chat` (forme §H4.3)."""
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
    """Sert les réponses dans l'ordre et garde chaque corps émis pour inspection."""

    def __init__(self, reponses: list[dict[str, Any]]) -> None:
        self.reponses = list(reponses)
        self.corps_emis: list[dict[str, Any]] = []

    def __call__(self, url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
        self.corps_emis.append(json.loads(corps))
        if not self.reponses:
            raise AssertionError("plus de réponse scriptée : appel LLM de trop")
        return ReponseHTTP(200, json.dumps(self.reponses.pop(0)).encode())

    def invite(self, rang: int) -> str:
        return str(self.corps_emis[rang]["messages"][-1]["content"])


class _DecorTranscript(unittest.TestCase):
    """Décor commun : notes en répertoire temporaire, registre avec prédiction."""

    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.notes = Notes(Path(self._dossier.name) / "notes")
        self.environnement = _EnvironnementFactice()

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def _registre(self, prediction_requise: bool = True) -> RegistreOutils:
        proprietes: dict[str, Any] = {"prediction": {"type": "string"}}
        parametres: dict[str, Any] = {"type": "object", "properties": proprietes}
        if prediction_requise:
            parametres["required"] = ["prediction"]

        def avance(prediction: str | None = None) -> str:
            self.environnement.jouer("avance", prediction=prediction)
            return "action jouée"

        return RegistreOutils(
            [
                Outil(
                    nom="avance",
                    description="Joue une action d'environnement",
                    parametres=parametres,
                    fonction=avance,
                    etiquettes=frozenset({"action"}),
                ),
                outil_depuis_schema(
                    SCHEMA_NOTE_WRITE,
                    lambda name, content: note_write(self.notes, name, content),
                    ["notes"],
                ),
            ]
        )

    def _boucle(
        self, reponses: list[dict[str, Any]], **env: str
    ) -> tuple[BoucleAgent, _TransportScripte]:
        config = _config(**env)
        transport = _TransportScripte(reponses)
        client = LLMClient(config, transport=transport, dormir=lambda _: None)
        return (
            BoucleAgent(config, client, self._registre(), self.environnement, self.notes),
            transport,
        )


class TestGardeDocumentaire(_DecorTranscript):
    """§H16.1 : les outils d'action ne se déverrouillent pas sur un WORKING vide."""

    def test_le_premier_planning_recoit_la_demande_et_compose_k(self) -> None:
        boucle, transport = self._boucle(
            [
                _corps("je note", [_appel("note_write", {"name": "WORKING", "content": "plan"})]),
                _corps("j'agis", [_appel("avance", {"prediction": "un changement"})]),
                _corps("conforme.\nVERDICT: confirmee"),
            ]
        )
        tour = boucle.jouer_tour(1)
        self.assertEqual(tour.action, "avance")
        premiere_invite = transport.invite(0)
        self.assertIn("[GARDE]", premiere_invite)
        self.assertIn("WORKING.md", premiere_invite)
        self.assertIn("Tes notes persistantes", premiere_invite, "K est composé (§H16.1)")
        self.assertEqual(boucle.bilan.redemandes_gardes, 0, "artefact présent du premier coup")

    def test_l_artefact_manquant_est_redemande_puis_satisfait(self) -> None:
        boucle, transport = self._boucle(
            [
                _corps("je réfléchis sans rien écrire"),
                _corps("je note", [_appel("note_write", {"name": "WORKING", "content": "plan"})]),
                _corps("j'agis", [_appel("avance", {"prediction": "un changement"})]),
                _corps("conforme.\nVERDICT: confirmee"),
            ]
        )
        tour = boucle.jouer_tour(1)
        self.assertEqual(tour.action, "avance")
        self.assertEqual(boucle.bilan.redemandes_gardes, 1)
        self.assertIn(prompts.GARDE_DOCUMENTAIRE, transport.invite(1))

    def test_budget_epuise_clot_le_tour_sans_action_jamais_fatal(self) -> None:
        boucle, _transport = self._boucle(
            [
                _corps("rien"),
                _corps("toujours rien"),
                _corps("encore rien"),
            ]
        )
        tour = boucle.jouer_tour(1)
        self.assertIsNone(tour.action)
        self.assertEqual(self.environnement.jouees, [], "aucune action dépensée")
        self.assertIs(boucle.phase, Phase.PLANNING)
        self.assertEqual(boucle.bilan.redemandes_gardes, 2, "AVO_GARDE_RETRIES par défaut")

    def test_gardes_desactivees_restituent_le_comportement_anterieur(self) -> None:
        boucle, transport = self._boucle(
            [
                _corps("je planifie"),
                _corps("j'agis", [_appel("avance", {"prediction": "peu importe"})]),
                _corps("rien à signaler"),
            ],
            AVO_GARDES="false",
        )
        tour = boucle.jouer_tour(1)
        self.assertEqual(tour.action, "avance")
        self.assertEqual(boucle.bilan.redemandes_gardes, 0)
        self.assertNotIn("[GARDE]", transport.invite(0))
        self.assertNotIn("VERDICT", transport.invite(2))


class TestGardePrediction(_DecorTranscript):
    """§H16.2 : une action sans prédiction est refusée, rien n'est dépensé."""

    def setUp(self) -> None:
        super().setUp()
        self.notes.ecrire(WORKING, "je sais / j'ignore / je découvre")

    def test_l_appel_sans_prediction_est_refuse_et_ne_joue_rien(self) -> None:
        boucle, _transport = self._boucle(
            [
                _corps("je planifie"),
                _corps("j'agis", [_appel("avance", {})]),
            ]
        )
        tour = boucle.jouer_tour(1)
        self.assertIsNone(tour.action)
        self.assertEqual(self.environnement.jouees, [], "l'action refusée n'est pas jouée")
        self.assertEqual(boucle.bilan.actions_jeu, 0, "rien n'est compté au score")
        # L'erreur est rendue au modèle dans l'historique (§H7.4).
        messages = boucle.contexte.transcript.pour_api()
        erreurs = [
            message
            for message in messages
            if message.get("role") == "tool" and "prediction" in str(message.get("content"))
        ]
        self.assertTrue(erreurs, "l'erreur nomme l'argument manquant")

    def test_la_prediction_est_transmise_a_l_outil(self) -> None:
        boucle, _transport = self._boucle(
            [
                _corps("je planifie"),
                _corps("j'agis", [_appel("avance", {"prediction": "la grille change"})]),
                _corps("conforme.\nVERDICT: confirmee"),
            ]
        )
        tour = boucle.jouer_tour(1)
        self.assertEqual(tour.action, "avance")
        self.assertEqual(self.environnement.jouees[0][1], {"prediction": "la grille change"})


class TestGardeEvaluation(_DecorTranscript):
    """§H16.3 : prédit-contre-observé présenté, qualification exigée."""

    def setUp(self) -> None:
        super().setUp()
        self.notes.ecrire(WORKING, "artefact documentaire présent")

    def _reponses_jusqu_a_evaluation(self, *evaluations: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            _corps("je planifie"),
            _corps("j'agis", [_appel("avance", {"prediction": "la case s'allume"})]),
            *evaluations,
        ]

    def test_l_invite_cite_la_prediction_et_le_verdict_tranche(self) -> None:
        boucle, transport = self._boucle(
            self._reponses_jusqu_a_evaluation(_corps("conforme.\nVERDICT: confirmée"))
        )
        tour = boucle.jouer_tour(1)
        self.assertIs(tour.evenement, Evenement.PREDICTION_CONFIRMEE)
        self.assertIn("la case s'allume", transport.invite(2), "prédit-contre-observé (§H16.3)")
        self.assertIn("VERDICT", transport.invite(2))

    def test_le_verdict_explicite_prime_sur_l_heuristique_de_sous_chaine(self) -> None:
        boucle, _transport = self._boucle(
            self._reponses_jusqu_a_evaluation(
                _corps("aucune contradiction à signaler.\nVERDICT: confirmee")
            )
        )
        tour = boucle.jouer_tour(1)
        self.assertIs(
            tour.evenement,
            Evenement.PREDICTION_CONFIRMEE,
            "le mot « contradiction » dans la prose ne déclenche plus rien : le VERDICT tranche",
        )

    def test_verdict_contredit_declenche_le_bug_fixing(self) -> None:
        boucle, _transport = self._boucle(
            self._reponses_jusqu_a_evaluation(
                _corps("inattendu.\nVERDICT: contredite"),
                _corps("je révise mes hypothèses"),
            )
        )
        tour = boucle.jouer_tour(1)
        self.assertIs(tour.evenement, Evenement.CONTRADICTION)
        self.assertIs(tour.phase_finale, Phase.PLANNING, "le bug-fixing a rendu la main")

    def test_sans_verdict_redemande_puis_issue_prudente(self) -> None:
        boucle, transport = self._boucle(
            self._reponses_jusqu_a_evaluation(
                _corps("je décris sans qualifier"),
                _corps("toujours pas de qualification"),
                _corps("rien non plus"),
                _corps("je révise mes hypothèses"),
            )
        )
        tour = boucle.jouer_tour(1)
        self.assertIs(
            tour.evenement,
            Evenement.CONTRADICTION,
            "une prédiction non qualifiée est réputée contredite (§H16.3)",
        )
        self.assertEqual(boucle.bilan.redemandes_gardes, 2)
        self.assertIn(prompts.GARDE_VERDICT_REDEMANDE, transport.invite(3))


class TestGardePersistance(_DecorTranscript):
    """§H16.4 : complétion, game over ou intervention exigent une écriture de GUIDE."""

    def setUp(self) -> None:
        super().setUp()
        self.notes.ecrire(WORKING, "artefact documentaire présent")

    def test_la_completion_arme_la_garde_et_l_evaluation_porte_la_demande(self) -> None:
        self.environnement.scenario = [Evenement.NIVEAU_COMPLETE]
        boucle, transport = self._boucle(
            [
                _corps("je planifie"),
                _corps("j'agis", [_appel("avance", {"prediction": "le niveau se termine"})]),
                _corps(
                    "je retiens.\nVERDICT: confirmee",
                    [_appel("note_write", {"name": "GUIDE", "content": "durable"})],
                ),
            ]
        )
        tour = boucle.jouer_tour(1)
        self.assertIs(tour.evenement, Evenement.NIVEAU_COMPLETE)
        self.assertIn(prompts.GARDE_PERSISTANCE, transport.invite(2))
        self.assertEqual(self.notes.lire(GUIDE), "durable")
        self.assertEqual(boucle.bilan.redemandes_gardes, 0, "satisfaite dans l'évaluation même")

    def test_guide_non_ecrit_verrouille_l_action_du_tour_suivant(self) -> None:
        self.environnement.scenario = [Evenement.GAME_OVER, Evenement.PREDICTION_CONFIRMEE]
        boucle, _transport = self._boucle(
            [
                # Tour 1 : game over, l'évaluation n'écrit pas GUIDE.
                _corps("je planifie"),
                _corps("j'agis", [_appel("avance", {"prediction": "je gagne"})]),
                _corps("perdu.\nVERDICT: contredite"),
                _corps("je révise"),
                # Tour 2 : la demande est redemandée, satisfaite, puis l'action part.
                _corps("je planifie encore"),
                _corps(
                    "j'écris",
                    [_appel("note_write", {"name": "GUIDE", "content": "leçon du game over"})],
                ),
                _corps("j'agis", [_appel("avance", {"prediction": "autre chose"})]),
                _corps("conforme.\nVERDICT: confirmee"),
            ]
        )
        premier = boucle.jouer_tour(1)
        self.assertIs(premier.evenement, Evenement.GAME_OVER)
        second = boucle.jouer_tour(2)
        self.assertEqual(second.action, "avance")
        self.assertEqual(boucle.bilan.redemandes_gardes, 1, "une redemande au tour 2")
        self.assertEqual(self.notes.lire(GUIDE), "leçon du game over")

    def test_une_reecriture_a_l_identique_satisfait_la_garde(self) -> None:
        self.notes.ecrire(GUIDE, "déjà là")
        self.environnement.scenario = [Evenement.NIVEAU_COMPLETE]
        boucle, _transport = self._boucle(
            [
                _corps("je planifie"),
                _corps("j'agis", [_appel("avance", {"prediction": "fin de niveau"})]),
                _corps(
                    "rien de neuf.\nVERDICT: confirmee",
                    [_appel("note_write", {"name": "GUIDE", "content": "déjà là"})],
                ),
            ]
        )
        boucle.jouer_tour(1)
        self.assertEqual(
            boucle.bilan.redemandes_gardes,
            0,
            "le compteur d'écritures constate la confirmation, pas une différence (§H16.4)",
        )


class TestGardesModeEtat(unittest.TestCase):
    """§H16.1–§H16.3 portées au mode `state` : lignes PREDICTION/VERDICT, Σ.hypotheses."""

    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.notes = Notes(Path(self._dossier.name) / "notes")
        self.environnement = _EnvironnementFactice()

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

    def _boucle(
        self, reponses: list[dict[str, Any]], **env: str
    ) -> tuple[BoucleAgent, _TransportScripte]:
        config = _config(AVO_CONTEXT_MODE="state", **env)
        transport = _TransportScripte(reponses)
        client = LLMClient(config, transport=transport, dormir=lambda _: None)
        return (
            BoucleAgent(config, client, self._registre(), self.environnement, self.notes),
            transport,
        )

    @staticmethod
    def _pas(
        texte_avant: str, patch: dict[str, Any] | None = None, action: str = "avance"
    ) -> dict[str, Any]:
        bloc = json.dumps({"state_patch": patch or {}, "action": action})
        return _corps(f"{texte_avant}\n```json\n{bloc}\n```")

    def test_hypotheses_vides_retiennent_l_action_gratuite(self) -> None:
        boucle, transport = self._boucle(
            [
                self._pas("PREDICTION: quelque chose bouge"),
                self._pas(
                    "PREDICTION: quelque chose bouge",
                    {"hypotheses": ["la commande déplace un objet"]},
                ),
            ]
        )
        premier = boucle.jouer_tour(1)
        self.assertIsNone(premier.action)
        self.assertEqual(self.environnement.jouees, [], "l'action retenue est gratuite")
        second = boucle.jouer_tour(2)
        self.assertEqual(second.action, "avance")
        self.assertIn("hypotheses", transport.invite(1), "l'erreur nommée revient au pas suivant")

    def test_le_patch_du_pas_refuse_est_annule_avec_l_action(self) -> None:
        """§H16.1 : refus de garde = pas blanc atomique — Σ ne garde rien du pas refusé.

        Mesuré (journal 2026-09-02, suite 21) : le patch d'un pas retenu porte
        l'effet ATTENDU de l'action jamais jouée ; l'acquérir fait mentir Σ et
        les pas suivants en découlent (un `wait` indu, une action invalide).
        """
        boucle, _transport = self._boucle(
            [
                self._pas("PREDICTION: l'objet se déplace", {"position": {"x": 1, "y": 2}}),
                self._pas(
                    "PREDICTION: l'objet se déplace",
                    {
                        "hypotheses": ["la commande déplace un objet"],
                        "position": {"x": 1, "y": 2},
                    },
                ),
            ]
        )
        premier = boucle.jouer_tour(1)
        self.assertIsNone(premier.action)
        assert boucle.etat is not None
        self.assertIsNone(boucle.etat.champs["position"], "le patch du pas refusé n'atteint pas Σ")
        second = boucle.jouer_tour(2)
        self.assertEqual(second.action, "avance")
        self.assertEqual(dict(boucle.etat.champs["position"]), {"x": 1, "y": 2})

    def test_prediction_ligne_manquante_retient_puis_accompagne_l_action(self) -> None:
        boucle, transport = self._boucle(
            [
                self._pas("pas de ligne de prédiction", {"hypotheses": ["h"]}),
                self._pas("PREDICTION: la grille change", {"hypotheses": ["h"]}),
                self._pas("VERDICT: confirmee\nPREDICTION: la suite", {"hypotheses": ["h"]}),
            ]
        )
        premier = boucle.jouer_tour(1)
        self.assertIsNone(premier.action)
        second = boucle.jouer_tour(2)
        self.assertEqual(second.action, "avance")
        self.assertEqual(
            self.environnement.jouees[0][1],
            {"prediction": "la grille change"},
            "la prédiction est injectée dans l'appel d'outil (§H16.2)",
        )
        troisieme = boucle.jouer_tour(3)
        self.assertEqual(troisieme.action, "avance")
        self.assertIn(
            "la grille change", transport.invite(2), "la prédiction à qualifier est présentée"
        )
        self.assertIs(troisieme.evenement, Evenement.PREDICTION_CONFIRMEE)

    def test_le_refus_enonce_la_forme_complete_verdict_du(self) -> None:
        """§H16.0.6 : le refus porte la forme entière, verdict compris quand il est dû.

        Mesuré (journal 2026-09-02, suite 24) : une redemande qui ne nomme que
        la ligne manquante fait produire celle-là et perdre l'autre — quatre
        redemandes alternées sur un même tour.
        """
        boucle, transport = self._boucle(
            [
                self._pas("PREDICTION: p1", {"hypotheses": ["h"]}),
                self._pas("VERDICT: confirmee", {"hypotheses": ["h"]}),
                self._pas("VERDICT: confirmee\nPREDICTION: p2", {"hypotheses": ["h"]}),
            ]
        )
        premier = boucle.jouer_tour(1)
        self.assertEqual(premier.action, "avance")
        deuxieme = boucle.jouer_tour(2)
        self.assertIsNone(deuxieme.action, "PREDICTION manquante : action retenue")
        troisieme = boucle.jouer_tour(3)
        refus = transport.invite(2).splitlines()[0]
        self.assertIn("Forme complète attendue", refus)
        self.assertIn("VERDICT: confirmee", refus, "le verdict dû figure dans la forme")
        self.assertIn("PREDICTION:", refus)
        self.assertIn("state_patch", refus, "le bloc JSON figure dans la forme")
        self.assertEqual(troisieme.action, "avance", "la forme complète est rejouable telle quelle")

    def test_le_refus_sans_prediction_courante_n_exige_pas_de_verdict(self) -> None:
        """§H16.0.6 : sans prédiction à qualifier, la forme ne réclame pas de verdict."""
        boucle, transport = self._boucle(
            [
                self._pas("pas de ligne de prédiction", {"hypotheses": ["h"]}),
                self._pas("PREDICTION: p1", {"hypotheses": ["h"]}),
            ]
        )
        premier = boucle.jouer_tour(1)
        self.assertIsNone(premier.action)
        second = boucle.jouer_tour(2)
        refus = transport.invite(1).splitlines()[0]
        self.assertIn("Forme complète attendue", refus)
        self.assertNotIn("VERDICT", refus, "aucun verdict dû : la forme n'en réclame pas")
        self.assertEqual(second.action, "avance")

    def test_verdict_manquant_redemande_puis_issue_prudente(self) -> None:
        boucle, _transport = self._boucle(
            [
                self._pas("PREDICTION: p1", {"hypotheses": ["h"]}),
                self._pas("PREDICTION: p2", {"hypotheses": ["h"]}),
                self._pas("PREDICTION: p3", {"hypotheses": ["h"]}),
                self._pas("PREDICTION: p4", {"hypotheses": ["h"]}),
            ],
            AVO_GARDE_RETRIES="1",
        )
        premier = boucle.jouer_tour(1)
        self.assertEqual(premier.action, "avance", "premier pas : aucun verdict attendu")
        deuxieme = boucle.jouer_tour(2)
        self.assertIsNone(deuxieme.action, "verdict manquant : action retenue")
        troisieme = boucle.jouer_tour(3)
        self.assertEqual(troisieme.action, "avance", "budget épuisé : issue prudente, on avance")
        self.assertIs(
            troisieme.evenement,
            Evenement.CONTRADICTION,
            "la prédiction non qualifiée est réputée contredite (§H16.3)",
        )

    def test_verdict_caduque_satisfait_la_garde_sans_bug_fixing(self) -> None:
        """§H16.3 : « caduque » qualifie — l'action passe, Bug-Fixing ne s'arme pas."""
        boucle, _transport = self._boucle(
            [
                self._pas("PREDICTION: p1", {"hypotheses": ["h"]}),
                self._pas("VERDICT: non applicable\nPREDICTION: p2", {"hypotheses": ["h"]}),
            ]
        )
        premier = boucle.jouer_tour(1)
        self.assertEqual(premier.action, "avance")
        deuxieme = boucle.jouer_tour(2)
        self.assertEqual(deuxieme.action, "avance", "caduque qualifie : l'action passe")
        self.assertIs(
            deuxieme.evenement,
            Evenement.PREDICTION_CONFIRMEE,
            "caduque ne déclenche pas Bug-Fixing (§H16.3)",
        )
        self.assertEqual(boucle.bilan.redemandes_gardes, 0, "aucune redemande dépensée")


class TestLectureVerdict(unittest.TestCase):
    """§H16.3 : trois issues, jetons lus où qu'ils soient, ambiguïté redemandée.

    Mesure qui désigne la règle (journal 2026-09-02, série h25 bruit 20) : 17 des
    18 refus de verdict portaient une qualification explicite que la lecture
    stricte refusait — « non applicable », verdict en milieu de ligne, prose.
    """

    def test_les_trois_issues_et_leurs_familles(self) -> None:
        self.assertEqual(_verdict_dans("VERDICT: confirmee"), "confirmee")
        self.assertEqual(_verdict_dans("VERDICT: confirmée."), "confirmee")
        self.assertEqual(_verdict_dans("VERDICT: contredite"), "contredite")
        self.assertEqual(_verdict_dans("VERDICT: infirmée"), "contredite")
        self.assertEqual(_verdict_dans("VERDICT: caduque"), "caduque")
        self.assertEqual(_verdict_dans("VERDICT: non applicable (dépassée)"), "caduque")
        self.assertEqual(_verdict_dans("VERDICT: non_applicable"), "caduque")
        self.assertEqual(_verdict_dans("VERDICT: n/a"), "caduque")

    def test_le_jeton_se_lit_en_milieu_de_ligne(self) -> None:
        self.assertEqual(
            _verdict_dans("PREDICTION: l'objet est déplacé. VERDICT: confirmee"),
            "confirmee",
            "un verdict présent mais mal placé n'est pas une absence de verdict",
        )
        self.assertEqual(
            _verdict_dans("La prédiction était fausse. Donc VERDICT: contredite."),
            "contredite",
        )

    def test_familles_contradictoires_ou_absence_rendent_none(self) -> None:
        self.assertIsNone(_verdict_dans("aucune qualification ici"))
        self.assertIsNone(
            _verdict_dans("« VERDICT: confirmee » ou « VERDICT: contredite »"),
            "une réponse qui recopie la forme entière est ambiguë : redemandée",
        )
        self.assertIsNone(_verdict_dans("VERDICT: la prédiction reste à voir"))

    def test_occurrences_repetees_de_la_meme_famille_se_lisent(self) -> None:
        self.assertEqual(
            _verdict_dans("VERDICT: caduque\n…\nVERDICT: non applicable"),
            "caduque",
        )


class TestCompteurEcritures(unittest.TestCase):
    """§H16.4 : le compteur d'écritures des notes est monotone et par note."""

    def test_ecrire_incremente_lire_ne_touche_pas(self) -> None:
        with tempfile.TemporaryDirectory() as dossier:
            notes = Notes(Path(dossier))
            self.assertEqual(notes.ecritures(GUIDE), 0)
            notes.lire(GUIDE)
            self.assertEqual(notes.ecritures(GUIDE), 0)
            notes.ecrire(GUIDE, "a")
            notes.ecrire(GUIDE, "a")
            self.assertEqual(notes.ecritures(GUIDE), 2, "la réécriture à l'identique compte")
            self.assertEqual(notes.ecritures(WORKING), 0, "compteur par note")


if __name__ == "__main__":
    unittest.main()
