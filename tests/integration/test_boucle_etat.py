"""La boucle agent en mode `state`, de bout en bout, contre le rejeu HTTP réel.

@verifies docs/BACKLOG.md U27 — Mode d'exécution `state` de la boucle
@verifies docs/SPEC_HARNAIS.md §H15.1 (contrat de pas), §H15.2 (opérateur ⊕),
          §H15.4 (rollback-retry), §H15.5 (persistance de Σ),
          §H15.8 (un pas = un tour, résolution générique de l'action)

Même principe que `test_boucle_complete.py` : les réponses du modèle sont scriptées,
mais leur forme (corps de réponse) est celle réellement enregistrée chez le serveur, et
l'échange passe par le vrai rejoueur HTTP. Ici le contenu scripté est le bloc
```json``` à deux clés attendu par le mode `state`, jamais un `tool_calls`.
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
from avo.context.etat import RetriesEpuises
from avo.llm.client import LLMClient
from avo.loop.boucle import BoucleAgent
from avo.loop.etats import Evenement
from avo.memory.notes import Notes
from avo.memory.workspace import Workspace
from avo.tools.registre import Outil, RegistreOutils
from llm_replay.cassette import (
    AUTH_VALIDE,
    Cassette,
    Exchange,
    RequestRecord,
    ResponseRecord,
    premiere_conversation,
)
from llm_replay.server import creer_serveur

CASSETTE_REELLE = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")
CLE = "sk-cle-de-rejeu-de-la-boucle-etat"


def _gabarit_de_reponse() -> dict[str, Any]:
    return premiere_conversation(Cassette.lire(CASSETTE_REELLE))


@dataclass
class _Issue:
    observation: str
    evenement: Evenement


class _EnvironnementFactice:
    """Environnement en mémoire, identique en esprit à celui du mode transcript."""

    def __init__(self, scenario: list[Evenement]) -> None:
        self.scenario = scenario
        self.jouees: list[tuple[str, dict[str, Any]]] = []
        self._derniere: _Issue | None = None

    def observation(self) -> str:
        return f"grille-{len(self.jouees)}"

    def actions_disponibles(self) -> list[str]:
        return ["avance", "reset"]

    def derniere_issue(self) -> _Issue | None:
        return self._derniere

    def etat_terminal(self) -> str | None:
        """Jamais terminal ici : ces preuves éprouvent les pas, pas l'arrêt (§H8.3)."""
        return None

    def jouer(self, action: str, **parametres: Any) -> _Issue:
        self.jouees.append((action, parametres))
        index = min(len(self.jouees) - 1, len(self.scenario) - 1)
        self._derniere = _Issue(f"grille-{len(self.jouees)}", self.scenario[index])
        return self._derniere


def _registre(journal: list[str], environnement: _EnvironnementFactice) -> RegistreOutils:
    def avance() -> str:
        journal.append("avance")
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
            )
        ]
    )


def _bloc_json(state_patch: dict[str, Any], action: str) -> str:
    charge = {"state_patch": state_patch, "action": action}
    return f"Je raisonne un peu.\n```json\n{json.dumps(charge)}\n```"


