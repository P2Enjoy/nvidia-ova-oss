"""La boucle agent, de bout en bout, contre le rejeu HTTP réel.

@verifies docs/BACKLOG.md U13 — Boucle agent P→I→E→B
@verifies docs/SPEC_HARNAIS.md §H8.1 (phases), §H8.2 (un tour), §H8.3 (arrêts :
          état terminal, bornes, priorité sur « tours_epuises »),
          §H7.1 (outils exposés selon l'état), §H5.1 (historique append-only)

Les réponses du modèle sont scriptées — c'est le comportement de l'AGENT qu'on met en
scène — mais leur **forme** est celle réellement enregistrée chez le serveur : la
cassette de test est bâtie à partir du corps de réponse authentique, dont seuls le
contenu et les appels d'outils varient. Le protocole reste donc mesuré, jamais inventé,
et l'échange passe par le vrai serveur de rejeu en HTTP.
"""

from __future__ import annotations

import copy
import json
import tempfile
import threading
import unittest
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from avo.config import Config, Mode, charger
from avo.llm.client import LLMClient
from avo.loop.boucle import OUTILS_PAR_PHASE, BoucleAgent
from avo.loop.etats import Evenement, Phase
from avo.memory.notes import SCHEMA_NOTE_WRITE, Notes, note_write
from avo.tools.registre import Outil, RegistreOutils, outil_depuis_schema
from llm_replay.cassette import AUTH_VALIDE, Cassette, Exchange, RequestRecord, ResponseRecord
from llm_replay.server import creer_serveur

CASSETTE_REELLE = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")
CLE = "sk-cle-de-rejeu-de-la-boucle"


def _gabarit_de_reponse() -> dict[str, Any]:
    """Corps de réponse RÉEL, qui sert de moule aux réponses scriptées."""
    for echange in Cassette.lire(CASSETTE_REELLE):
        corps = echange.response.body
        if echange.response.status == 200 and isinstance(corps, dict) and "message" in corps:
            return copy.deepcopy(corps)
    raise AssertionError("aucune réponse de conversation dans la cassette réelle")


@dataclass
class _Issue:
    observation: str
    evenement: Evenement


class _EnvironnementFactice:
    """Environnement en mémoire : aucune connaissance de jeu ne peut fuiter (§H8.2)."""

    def __init__(self, scenario: list[Evenement], terminal_apres: int | None = None) -> None:
        self.scenario = scenario
        #: Nombre d'actions au-delà duquel l'environnement se déclare terminal (§H8.3).
        self.terminal_apres = terminal_apres
        self.jouees: list[tuple[str, dict[str, Any]]] = []
        self._derniere: _Issue | None = None

    def observation(self) -> str:
        return f"grille-{len(self.jouees)}"

    def actions_disponibles(self) -> list[str]:
        return ["avance", "reset"]

    def derniere_issue(self) -> _Issue | None:
        return self._derniere

    def etat_terminal(self) -> str | None:
        if self.terminal_apres is not None and len(self.jouees) >= self.terminal_apres:
            return "victoire"
        return None

    def jouer(self, action: str, **parametres: Any) -> _Issue:
        """Appelée par l'OUTIL d'action, jamais par la boucle (§H8.1)."""
        self.jouees.append((action, parametres))
        index = min(len(self.jouees) - 1, len(self.scenario) - 1)
        self._derniere = _Issue(f"grille-{len(self.jouees)}", self.scenario[index])
        return self._derniere


class _Scenario:
    """Construit une cassette dont chaque requête attendue a sa réponse scriptée."""

    def __init__(self, dossier: Path) -> None:
        self.dossier = dossier
        self.gabarit = _gabarit_de_reponse()
        self.cassette = Cassette()

    def repondre(self, contenu: str, tool_calls: list[dict[str, Any]] | None = None) -> None:
        """Ajoute une réponse scriptée, servie par appariement sur le corps émis."""
        corps = copy.deepcopy(self.gabarit)
        corps["message"]["content"] = contenu
        if tool_calls is not None:
            corps["message"]["tool_calls"] = tool_calls
        else:
            corps["message"].pop("tool_calls", None)
        self._reponses.append(corps)

    _reponses: list[dict[str, Any]]

    def preparer(self, corps_requetes: list[dict[str, Any]]) -> Path:
        for requete, reponse in zip(corps_requetes, self._reponses, strict=True):
            self.cassette.ajouter(
                Exchange(
                    request=RequestRecord.depuis("POST", "/api/chat", AUTH_VALIDE, requete),
                    response=ResponseRecord(
                        status=200, headers={"content-type": "application/json"}, body=reponse
                    ),
                    recorded_at="2026-08-28T00:00:00+00:00",
                    duration_ms=1,
                )
            )
        chemin = self.dossier / "scenario.jsonl"
        self.cassette.ecrire(chemin)
        return chemin


