"""Partie complète sur `cible` SOUS GARDES : artefacts exigés, rien de dépensé en trop.

@verifies docs/BACKLOG.md U30 — Spécification H16 et gardes de méthode
@verifies docs/SPEC_HARNAIS.md §H16.1 (WORKING écrit avant la première action),
          §H16.2 (prédiction dans chaque action, acheminée vers le fil),
          §H16.3 (verdict à chaque évaluation), §H16.4 (GUIDE écrit aux
          complétions), §H16.5 (chemin nominal : aucun événement de garde)
@verifies docs/SPEC_ARCAGI3.md §A8.2 (rejeu ARC local), §A3.2 (jeu `cible`)
@verifies docs/SPEC_HARNAIS.md §H16.0.4 (comparaison avant/après gardes sur `cible` :
          mêmes issues et mêmes appels sur politique conforme, artefacts en plus)

L'agent complet joue le jeu `cible` de bout en bout, gardes ACTIVES (défaut de la
configuration), avec une politique scriptée qui satisfait chaque garde du premier
coup : la partie reste parfaite (RHAE 100.00) et le workspace porte les artefacts
que les gardes exigent — la méthode ne coûte aucune action d'environnement.
"""

from __future__ import annotations

import copy
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from arc_replay.serveur import creer_serveur as creer_serveur_arc
from avo.arc.campagne import Plafonds, executer_campagne
from avo.config import Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP
from avo.memory.workspace import Workspace
from tests.e2e.scenarios import JEU, actions_victoire, gabarit_reponse

CASSETTE_REELLE = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")

#: Prédiction scriptée, constante : la garde exige l'artefact, pas son contenu.
PREDICTION = "je m'attends à un changement visible de la grille"