class TestBoucleEtat(unittest.TestCase):
    """La boucle tourne réellement en mode `state`, en HTTP, sur un environnement factice."""

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

    def _servir(self, cassette: Path) -> str:
        self.serveur = creer_serveur(cassette.parent, port=0, cle_attendue=CLE)
        hote, port = self.serveur.server_address[0], self.serveur.server_address[1]
        self.fil = threading.Thread(target=self.serveur.serve_forever, daemon=True)
        self.fil.start()
        return f"http://{hote!s}:{port}"

    def _config(self, base: str, **surcharges: str) -> Config:
        # Mécanique du mode `state` hors gardes (§H16.0.4) ; les gardes ont
        # leurs propres preuves (test_gardes*, U30).
        env = {
            "OLLAMA_HOST": base,
            "OLLAMA_API_KEY": CLE,
            "AVO_CONTEXT_MODE": "state",
            "AVO_GARDES": "false",
            **surcharges,
        }
        return charger(Mode.REJEU, env=env, racine=Path("/inexistant"))

    def _boucle_scriptee(
        self,
        reponses: list[str],
        scenario_env: list[Evenement],
        tours_max: int = 1,
        workspace: Workspace | None = None,
        **surcharges: str,
    ) -> tuple[BoucleAgent, _EnvironnementFactice, list[str]]:
        """Même principe à deux passes que `test_boucle_complete.py` (mode `state`)."""
        journal: list[str] = []
        corps_emis: list[dict[str, Any]] = []

        def transport_capture(url: str, corps: bytes, entetes: Any, timeout: float) -> Any:
            corps_emis.append(json.loads(corps))
            reponse = copy.deepcopy(self.gabarit)
            reponse["message"]["content"] = reponses[(len(corps_emis) - 1) % len(reponses)]
            reponse["message"].pop("tool_calls", None)
            from avo.llm.client import ReponseHTTP

            return ReponseHTTP(200, json.dumps(reponse).encode())

        env_capture = _EnvironnementFactice(list(scenario_env))
        config_capture = charger(
            Mode.REJEU,
            env={
                "OLLAMA_HOST": "http://capture.invalide",
                "OLLAMA_API_KEY": CLE,
                "AVO_CONTEXT_MODE": "state",
                "AVO_GARDES": "false",
                **surcharges,
            },
            racine=Path("/inexistant"),
        )
        try:
            BoucleAgent(
                config_capture,
                LLMClient(config_capture, transport=transport_capture, dormir=lambda _: None),
                _registre([], env_capture),
                env_capture,
                Notes(self.racine / "notes_capture"),
            ).executer(tours_max=tours_max)
        except Exception:
            # La capture veut seulement les corps ÉMIS avant un arrêt fatal (par
            # exemple RetriesEpuises) : le second passage, servi en HTTP, est celui
            # que le test observe réellement lever ou non.
            pass

        cassette = Cassette()
        for index, corps in enumerate(corps_emis):
            reponse = copy.deepcopy(self.gabarit)
            reponse["message"]["content"] = reponses[index % len(reponses)]
            reponse["message"].pop("tool_calls", None)
            cassette.ajouter(
                Exchange(
                    request=RequestRecord.depuis("POST", "/api/chat", AUTH_VALIDE, corps),
                    response=ResponseRecord(
                        status=200, headers={"content-type": "application/json"}, body=reponse
                    ),
                    recorded_at="2026-08-30T00:00:00+00:00",
                    duration_ms=1,
                )
            )
        chemin = self.racine / "scenario_etat.jsonl"
        cassette.ecrire(chemin)
        base = self._servir(chemin)

        config = self._config(base, **surcharges)
        environnement = _EnvironnementFactice(list(scenario_env))
        boucle = BoucleAgent(
            config,
            LLMClient(config, dormir=lambda _: None),
            _registre(journal, environnement),
            environnement,
            self.notes,
            workspace=workspace,
        )
        return boucle, environnement, journal

    # -- preuves ---------------------------------------------------------------
    def test_un_pas_valide_joue_l_action_et_met_a_jour_sigma(self) -> None:
        boucle, environnement, journal = self._boucle_scriptee(
            [_bloc_json({"essai": 1, "hypotheses": ["h1"]}, "avance")],
            [Evenement.PREDICTION_CONFIRMEE],
        )
        bilan = boucle.executer(tours_max=1)
        self.assertEqual(bilan.actions_jeu, 1)
        self.assertEqual(journal, ["avance"])
        self.assertEqual(environnement.jouees, [("avance", {})])
        assert boucle.etat is not None
        self.assertEqual(boucle.etat.en_dict()["hypotheses"], ["h1"])
        self.assertIs(bilan.tours[0].evenement, Evenement.PREDICTION_CONFIRMEE)

    def test_un_seul_appel_llm_par_tour(self) -> None:
        """§H15.8 : contrairement au mode transcript, pas de multi-appel P->I->E."""
        espace = Workspace.ouvrir(
            self._config("http://inutilise.invalide"), "run-un-appel", racine=self.racine / "ws3"
        )
        boucle, _, _ = self._boucle_scriptee(
            [_bloc_json({}, "avance")], [Evenement.PREDICTION_CONFIRMEE], workspace=espace
        )
        boucle.executer(tours_max=1)
        appels = [ligne for ligne in espace.lire_metriques() if ligne["type"] == "llm"]
        self.assertEqual(len(appels), 1)
        self.assertEqual(appels[0]["phase"], "state")

    def test_une_cle_absente_du_patch_survit(self) -> None:
        """§H15.2 : Σ ⊕ ΔΣ ne réinitialise jamais un champ omis."""
        boucle, _, _ = self._boucle_scriptee(
            [
                _bloc_json({"hypotheses": ["h1"]}, "avance"),
                _bloc_json({"essai": 2}, "avance"),
            ],
            [Evenement.PREDICTION_CONFIRMEE] * 2,
            tours_max=2,
        )
        boucle.executer(tours_max=2)
        assert boucle.etat is not None
        self.assertEqual(boucle.etat.en_dict()["hypotheses"], ["h1"])
        self.assertEqual(boucle.etat.en_dict()["essai"], 2)

    def test_le_vidage_d_hypotheses_est_sans_effet_et_archive(self) -> None:
        """§H16.1 : un patch qui vide « hypotheses » non vide s'applique avec le
        champ conservé — le reste du patch et l'action jouent, l'écart est
        archivé (`hypotheses_conservees`, §H15.10).

        Mesuré (journal 2026-09-02, suite 23) : traité en `EtatInvalide` à
        rollback-retry, le vidage tuait en `RetriesEpuises` un run dont toutes
        les actions étaient correctes.
        """
        espace = Workspace.ouvrir(
            self._config("http://inutilise.invalide"), "run-vidage", racine=self.racine / "ws4"
        )
        boucle, environnement, _ = self._boucle_scriptee(
            [
                _bloc_json({"hypotheses": ["h1"]}, "avance"),
                _bloc_json({"hypotheses": [], "essai": 2}, "avance"),
            ],
            [Evenement.PREDICTION_CONFIRMEE] * 2,
            tours_max=2,
            workspace=espace,
        )
        bilan = boucle.executer(tours_max=2)
        self.assertEqual(bilan.retries_patch, 0, "le vidage n'est plus une tentative refusée")
        self.assertEqual(len(environnement.jouees), 2, "les deux actions jouent")
        assert boucle.etat is not None
        self.assertEqual(boucle.etat.en_dict()["hypotheses"], ["h1"])
        self.assertEqual(boucle.etat.en_dict()["essai"], 2)
        pas = espace.lire_pas()
        self.assertNotIn("hypotheses_conservees", pas[0])
        self.assertTrue(pas[1]["hypotheses_conservees"])

    def test_un_patch_malforme_est_retente_puis_reussit(self) -> None:
        """§H15.4 : rollback-retry, Σ n'est jamais modifié par la tentative refusée."""
        boucle, environnement, journal = self._boucle_scriptee(
            ["ceci n'est pas un bloc json", _bloc_json({}, "avance")],
            [Evenement.PREDICTION_CONFIRMEE],
        )
        bilan = boucle.executer(tours_max=1)
        self.assertEqual(bilan.tours[0].retries_patch, 1)
        self.assertEqual(bilan.retries_patch, 1)
        self.assertEqual(journal, ["avance"])
        self.assertEqual(environnement.jouees, [("avance", {})])

    def test_le_budget_de_retries_epuise_leve_une_erreur_fatale(self) -> None:
        """§H15.4 : jamais une boucle infinie, jamais un état par défaut trompeur."""
        boucle, _, _ = self._boucle_scriptee(
            ["texte sans bloc json valide"], [Evenement.PREDICTION_CONFIRMEE]
        )
        with self.assertRaises(RetriesEpuises):
            boucle.executer(tours_max=1)

    def test_une_action_inconnue_ne_joue_rien_et_se_signale_au_tour_suivant(self) -> None:
        boucle, environnement, journal = self._boucle_scriptee(
            [_bloc_json({}, "voler"), _bloc_json({}, "avance")],
            [Evenement.PREDICTION_CONFIRMEE],
            tours_max=2,
        )
        bilan = boucle.executer(tours_max=2)
        self.assertEqual(environnement.jouees, [("avance", {})])
        self.assertEqual(journal, ["avance"])
        self.assertIsNone(bilan.tours[0].evenement)
        self.assertIs(bilan.tours[1].evenement, Evenement.PREDICTION_CONFIRMEE)

    def test_la_ponctuation_trainante_du_nom_d_action_est_normalisee(self) -> None:
        """§H15.8 : « avance, » est un bruit de format, pas une action inconnue.

        Mesuré en conditions réelles (run `ab-u28-state`, 2026-09-01) : un tour
        entier perdu sur « action1, ». La normalisation ne touche que la
        ponctuation de bord du jeton de nom.
        """
        boucle, environnement, journal = self._boucle_scriptee(
            [_bloc_json({}, "avance,")], [Evenement.PREDICTION_CONFIRMEE]
        )
        boucle.executer(tours_max=1)
        self.assertEqual(environnement.jouees, [("avance", {})])
        self.assertEqual(journal, ["avance"])

    def test_la_syntaxe_d_appel_de_fonction_est_normalisee(self) -> None:
        """§H15.8 : « avance() » est un bruit de format, pas une action inconnue.

        Mesuré en conditions réelles (relevé live du banc, 2026-09-01) : cinq
        tours perdus sur « wait() ». La normalisation est purement syntaxique.
        """
        boucle, environnement, journal = self._boucle_scriptee(
            [_bloc_json({}, "avance()")], [Evenement.PREDICTION_CONFIRMEE]
        )
        boucle.executer(tours_max=1)
        self.assertEqual(environnement.jouees, [("avance", {})])
        self.assertEqual(journal, ["avance"])

    def test_sigma_est_persiste_dans_le_workspace_apres_chaque_tour(self) -> None:
        espace = Workspace.ouvrir(
            self._config("http://inutilise.invalide"), "run-etat", racine=self.racine / "ws"
        )
        boucle, _, _ = self._boucle_scriptee(
            [_bloc_json({"essai": 4}, "avance")],
            [Evenement.PREDICTION_CONFIRMEE],
            workspace=espace,
        )
        boucle.executer(tours_max=1)
        relu = espace.lire_etat()
        assert relu is not None
        self.assertEqual(relu.en_dict()["essai"], 4)

    def test_chaque_appel_est_archive_dans_pas_jsonl(self) -> None:
        """§H15.10 : la réponse brute et son issue sont archivées à chaque appel —
        patch malformé compris —, sans jamais entrer dans un prompt."""
        espace = Workspace.ouvrir(
            self._config("http://inutilise.invalide"), "run-archive", racine=self.racine / "ws3"
        )
        boucle, _, _ = self._boucle_scriptee(
            ["aucun bloc json ici", _bloc_json({"essai": 4}, "avance")],
            [Evenement.PREDICTION_CONFIRMEE],
            workspace=espace,
        )
        boucle.executer(tours_max=1)
        pas = espace.lire_pas()
        self.assertEqual([p["tour"] for p in pas], [1, 1])
        self.assertEqual(pas[0]["contenu"], "aucun bloc json ici")
        self.assertIn("erreur", pas[0])
        self.assertEqual(pas[1]["tentative"], 1)
        self.assertEqual(pas[1]["patch"], {"essai": 4})
        self.assertEqual(pas[1]["action"], "avance")
        # L'archive ne remonte pas dans le prompt : le second appel ne cite pas
        # la réponse brute du premier, seulement l'erreur nommée (§H15.8).
        self.assertNotIn("aucun bloc json ici", boucle.contexte.systeme)

    def test_un_workspace_avec_etat_existant_est_recharge(self) -> None:
        espace = Workspace.ouvrir(
            self._config("http://inutilise.invalide"), "run-reprise", racine=self.racine / "ws2"
        )
        from avo.context.etat import Etat

        espace.ecrire_etat(Etat.initial().fusionner({"essai": 9}))
        boucle, _, _ = self._boucle_scriptee(
            [_bloc_json({}, "avance")], [Evenement.PREDICTION_CONFIRMEE], workspace=espace
        )
        assert boucle.etat is not None
        self.assertEqual(boucle.etat.en_dict()["essai"], 9)

    def test_l_evenement_complete_par_l_environnement_prime(self) -> None:
        boucle, _, _ = self._boucle_scriptee(
            [_bloc_json({}, "avance")], [Evenement.NIVEAU_COMPLETE]
        )
        bilan = boucle.executer(tours_max=1)
        self.assertIs(bilan.tours[0].evenement, Evenement.NIVEAU_COMPLETE)
        self.assertEqual(bilan.niveaux_completes, 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