class TestBoucleComplete(unittest.TestCase):
    """La boucle tourne réellement, en HTTP, sur un environnement factice."""

    def setUp(self) -> None:
        if not CASSETTE_REELLE.exists():
            self.skipTest("cassette absente : lancer « make record-llm »")
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        self.notes = Notes(self.racine / "notes")
        self.gabarit = _gabarit_de_reponse()
        self.serveur: ThreadingHTTPServer | None = None

    def tearDown(self) -> None:
        if self.serveur is not None:
            self.serveur.shutdown()
            self.serveur.server_close()
            self.fil.join(timeout=5)
        self._dossier.cleanup()

    # -- construction du décor -------------------------------------------------
    def _registre(
        self, journal: list[str], environnement: _EnvironnementFactice | None = None
    ) -> RegistreOutils:
        def avance() -> str:
            journal.append("avance")
            if environnement is not None:
                environnement.jouer("avance")
            return "action jouée"

        return RegistreOutils(
            [
                Outil(
                    nom="avance",
                    description="Joue une action d'environnement",
                    parametres={"type": "object", "properties": {}},
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

    def _servir(self, cassette: Path) -> str:
        self.serveur = creer_serveur(cassette.parent, port=0, cle_attendue=CLE)
        hote, port = self.serveur.server_address[0], self.serveur.server_address[1]
        self.fil = threading.Thread(target=self.serveur.serve_forever, daemon=True)
        self.fil.start()
        return f"http://{hote!s}:{port}"

    def _config(self, base: str, **surcharges: str) -> Config:
        # Ces preuves éprouvent la mécanique de la boucle hors gardes ; §H16.0.4 :
        # `AVO_GARDES=false` restitue exactement le comportement antérieur. Les
        # gardes ont leurs propres preuves (test_gardes*, U30).
        env = {"OLLAMA_HOST": base, "OLLAMA_API_KEY": CLE, "AVO_GARDES": "false", **surcharges}
        return charger(Mode.REJEU, env=env, racine=Path("/inexistant"))

    def _boucle_scriptee(
        self,
        reponses: list[tuple[str, list[dict[str, Any]] | None]],
        scenario_env: list[Evenement],
        tours_max: int = 1,
        terminal_apres: int | None = None,
        **surcharges: str,
    ) -> tuple[BoucleAgent, _EnvironnementFactice, list[str]]:
        """Monte une boucle dont chaque appel au modèle a sa réponse préparée.

        La cassette est bâtie en deux temps : on laisse d'abord la boucle émettre ses
        requêtes pour les capturer, ce qui garantit que la cassette porte EXACTEMENT
        les corps que la boucle produit. Les deux passes emploient le MÊME
        `tours_max`, sans quoi les corps émis divergeraient.
        """
        journal: list[str] = []
        corps_emis: list[dict[str, Any]] = []

        def transport_capture(url: str, corps: bytes, entetes: Any, timeout: float) -> Any:
            corps_emis.append(json.loads(corps))
            reponse = copy.deepcopy(self.gabarit)
            # Le motif de tour se répète : sans cela, la dernière réponse figée
            # supprimerait toute action des tours suivants et la borne d'actions ne
            # serait jamais atteinte.
            contenu, appels = reponses[(len(corps_emis) - 1) % len(reponses)]
            reponse["message"]["content"] = contenu
            if appels is not None:
                reponse["message"]["tool_calls"] = appels
            else:
                reponse["message"].pop("tool_calls", None)
            from avo.llm.client import ReponseHTTP

            return ReponseHTTP(200, json.dumps(reponse).encode())

        # 1er passage : capture des corps réellement émis par la boucle.
        env_capture = _EnvironnementFactice(list(scenario_env), terminal_apres=terminal_apres)
        config_capture = charger(
            Mode.REJEU,
            env={
                "OLLAMA_HOST": "http://capture.invalide",
                "OLLAMA_API_KEY": CLE,
                "AVO_GARDES": "false",
                **surcharges,
            },
            racine=Path("/inexistant"),
        )
        BoucleAgent(
            config_capture,
            LLMClient(config_capture, transport=transport_capture, dormir=lambda _: None),
            self._registre([], env_capture),
            env_capture,
            Notes(self.racine / "notes_capture"),
        ).executer(tours_max=tours_max)

        # 2e passage : la même séquence, servie en HTTP par le vrai rejoueur.
        scenario = _Scenario(self.racine)
        scenario._reponses = []
        # Une réponse par requête réellement émise, en répétant la dernière comme le
        # fait le transport de capture : la boucle peut enchaîner plus de tours que
        # le scénario n'a d'entrées.
        for index in range(len(corps_emis)):
            contenu, appels = reponses[index % len(reponses)]
            scenario.repondre(contenu, appels)
        cassette = scenario.preparer(corps_emis)
        base = self._servir(cassette)

        config = self._config(base, **surcharges)
        environnement = _EnvironnementFactice(list(scenario_env), terminal_apres=terminal_apres)
        boucle = BoucleAgent(
            config,
            LLMClient(config, dormir=lambda _: None),
            self._registre(journal, environnement),
            environnement,
            self.notes,
        )
        return boucle, environnement, journal

    # -- preuves ---------------------------------------------------------------
    def test_un_tour_complet_traverse_les_phases_et_joue_une_action(self) -> None:
        appel_action = [{"function": {"name": "avance", "arguments": {}}}]
        boucle, environnement, journal = self._boucle_scriptee(
            [
                ("je vais avancer, j'attends un déplacement", None),
                ("j'avance", appel_action),
                ("le déplacement est conforme", None),
            ],
            [Evenement.PREDICTION_CONFIRMEE],
        )
        bilan = boucle.executer(tours_max=1)
        self.assertEqual(len(bilan.tours), 1)
        self.assertEqual(bilan.actions_jeu, 1)
        self.assertEqual(journal, ["avance"])
        self.assertEqual(environnement.jouees, [("avance", {})])
        self.assertIs(bilan.tours[0].evenement, Evenement.PREDICTION_CONFIRMEE)
        self.assertIs(boucle.phase, Phase.PLANNING)

    def test_une_contradiction_declaree_declenche_le_bug_fixing(self) -> None:
        appel_action = [{"function": {"name": "avance", "arguments": {}}}]
        boucle, _, _ = self._boucle_scriptee(
            [
                ("je vais avancer", None),
                ("j'avance", appel_action),
                ("ma prédiction est contredite : rien n'a bougé", None),
                ("je révise mon modèle", None),
            ],
            [Evenement.PREDICTION_CONFIRMEE],
        )
        bilan = boucle.executer(tours_max=1)
        self.assertIs(bilan.tours[0].evenement, Evenement.CONTRADICTION)
        self.assertIs(boucle.phase, Phase.PLANNING)

    def test_l_environnement_prime_sur_ce_que_dit_le_modele(self) -> None:
        """Un niveau complété est un fait, pas une affirmation du modèle."""
        appel_action = [{"function": {"name": "avance", "arguments": {}}}]
        boucle, _, _ = self._boucle_scriptee(
            [
                ("j'avance", None),
                ("j'avance", appel_action),
                ("ma prédiction est contredite", None),
            ],
            [Evenement.NIVEAU_COMPLETE],
        )
        bilan = boucle.executer(tours_max=1)
        self.assertIs(bilan.tours[0].evenement, Evenement.NIVEAU_COMPLETE)
        self.assertEqual(bilan.niveaux_completes, 1)
        self.assertEqual(bilan.actions_niveau, 0, "le compteur de niveau repart à zéro")

    def test_la_borne_de_jeu_arrete_proprement_en_la_nommant(self) -> None:
        appel_action = [{"function": {"name": "avance", "arguments": {}}}]
        boucle, _, _ = self._boucle_scriptee(
            [
                ("je vais avancer", None),
                ("j'avance", appel_action),
                ("conforme", None),
            ],
            [Evenement.PREDICTION_CONFIRMEE] * 4,
            tours_max=6,
            AVO_ACTIONS_MAX_JEU="2",
        )
        bilan = boucle.executer(tours_max=6)
        self.assertEqual(bilan.actions_jeu, 2)
        self.assertIn("borne d'actions du jeu", bilan.arret)
        self.assertIn("2", bilan.arret)

    def test_l_etat_terminal_arrete_la_boucle_sans_nouvel_appel(self) -> None:
        """§H8.3 : l'environnement terminal clôt le run, plus aucun appel au modèle."""
        appel_action = [{"function": {"name": "avance", "arguments": {}}}]
        boucle, environnement, journal = self._boucle_scriptee(
            [
                ("je vais avancer", None),
                ("j'avance", appel_action),
                ("conforme, tout est accompli", None),
            ],
            [Evenement.NIVEAU_COMPLETE],
            tours_max=4,
            terminal_apres=1,
        )
        bilan = boucle.executer(tours_max=4)
        self.assertEqual(bilan.arret, "victoire")
        self.assertEqual(len(bilan.tours), 1, "aucun tour joué après l'état terminal")
        self.assertEqual(journal, ["avance"], "une seule action, aucune après la fin")
        self.assertEqual(environnement.jouees, [("avance", {})])

    def test_l_etat_terminal_au_dernier_tour_prime_tours_epuises(self) -> None:
        """§H8.3 : une tâche accomplie au dernier tour ne se clôt pas « tours_epuises »."""
        appel_action = [{"function": {"name": "avance", "arguments": {}}}]
        boucle, _, _ = self._boucle_scriptee(
            [
                ("je vais avancer", None),
                ("j'avance", appel_action),
                ("conforme", None),
            ],
            [Evenement.NIVEAU_COMPLETE],
            tours_max=1,
            terminal_apres=1,
        )
        bilan = boucle.executer(tours_max=1)
        self.assertEqual(bilan.arret, "victoire")
        self.assertEqual(len(bilan.tours), 1)

    def test_un_tour_sans_appel_d_action_n_en_invente_pas(self) -> None:
        boucle, environnement, journal = self._boucle_scriptee(
            [("je réfléchis encore", None), ("je ne suis pas prêt", None)],
            [Evenement.PREDICTION_CONFIRMEE],
        )
        bilan = boucle.executer(tours_max=1)
        self.assertEqual(bilan.actions_jeu, 0)
        self.assertEqual(environnement.jouees, [])
        self.assertEqual(journal, [])
        self.assertIs(boucle.phase, Phase.PLANNING)

    def test_l_historique_reste_append_only_sur_tout_le_tour(self) -> None:
        appel_action = [{"function": {"name": "avance", "arguments": {}}}]
        boucle, _, _ = self._boucle_scriptee(
            [("je vais avancer", None), ("j'avance", appel_action), ("conforme", None)],
            [Evenement.PREDICTION_CONFIRMEE],
        )
        avant = boucle.contexte.transcript
        boucle.executer(tours_max=1)
        self.assertTrue(boucle.contexte.transcript.prolonge(avant))
        self.assertGreater(len(boucle.contexte.transcript), len(avant))

    def test_les_outils_d_action_ne_sont_exposes_qu_a_l_implementation(self) -> None:
        """§H7.1 : hors de cet état, le modèle ne peut pas dépenser une action."""
        self.assertEqual(OUTILS_PAR_PHASE[Phase.IMPLEMENTATION], ("action",))
        for phase in (Phase.PLANNING, Phase.EVALUATION, Phase.BUG_FIXING):
            with self.subTest(phase=phase):
                self.assertNotIn("action", OUTILS_PAR_PHASE[phase])

    def test_le_bilan_porte_la_version_des_prompts(self) -> None:
        """Un rapport doit dire sous quelle formulation il a été obtenu."""
        appel_action = [{"function": {"name": "avance", "arguments": {}}}]
        boucle, _, _ = self._boucle_scriptee(
            [("je vais avancer", None), ("j'avance", appel_action), ("conforme", None)],
            [Evenement.PREDICTION_CONFIRMEE],
        )
        resume = boucle.executer(tours_max=1).resume()
        self.assertIn("prompts_version", resume)
        self.assertEqual(resume["actions_jeu"], 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
