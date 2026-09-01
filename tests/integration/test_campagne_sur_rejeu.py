"""Une mini-campagne réelle contre les deux rejeux, puis sa reprise.

@verifies docs/BACKLOG.md U23 — Runner de campagne et rapport
@verifies docs/SPEC_ARCAGI3.md §A7.1 (runner), §A7.3 (rapport), §A7.4 (état de
          campagne, reprise sans rejouer les jeux terminés), §A6 (RHAE mesuré)
@verifies docs/SPEC_HARNAIS.md §H6.1 (artefacts du run), §H8.4 (branchements de la
          boucle : métriques et transcripts réellement écrits), §H13.2 (reprise)

L'agent est scripté — c'est le RUNNER qu'on met en scène — mais tout le reste est
réel : deux serveurs HTTP, un workspace sur disque, un dépôt de lignée, et les
artefacts relus depuis les fichiers que le run a écrits.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest import mock

from arc_replay.serveur import creer_serveur as creer_serveur_arc
from avo import cli
from avo.arc.campagne import ETAT, EtatCampagne, Plafonds, executer_campagne, reprendre_campagne
from avo.arc.client import ArcClient, ArcProtocoleError
from avo.config import Config, Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP
from avo.loop import prompts
from avo.memory.workspace import Workspace
from llm_replay.cassette import AUTH_VALIDE, Cassette, Exchange, RequestRecord, ResponseRecord
from llm_replay.server import creer_serveur as creer_serveur_llm

CASSETTE_REELLE = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")
CLE = "sk-cle-de-rejeu-de-la-campagne"
JEU = "cible-synthetique"

#: Clic qui manque la cible à coup sûr : le curseur y démarre, la cible est ailleurs.
CLIC_MANQUE = {"row": 32, "col": 32}

#: Trois clics manqués perdent la tentative, le quatrième tour la relance.
ACTIONS = [
    ("action6", CLIC_MANQUE),
    ("action6", CLIC_MANQUE),
    ("action6", CLIC_MANQUE),
    ("reset", {}),
]
TOURS = 4


class _ClientLLMInterdit(LLMClient):
    """Client qui refuse d'être appelé : sert à prouver qu'un jeu n'a PAS été rejoué."""

    def chat(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("le modèle a été appelé alors qu'aucun jeu ne restait à jouer")


class _SocleCampagneSurRejeu(unittest.TestCase):
    """Pile de rejeu montée et démontée par test : socle partagé des scénarios.

    Les classes de scénario en héritent au lieu d'emprunter ses méthodes attribut
    par attribut — l'emprunt inter-classes rendait les types de `self` invalides
    (mypy strict, corrigé le 2026-09-01).
    """

    def setUp(self) -> None:
        if not CASSETTE_REELLE.exists():
            self.skipTest("cassette absente : lancer « make record-llm »")
        self.serveur_arc: ThreadingHTTPServer = creer_serveur_arc(port=0, niveaux=3)
        hote, port = self.serveur_arc.server_address[0], self.serveur_arc.server_address[1]
        self.fil_arc = threading.Thread(target=self.serveur_arc.serve_forever, daemon=True)
        self.fil_arc.start()
        self.base_arc = f"http://{hote!s}:{port}"
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        self.gabarit = self._gabarit()
        self.serveur_llm: ThreadingHTTPServer | None = None

    def tearDown(self) -> None:
        if self.serveur_llm is not None:
            self.serveur_llm.shutdown()
            self.serveur_llm.server_close()
            self.fil_llm.join(timeout=5)
        self.serveur_arc.shutdown()
        self.serveur_arc.server_close()
        self.fil_arc.join(timeout=5)
        self._dossier.cleanup()

    # -- décor -----------------------------------------------------------------
    @staticmethod
    def _gabarit() -> dict[str, Any]:
        for echange in Cassette.lire(CASSETTE_REELLE):
            corps = echange.response.body
            if echange.response.status == 200 and isinstance(corps, dict) and "message" in corps:
                return copy.deepcopy(corps)
        raise AssertionError("aucune réponse de conversation dans la cassette réelle")

    def _config(self, base_llm: str) -> Config:
        return charger(
            Mode.REJEU,
            # Mécanique de campagne hors gardes (§H16.0.4) ; les gardes ont
            # leurs propres preuves (test_gardes*, U30).
            env={
                "ARC_BASE_URL": self.base_arc,
                "ARC_API_KEY": "cle-de-test",
                "OLLAMA_HOST": base_llm,
                "OLLAMA_API_KEY": CLE,
                "AVO_GARDES": "false",
            },
            racine=Path("/inexistant"),
        )

    @staticmethod
    def _plafonds() -> Plafonds:
        return Plafonds(actions_niveau=100, actions_jeu=200, tours_max=TOURS)

    def _repondre(self, corps: dict[str, Any], rang: int) -> dict[str, Any]:
        reponse = copy.deepcopy(self.gabarit)
        if prompts.IMPLEMENTATION in corps["messages"][-1]["content"]:
            nom, arguments = ACTIONS[min(rang, len(ACTIONS) - 1)]
            reponse["message"]["content"] = "je joue une commande"
            reponse["message"]["tool_calls"] = [{"function": {"name": nom, "arguments": arguments}}]
        else:
            reponse["message"]["content"] = "j'observe et je note ce que je vois"
            reponse["message"].pop("tool_calls", None)
        return reponse

    def _servir(self, cassette: Path) -> str:
        self.serveur_llm = creer_serveur_llm(cassette.parent, port=0, cle_attendue=CLE)
        hote, port = self.serveur_llm.server_address[0], self.serveur_llm.server_address[1]
        self.fil_llm = threading.Thread(target=self.serveur_llm.serve_forever, daemon=True)
        self.fil_llm.start()
        return f"http://{hote!s}:{port}"

    def _preparer_cassette(self, run_id: str, config_capture: Config | None = None) -> str:
        """Passe de capture : joue la campagne pour relever les corps réellement émis.

        La cassette servie ensuite porte EXACTEMENT ces corps : si la seconde passe
        divergeait d'un octet, l'appariement par empreinte échouerait.
        """
        corps_emis: list[dict[str, Any]] = []
        rang = 0

        def transport(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
            nonlocal rang
            charge = json.loads(corps)
            corps_emis.append(charge)
            reponse = self._repondre(charge, rang)
            if reponse["message"].get("tool_calls"):
                rang += 1
            return ReponseHTTP(200, json.dumps(reponse).encode())

        config_capture = config_capture or self._config("http://capture.invalide")
        executer_campagne(
            config_capture,
            Workspace.ouvrir(config_capture, f"{run_id}-capture", racine=self.racine),
            self._plafonds(),
            jeux=[JEU],
            client_llm=LLMClient(config_capture, transport=transport, dormir=lambda _: None),
        )

        cassette = Cassette()
        rang = 0
        for charge in corps_emis:
            reponse = self._repondre(charge, rang)
            if reponse["message"].get("tool_calls"):
                rang += 1
            cassette.ajouter(
                Exchange(
                    request=RequestRecord.depuis("POST", "/api/chat", AUTH_VALIDE, charge),
                    response=ResponseRecord(
                        status=200, headers={"content-type": "application/json"}, body=reponse
                    ),
                    recorded_at="2026-08-28T00:00:00+00:00",
                    duration_ms=1,
                )
            )
        chemin = self.racine / f"{run_id}.jsonl"
        cassette.ecrire(chemin)
        return self._servir(chemin)

    def _campagne(self, run_id: str) -> tuple[Any, Workspace]:
        """La campagne jouée pour de bon, servie en HTTP par le vrai rejoueur."""
        config = self._config(self._preparer_cassette(run_id))
        espace = Workspace.ouvrir(config, run_id, racine=self.racine)
        resultat = executer_campagne(
            config,
            espace,
            self._plafonds(),
            jeux=[JEU],
            client_llm=LLMClient(config, dormir=lambda _: None),
        )
        return resultat, espace


class TestCampagneSurRejeu(_SocleCampagneSurRejeu):
    # -- preuves ---------------------------------------------------------------
    def test_une_mini_campagne_joue_mesure_et_rend_compte(self) -> None:
        resultat, espace = self._campagne("run-mini")

        self.assertEqual(len(resultat.jeux), 1)
        jeu = resultat.jeux[0]
        self.assertEqual(jeu.game_id, JEU)
        self.assertEqual(jeu.actions, 4, "trois clics manqués puis une relance")
        self.assertEqual(jeu.game_overs, 1)
        self.assertEqual(jeu.niveaux_completes, 0)
        self.assertEqual(len(jeu.niveaux), 3, "les trois niveaux du jeu pèsent (§A6.1 bis)")
        self.assertEqual(jeu.rhae.valeur, 0.0, "aucun niveau complété")
        self.assertEqual(resultat.score_global, 0.0)
        self.assertIsNotNone(resultat.card_id)

    def test_les_artefacts_du_run_existent_et_disent_la_verite(self) -> None:
        """§H6.1 : le run s'audite sans le dépôt — donc tout doit être sur le disque."""
        resultat, espace = self._campagne("run-artefacts")

        self.assertTrue(espace.rapport.exists(), "le rapport est un invariant du runner")
        rapport = espace.rapport.read_text(encoding="utf-8")
        for attendu in ("Par jeu", "Détail par niveau", "Coûts", "Événements", "Limites"):
            with self.subTest(section=attendu):
                self.assertIn(attendu, rapport)
        self.assertIn("pas comparable", rapport, "un score de rejeu n'est pas un score ARC")
        self.assertIn(JEU, rapport)

        self.assertTrue((espace.frames / JEU / "niveau_01.jsonl").exists())
        self.assertTrue(
            (espace.chemin / "lineage" / JEU / ".git").is_dir(), "lignée isolée (§H9.3)"
        )
        self.assertTrue(any(espace.transcripts.iterdir()), "le segment est archivé (§H11.3)")

    def test_les_metriques_portent_ce_que_le_rapport_annonce(self) -> None:
        """§H8.4 : les branchements écrivent réellement, sinon le rapport serait creux."""
        resultat, espace = self._campagne("run-metriques")
        types = [ligne["type"] for ligne in espace.lire_metriques()]

        self.assertIn("llm", types)
        self.assertIn("action", types)
        self.assertIn("arret", types)
        self.assertIn("jeu", types)
        self.assertEqual(types.count("action"), 4, "une métrique par action jouée")
        appels = types.count("llm")
        self.assertGreaterEqual(appels, 3 * TOURS, "au moins P, I et E par tour")
        self.assertIn(
            f"appels au modèle : **{appels}**", espace.rapport.read_text(encoding="utf-8")
        )

    def test_l_etat_de_campagne_est_ecrit_apres_le_jeu(self) -> None:
        """§A7.4 : une interruption ne coûte au plus qu'un jeu."""
        _, espace = self._campagne("run-etat")
        etat = EtatCampagne.lire(espace)
        self.assertEqual(etat.jeux_demandes, [JEU])
        self.assertEqual([resultat.game_id for resultat in etat.resultats], [JEU])
        self.assertEqual(etat.restants(), [], "plus rien à jouer")
        self.assertIsNotNone(etat.card_id)
        self.assertTrue((espace.chemin / ETAT).exists())

    def test_la_reprise_ne_rejoue_pas_un_jeu_termine(self) -> None:
        """§H13.2 : la preuve est qu'aucun appel au modèle n'est nécessaire."""
        avant, espace = self._campagne("run-reprise")
        config = self._config("http://interdit.invalide")

        repris = reprendre_campagne(
            config, self.racine, "run-reprise", client_llm=_ClientLLMInterdit(config)
        )

        self.assertEqual([jeu.game_id for jeu in repris.jeux], [JEU])
        self.assertEqual(repris.jeux[0].actions, avant.jeux[0].actions)
        self.assertEqual(repris.score_global, avant.score_global)
        self.assertEqual(repris.card_id, avant.card_id, "le scorecard ouvert est réutilisé")

    def test_la_cli_reelle_joue_la_campagne_et_annonce_le_resultat(self) -> None:
        """MASTER_PLAN §5 : le produit est une CLI ; c'est `main()` qu'il faut exécuter."""
        # La CLI résout sa configuration depuis l'environnement RÉEL puis `.env` : la
        # passe de capture doit donc la résoudre exactement de la même façon, sans
        # quoi un seul champ d'options — `num_ctx` par exemple — suffirait à faire
        # diverger le corps émis et l'appariement de la cassette échouerait.
        commun = {
            "ARC_BASE_URL": self.base_arc,
            "ARC_API_KEY": "cle-de-test",
            "OLLAMA_API_KEY": CLE,
            "AVO_RUNS_DIR": str(self.racine),
            "AVO_GARDES": "false",
        }
        with mock.patch.dict(os.environ, {**commun, "OLLAMA_HOST": "http://capture.invalide"}):
            config_capture = charger("replay")
        base_llm = self._preparer_cassette("run-cli", config_capture)

        sortie = io.StringIO()
        with (
            mock.patch.dict(os.environ, {**commun, "OLLAMA_HOST": base_llm}, clear=False),
            contextlib.redirect_stdout(sortie),
        ):
            code = cli.main(
                [
                    "run-arc",
                    "--mode",
                    "replay",
                    "--games",
                    JEU,
                    "--run-id",
                    "run-cli",
                    "--tours-max",
                    str(TOURS),
                    "--actions-max-niveau",
                    "100",
                    "--actions-max-jeu",
                    "200",
                ]
            )

        self.assertEqual(code, 0)
        texte = sortie.getvalue()
        self.assertIn("campagne terminée : 1 jeu(x)", texte)
        self.assertIn(f"{JEU} : 0/3 niveaux, 4 actions, RHAE 0.00", texte)
        self.assertIn("score global : 0.00", texte)
        self.assertIn("report.md", texte)
        self.assertTrue((self.racine / "run-cli" / "report.md").exists())

    def test_la_cli_refuse_une_campagne_live_sans_accord(self) -> None:
        """§A7.2 : le refus est ce que l'opérateur voit, avec le motif."""
        environnement = {
            "ARC_API_KEY": "cle-de-test",
            "OLLAMA_HOST": "https://exemple.invalide",
            "OLLAMA_API_KEY": CLE,
            "OLLAMA_CONTEXT_LENGTH": "229376",
            "AVO_RUNS_DIR": str(self.racine),
        }
        erreurs = io.StringIO()
        with (
            mock.patch.dict(os.environ, environnement, clear=False),
            contextlib.redirect_stderr(erreurs),
        ):
            code = cli.main(["run-arc", "--mode", "live", "--run-id", "run-refus"])

        self.assertEqual(code, 2)
        self.assertIn("campagne refusée", erreurs.getvalue())
        self.assertIn("--j-autorise-la-publication", erreurs.getvalue())

    def test_reprendre_un_run_inexistant_est_refuse(self) -> None:
        config = self._config("http://interdit.invalide")
        with self.assertRaises(Exception) as capture:
            reprendre_campagne(config, self.racine, "run-fantome")
        self.assertIn("run-fantome", str(capture.exception))


class _ClientAvecFantome(ArcClient):
    """Client réel dont le catalogue liste un jeu que le backend refuse (§A1.4)."""

    def games(self) -> list[dict[str, Any]]:
        return [*super().games(), {"game_id": "fantome", "baseline_actions": [5, 5]}]

    def reset(
        self, game_id: str | None = None, card_id: str | None = None, guid: str | None = None
    ) -> Any:
        if game_id == "fantome":
            raise ArcProtocoleError("/api/cmd/RESET : HTTP 400 — game fantome not found")
        return super().reset(game_id=game_id, card_id=card_id, guid=guid)


class TestJeuRefuse(_SocleCampagneSurRejeu):
    """§A7.4 (2026-09-01) : un jeu refusé est nommé, la campagne poursuit et ferme."""

    def test_un_jeu_refuse_est_nomme_et_la_campagne_poursuit(self) -> None:
        config = self._config(self._preparer_cassette("run-refuse"))
        espace = Workspace.ouvrir(config, "run-refuse", racine=self.racine)
        resultat = executer_campagne(
            config,
            espace,
            self._plafonds(),
            jeux=["fantome", JEU],
            client_llm=LLMClient(config, dormir=lambda _: None),
            fabrique_arc=lambda: _ClientAvecFantome(config),
        )

        self.assertEqual([entree["jeu"] for entree in resultat.refus], ["fantome"])
        self.assertIn("not found", resultat.refus[0]["motif"])
        self.assertEqual([jeu.game_id for jeu in resultat.jeux], [JEU], "la campagne a poursuivi")
        self.assertIsNotNone(resultat.card_id, "le scorecard a été ouvert puis fermé")

        etat = EtatCampagne.lire(espace)
        self.assertEqual(etat.refus, list(resultat.refus), "le refus est persisté (§A7.4)")
        self.assertEqual(etat.restants(), [], "la reprise ne rejouerait pas le jeu refusé")

        rapport = espace.rapport.read_text(encoding="utf-8")
        self.assertIn("Jeux refusés par le backend", rapport)
        self.assertIn("fantome", rapport)
        types = [ligne["type"] for ligne in espace.lire_metriques()]
        self.assertIn("refus_jeu", types)
        self.assertTrue((espace.chemin / "scorecard.json").exists(), "résumé persisté (§A5.3)")


class TestEchecInference(_SocleCampagneSurRejeu):
    """§A7.4 : un échec d'inférence à retries épuisés clôt le JEU en échec nommé."""

    def test_un_500_permanent_ne_tue_pas_la_campagne(self) -> None:
        config = self._config("http://serveur-en-panne.invalide")
        espace = Workspace.ouvrir(config, "run-panne", racine=self.racine)

        def transport_en_panne(url: str, corps: bytes, entetes: Any, timeout: float) -> Any:
            return ReponseHTTP(500, b"erreur interne")

        resultat = executer_campagne(
            config,
            espace,
            self._plafonds(),
            jeux=[JEU],
            client_llm=LLMClient(config, transport=transport_en_panne, dormir=lambda _: None),
        )

        self.assertEqual(len(resultat.jeux), 0)
        self.assertEqual([entree["jeu"] for entree in resultat.refus], [JEU])
        self.assertIn("ServerError", resultat.refus[0]["motif"])
        self.assertTrue(espace.rapport.exists(), "le rapport n'est jamais perdu (§A7.4)")
        self.assertIn(
            "Jeux refusés par le backend",
            espace.rapport.read_text(encoding="utf-8"),
        )
        self.assertTrue((espace.chemin / "scorecard.json").exists(), "fermeture faite (§A5.3)")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