class TestPartieSousGardes(unittest.TestCase):
    def setUp(self) -> None:
        if not CASSETTE_REELLE.exists():
            self.skipTest("cassette absente : lancer « make record-llm »")
        self.serveur: ThreadingHTTPServer = creer_serveur_arc(port=0, niveaux=3)
        hote, port = self.serveur.server_address[0], self.serveur.server_address[1]
        self.base_arc = f"http://{hote!s}:{port}"
        self.fil = threading.Thread(target=self.serveur.serve_forever, daemon=True)
        self.fil.start()
        self.gabarit = gabarit_reponse()
        self.actions = tuple(actions_victoire())

    def tearDown(self) -> None:
        self.serveur.shutdown()
        self.serveur.server_close()
        self.fil.join(timeout=5)

    def _repondre(
        self, corps: dict[str, Any], rang_action: int, avec_prediction: bool = True
    ) -> tuple[dict[str, Any], bool]:
        """Politique conforme aux gardes, pilotée par l'invite reçue (§H16).

        `avec_prediction` suit le mode de l'interface : sans gardes, l'outil ne
        déclare pas le paramètre et un argument inconnu serait refusé (§H7.4).
        """
        reponse = copy.deepcopy(self.gabarit)
        dernier = str(corps["messages"][-1]["content"])
        appels: list[dict[str, Any]] = []
        if "[IMPLEMENTATION]" in dernier:
            nom, arguments = self.actions[min(rang_action, len(self.actions) - 1)]
            if avec_prediction:
                arguments = {**arguments, "prediction": PREDICTION}
            reponse["message"]["content"] = "je joue la commande annoncée"
            reponse["message"]["tool_calls"] = [{"function": {"name": nom, "arguments": arguments}}]
            return reponse, True
        if "WORKING.md" in dernier and "[GARDE]" in dernier:
            appels.append(
                {
                    "function": {
                        "name": "note_write",
                        "arguments": {
                            "name": "WORKING",
                            "content": "je sais peu / j'ignore les règles / j'agis pour découvrir",
                        },
                    }
                }
            )
        if "GUIDE.md" in dernier and "[GARDE]" in dernier:
            appels.append(
                {
                    "function": {
                        "name": "note_write",
                        "arguments": {"name": "GUIDE", "content": "ce que la partie m'apprend"},
                    }
                }
            )
        texte = "j'observe et je consigne"
        if "VERDICT" in dernier:
            texte = "l'observation est conforme.\nVERDICT: confirmee"
        reponse["message"]["content"] = texte
        if appels:
            reponse["message"]["tool_calls"] = appels
        else:
            reponse["message"].pop("tool_calls", None)
        return reponse, False

    def _jouer_campagne(self, gardes: str, run_id: str, dossier: Path) -> tuple[Any, Workspace]:
        # Mode épinglé : les réponses scriptées de ce banc encodent le chemin
        # `transcript` (le défaut du produit est prouvé par test_config.py).
        environnement = {
            "OLLAMA_HOST": "http://capture.invalide",
            "OLLAMA_API_KEY": "sk-cle-gardes-cible",
            "ARC_BASE_URL": self.base_arc,
            "ARC_API_KEY": "cle-de-test",
            "AVO_GARDES": gardes,
            "AVO_CONTEXT_MODE": "transcript",
        }
        config = charger(Mode.REJEU, env=environnement, racine=Path("/inexistant"))
        rang = 0

        def transport(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
            nonlocal rang
            reponse, avance = self._repondre(json.loads(corps), rang, avec_prediction=config.gardes)
            if avance:
                rang += 1
            return ReponseHTTP(200, json.dumps(reponse).encode())

        workspace = Workspace.ouvrir(config, run_id, racine=dossier)
        resultat = executer_campagne(
            config,
            workspace,
            Plafonds(actions_niveau=100, actions_jeu=200, tours_max=120),
            jeux=[JEU],
            client_llm=LLMClient(config, transport=transport, dormir=lambda _: None),
        )
        return resultat, workspace

    @staticmethod
    def _appels_llm(workspace: Workspace) -> int:
        metriques = (workspace.chemin / "metrics.jsonl").read_text(encoding="utf-8")
        return sum(
            1 for ligne in metriques.splitlines() if ligne and json.loads(ligne)["type"] == "llm"
        )

    def test_partie_parfaite_sous_gardes_artefacts_presents(self) -> None:
        with tempfile.TemporaryDirectory() as dossier:
            resultat, workspace = self._jouer_campagne("true", "gardes-cible", Path(dossier))

            jeu = resultat.jeux[0]
            self.assertEqual(jeu.niveaux_completes, 3)
            self.assertEqual(jeu.actions, 76, "la méthode ne coûte aucune action (§H16.0)")
            self.assertEqual(f"{jeu.rhae.valeur:.2f}", "100.00")

            # Les artefacts exigés par les gardes existent dans le workspace (§H16.5).
            working = (workspace.chemin / "notes" / "WORKING.md").read_text(encoding="utf-8")
            guide = (workspace.chemin / "notes" / "GUIDE.md").read_text(encoding="utf-8")
            self.assertIn("j'ignore", working, "l'artefact documentaire est écrit (§H16.1)")
            self.assertIn("apprend", guide, "la persistance est écrite (§H16.4)")

            # Chemin nominal : aucun événement de garde dans les métriques (§H16.5).
            metriques = (workspace.chemin / "metrics.jsonl").read_text(encoding="utf-8")
            evenements_garde = [
                json.loads(ligne)
                for ligne in metriques.splitlines()
                if ligne and json.loads(ligne).get("type") == "garde"
            ]
            self.assertEqual(evenements_garde, [], "artefacts présents du premier coup")

    def test_avant_apres_gardes_memes_issues_artefacts_en_plus(self) -> None:
        """A/B sur `cible` (§H16.0.4) : les gardes ne coûtent ni action ni appel
        sur politique conforme ; leur effet observable est l'artefact exigé."""
        with tempfile.TemporaryDirectory() as dossier:
            avec, ws_avec = self._jouer_campagne("true", "ab-avec", Path(dossier))
            sans, ws_sans = self._jouer_campagne("false", "ab-sans", Path(dossier))

            self.assertEqual(avec.jeux[0].niveaux_completes, sans.jeux[0].niveaux_completes)
            self.assertEqual(avec.jeux[0].actions, sans.jeux[0].actions)
            self.assertEqual(avec.score_global, sans.score_global)
            self.assertEqual(
                self._appels_llm(ws_avec),
                self._appels_llm(ws_sans),
                "sur politique conforme, la méthode ne coûte aucun appel (§H16.0)",
            )
            self.assertTrue((ws_avec.chemin / "notes" / "GUIDE.md").exists())
            guide_sans = ws_sans.chemin / "notes" / "GUIDE.md"
            self.assertFalse(
                guide_sans.exists() and guide_sans.read_text(encoding="utf-8").strip(),
                "sans gardes, rien n'exige l'écriture : l'artefact n'apparaît pas",
            )


if __name__ == "__main__":
    unittest.main()
