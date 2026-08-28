"""L'agent joue réellement, par l'interface, sur le rejeu ARC en HTTP.

@verifies docs/BACKLOG.md U19 — Interface de tâche direct-interaction
@verifies docs/SPEC_ARCAGI3.md §A5.1 (aucune règle de jeu fournie), §A5.2 (outils
          filtrés par la frame), §A5.3 (comptage réconcilié), §A2.2 (historique typé
          et persisté), §A1.2 (protocole de score)
@verifies docs/SPEC_HARNAIS.md §H8.2 (contrat `Environnement`), §H7.1 (outils selon
          l'état), §H6.1 (les frames vivent dans le workspace du run)

Deux preuves complémentaires, toutes deux contre le VRAI serveur de rejeu :

1. l'interface conduite directement joue une partie entière — c'est là que les
   compteurs traversent des changements de niveau et une victoire ;
2. la boucle agent, dont les réponses de modèle sont scriptées mais servies par le
   vrai rejoueur HTTP, joue par l'interface — c'est là que se vérifie que le modèle
   ne voit que les commandes déclarées par la frame courante.
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

from arc_replay.jeu_cible import JeuCible, baseline_humaine
from arc_replay.serveur import creer_serveur as creer_serveur_arc
from avo.arc.client import ArcClient, EtatArc, TypeFrame
from avo.arc.interface import ETIQUETTE_ACTION, InterfaceArc
from avo.arc.memoire import SCHEMA_INSPECT, outil_inspect
from avo.config import Config, Mode, charger
from avo.lineage import ScorerARC
from avo.llm.client import LLMClient, ReponseHTTP
from avo.loop import prompts
from avo.loop.boucle import BoucleAgent
from avo.loop.etats import Evenement
from avo.memory.notes import Notes
from avo.memory.workspace import Workspace
from avo.tools.registre import RegistreOutils, outil_depuis_schema
from llm_replay.cassette import AUTH_VALIDE, Cassette, Exchange, RequestRecord, ResponseRecord
from llm_replay.server import creer_serveur as creer_serveur_llm

CASSETTE_REELLE = Path("tests/fixtures/llm/cassettes/contrat_endpoint.jsonl")
CLE = "sk-cle-de-rejeu-de-l-interface"

#: Coordonnées volontairement fausses : le clic manque la cible. Trois échecs
#: perdent la tentative (§A3.2), ce qui met en scène le rétrécissement des
#: commandes déclarées sans qu'aucune règle n'ait été donnée à l'agent.
CLIC_MANQUE = (32, 32)


def _gabarit_de_reponse() -> dict[str, Any]:
    """Corps de réponse RÉEL, qui sert de moule aux réponses scriptées."""
    for echange in Cassette.lire(CASSETTE_REELLE):
        corps = echange.response.body
        if echange.response.status == 200 and isinstance(corps, dict) and "message" in corps:
            return copy.deepcopy(corps)
    raise AssertionError("aucune réponse de conversation dans la cassette réelle")


class _PileArc:
    """Le vrai serveur de rejeu ARC, en HTTP, sur un port éphémère."""

    def demarrer_arc(self, **kwargs: Any) -> str:
        self.serveur_arc: ThreadingHTTPServer = creer_serveur_arc(port=0, **kwargs)
        hote, port = self.serveur_arc.server_address[0], self.serveur_arc.server_address[1]
        self.fil_arc = threading.Thread(target=self.serveur_arc.serve_forever, daemon=True)
        self.fil_arc.start()
        return f"http://{hote!s}:{port}"

    def arreter_arc(self) -> None:
        self.serveur_arc.shutdown()
        self.serveur_arc.server_close()
        self.fil_arc.join(timeout=5)


def _config_arc(base: str) -> Config:
    return charger(
        Mode.REJEU,
        env={"ARC_BASE_URL": base, "ARC_API_KEY": "cle-de-test"},
        racine=Path("/inexistant"),
    )


class TestPartieEntiereParLInterface(unittest.TestCase, _PileArc):
    """L'interface conduite directement : compteurs et historique sur une partie."""

    def setUp(self) -> None:
        self.base = self.demarrer_arc(niveaux=3)
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)

    def tearDown(self) -> None:
        self.arreter_arc()
        self._dossier.cleanup()

    def _interface(self, registre: RegistreOutils | None = None) -> InterfaceArc:
        return InterfaceArc(ArcClient(_config_arc(self.base)), registre=registre)

    def test_une_partie_parfaite_compte_exactement_les_baselines(self) -> None:
        """Le comptage local suit le serveur action par action, sans divergence."""
        interface = self._interface()
        interface.demarrer()
        temoin = JeuCible(niveaux=3)
        temoin.reset()

        for niveau in (1, 2, 3):
            for commande, ligne, colonne in temoin.chemin_optimal():
                coordonnees = (
                    (ligne, colonne) if ligne is not None and colonne is not None else None
                )
                interface.jouer(commande, coordonnees)
                temoin.jouer(commande, ligne, colonne)
            assert interface.dernier is not None
            self.assertEqual(interface.dernier.score, niveau)
            if niveau < 3:
                self.assertEqual(
                    interface.comptage.actions_niveau,
                    0,
                    "le compteur de niveau repart à zéro au changement de niveau",
                )

        attendu = sum(baseline_humaine(n) for n in (1, 2, 3))
        self.assertEqual(interface.comptage.actions_jeu, attendu)
        self.assertEqual(interface.comptage.divergences, [], "aucun écart avec le serveur")
        assert interface.dernier is not None
        self.assertIs(interface.dernier.etat, EtatArc.GAGNEE)

    def test_le_reset_initial_est_gratuit_et_les_suivants_comptent(self) -> None:
        """§A1.2, vérifié contre le serveur qui produit le score."""
        interface = self._interface()
        interface.demarrer()
        self.assertEqual(interface.comptage.actions_jeu, 0)
        interface.jouer("RESET")
        assert interface.dernier is not None
        self.assertEqual(interface.comptage.actions_jeu, 1)
        self.assertEqual(interface.dernier.actions_niveau, 1, "le serveur compte aussi")
        self.assertEqual(interface.comptage.divergences, [])

    def test_les_commandes_declarees_se_reduisent_apres_la_perte(self) -> None:
        """L'agent le découvre en agissant : rien ne le lui a dit (§A5.1)."""
        registre = RegistreOutils()
        interface = self._interface(registre)
        interface.demarrer()
        self.assertIn(
            "action6", [s["function"]["name"] for s in registre.schemas((ETIQUETTE_ACTION,))]
        )
        for _ in range(3):
            interface.jouer("ACTION6", CLIC_MANQUE)
        assert interface.dernier is not None
        self.assertIs(interface.dernier.etat, EtatArc.PERDUE)
        self.assertEqual(
            [s["function"]["name"] for s in registre.schemas((ETIQUETTE_ACTION,))], ["reset"]
        )

    def test_l_historique_typé_est_exact_et_persiste_par_niveau(self) -> None:
        """§A2.2 : chaque commande, ses frames typées, son niveau, dans le workspace."""
        interface = self._interface()
        interface.demarrer()
        interface.jouer("ACTION2")
        interface.jouer("ACTION6", CLIC_MANQUE)

        entrees = interface.client.historique.entrees
        self.assertEqual([entree.commande for entree in entrees], ["RESET", "ACTION2", "ACTION6"])
        self.assertEqual(entrees[0].types_recus, [TypeFrame.INIT_RESET.value])
        self.assertEqual(
            entrees[1].types_recus, [TypeFrame.TRANSITOIRE.value, TypeFrame.DECISION.value]
        )
        self.assertEqual(entrees[2].coordonnees, CLIC_MANQUE)
        self.assertTrue(all(entree.niveau == 1 for entree in entrees))
        # Chaque commande est rattachée à la frame de décision d'où elle a été jouée.
        self.assertEqual([entree.frame_de_decision for entree in entrees], [None, 0, 2])

        espace = Workspace.ouvrir(_config_arc(self.base), "run-interface", racine=self.racine)
        interface.client.historique.ecrire(espace.frames)
        lignes = (espace.frames / "niveau_01.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            [json.loads(ligne)["commande"] for ligne in lignes], [e.commande for e in entrees]
        )

    def test_la_memoire_conserve_toutes_les_frames_recues(self) -> None:
        """§A4.3 : y compris les transitoires, que l'observation ne rend pas."""
        interface = self._interface()
        interface.demarrer()
        interface.jouer("ACTION2")
        self.assertEqual(len(interface.memoire.frames), 3)
        self.assertEqual(len(interface.memoire.frames_de_decision()), 2)
        self.assertIn("frame(s) intermédiaire(s)", interface.observation())


class TestAgentSurInterface(unittest.TestCase, _PileArc):
    """La boucle agent joue par l'interface, contre les deux rejeux, en HTTP."""

    def setUp(self) -> None:
        if not CASSETTE_REELLE.exists():
            self.skipTest("cassette absente : lancer « make record-llm »")
        # Ce que le modèle scripté demande à chaque implémentation, dans l'ordre :
        # trois clics manqués, puis la relance. Un test le remplace par une partie
        # parfaite.
        self.actions: list[tuple[str, dict[str, int]]] = [
            ("action6", {"row": CLIC_MANQUE[0], "col": CLIC_MANQUE[1]}),
            ("action6", {"row": CLIC_MANQUE[0], "col": CLIC_MANQUE[1]}),
            ("action6", {"row": CLIC_MANQUE[0], "col": CLIC_MANQUE[1]}),
            ("reset", {}),
        ]
        self.base_arc = self.demarrer_arc(niveaux=3)
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        self.gabarit = _gabarit_de_reponse()
        self.serveur_llm: ThreadingHTTPServer | None = None

    def tearDown(self) -> None:
        if self.serveur_llm is not None:
            self.serveur_llm.shutdown()
            self.serveur_llm.server_close()
            self.fil_llm.join(timeout=5)
        self.arreter_arc()
        self._dossier.cleanup()

    # -- décor -----------------------------------------------------------------
    def _decor(self, suffixe: str) -> tuple[InterfaceArc, RegistreOutils, Notes]:
        """Une partie neuve, un registre neuf : les deux passes sont identiques."""
        interface = InterfaceArc(ArcClient(_config_arc(self.base_arc)))
        interface.registre = RegistreOutils(
            [
                outil_depuis_schema(
                    SCHEMA_INSPECT,
                    lambda **kwargs: outil_inspect(interface.memoire, **kwargs),
                    ["inspection"],
                )
            ]
        )
        interface.demarrer()
        registre = interface.registre
        return interface, registre, Notes(self.racine / f"notes_{suffixe}")

    def _repondre(self, corps: dict[str, Any], rang_action: int) -> dict[str, Any]:
        """Réponse scriptée : un appel d'action à l'implémentation, du texte sinon.

        Le pilotage se fait sur l'invite reçue, pas sur un index d'appel : la
        séquence reste juste même quand un tour ajoute une phase de bug-fixing.
        """
        reponse = copy.deepcopy(self.gabarit)
        dernier = corps["messages"][-1]["content"]
        if prompts.IMPLEMENTATION in dernier:
            nom, arguments = self.actions[min(rang_action, len(self.actions) - 1)]
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

    def _config_llm(self, base: str) -> Config:
        return charger(
            Mode.REJEU,
            env={"OLLAMA_HOST": base, "OLLAMA_API_KEY": CLE},
            racine=Path("/inexistant"),
        )

    def _executer(self, tours: int) -> tuple[Any, InterfaceArc, list[dict[str, Any]]]:
        """Deux passes : capture des corps émis, puis rejeu HTTP de la même séquence.

        Si les deux passes divergeaient d'un seul octet, l'appariement par empreinte
        échouerait et la seconde passe rougirait : c'est la garantie que la cassette
        porte exactement ce que la boucle produit.
        """
        corps_emis: list[dict[str, Any]] = []
        rang = 0

        def transport_capture(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
            nonlocal rang
            charge = json.loads(corps)
            corps_emis.append(charge)
            reponse = self._repondre(charge, rang)
            if reponse["message"].get("tool_calls"):
                rang += 1
            return ReponseHTTP(200, json.dumps(reponse).encode())

        interface_capture, registre_capture, notes_capture = self._decor("capture")
        config_capture = charger(
            Mode.REJEU,
            env={"OLLAMA_HOST": "http://capture.invalide", "OLLAMA_API_KEY": CLE},
            racine=Path("/inexistant"),
        )
        BoucleAgent(
            config_capture,
            LLMClient(config_capture, transport=transport_capture, dormir=lambda _: None),
            registre_capture,
            interface_capture,
            notes_capture,
        ).executer(tours_max=tours)

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
        chemin = self.racine / "scenario.jsonl"
        cassette.ecrire(chemin)

        base_llm = self._servir(chemin)
        interface, registre, notes = self._decor("rejeu")
        config = self._config_llm(base_llm)
        bilan = BoucleAgent(
            config, LLMClient(config, dormir=lambda _: None), registre, interface, notes
        ).executer(tours_max=tours)
        return bilan, interface, corps_emis

    # -- preuves ---------------------------------------------------------------
    def test_l_agent_joue_par_l_interface_et_les_compteurs_sont_exacts(self) -> None:
        bilan, interface, _ = self._executer(tours=4)

        self.assertEqual(len(bilan.tours), 4)
        self.assertEqual([tour.action for tour in bilan.tours], ["action6"] * 3 + ["reset"])
        self.assertEqual(bilan.actions_jeu, 4)
        self.assertEqual(bilan.game_overs, 1)
        self.assertEqual(
            [tour.evenement for tour in bilan.tours],
            [Evenement.PREDICTION_CONFIRMEE] * 2
            + [Evenement.GAME_OVER, Evenement.PREDICTION_CONFIRMEE],
        )
        # Le compteur de l'interface est celui que le serveur confirme (§A5.3).
        self.assertEqual(interface.comptage.actions_jeu, 4)
        self.assertEqual(interface.comptage.actions_niveau, 4)
        self.assertEqual(interface.comptage.divergences, [])
        assert interface.dernier is not None
        self.assertIs(interface.dernier.etat, EtatArc.EN_COURS, "le RESET a relancé la tentative")

    def test_l_historique_typé_du_run_de_l_agent_est_exact(self) -> None:
        _, interface, _ = self._executer(tours=4)
        entrees = interface.client.historique.entrees
        self.assertEqual(
            [entree.commande for entree in entrees],
            ["RESET", "ACTION6", "ACTION6", "ACTION6", "RESET"],
        )
        self.assertEqual(
            [entree.etat for entree in entrees],
            [EtatArc.EN_COURS.value] * 3 + [EtatArc.PERDUE.value, EtatArc.EN_COURS.value],
        )
        self.assertEqual(entrees[3].types_recus[-1], TypeFrame.TERMINAL_PERDU.value)
        self.assertTrue(all(entree.score == 0 for entree in entrees))

    def test_le_modele_ne_voit_que_les_commandes_declarees_par_la_frame(self) -> None:
        """§A5.2 : le rétrécissement des actions atteint bien la surface d'outils."""
        _, _, corps_emis = self._executer(tours=4)
        offerts = [
            sorted(outil["function"]["name"] for outil in corps["tools"])
            for corps in corps_emis
            if prompts.IMPLEMENTATION in corps["messages"][-1]["content"]
        ]
        self.assertEqual(len(offerts), 4)
        for tour, noms in enumerate(offerts[:3]):
            with self.subTest(tour=tour):
                self.assertEqual(
                    noms, ["action1", "action2", "action3", "action4", "action6", "reset"]
                )
        self.assertEqual(offerts[3], ["reset"], "après la perte, seule la relance est offerte")

    def test_un_niveau_complete_alimente_le_scorer_de_lignee(self) -> None:
        """§H9.2 : le branchement va jusqu'au scorer, sur une partie réellement jouée."""
        temoin = JeuCible(niveaux=3)
        temoin.reset()
        self.actions = []
        for commande, ligne, colonne in temoin.chemin_optimal():
            arguments = (
                {"row": ligne, "col": colonne} if ligne is not None and colonne is not None else {}
            )
            self.actions.append((commande.lower(), arguments))
        baseline = baseline_humaine(1)
        self.assertEqual(len(self.actions), baseline, "le chemin optimal vaut la baseline")

        bilan, interface, _ = self._executer(tours=baseline)

        self.assertEqual(bilan.niveaux_completes, 1)
        self.assertEqual(bilan.actions_jeu, baseline)
        self.assertEqual(bilan.actions_niveau, 0, "le compteur de niveau repart à zéro")
        self.assertEqual(bilan.tours[-1].evenement, Evenement.NIVEAU_COMPLETE)

        scorer = ScorerARC()
        self.assertTrue(scorer.est_valide(bilan))
        self.assertEqual(scorer.score(bilan), (1, -baseline))

        # Ce que le serveur a compté, et ce que l'interface a compté, coïncident.
        self.assertEqual(interface.comptage.actions_jeu, baseline)
        self.assertEqual(interface.comptage.divergences, [])
        assert interface.dernier is not None
        self.assertEqual(interface.dernier.niveau, 2)

    def test_aucune_regle_de_jeu_n_atteint_le_modele(self) -> None:
        """§A5.1, mesuré sur ce que la boucle a RÉELLEMENT émis."""
        _, _, corps_emis = self._executer(tours=4)
        emis = json.dumps(corps_emis, ensure_ascii=False).lower()
        for interdit in ("cible", "curseur", "bordure", "target", "cursor", "cliquer sur"):
            with self.subTest(interdit=interdit):
                self.assertNotIn(interdit, emis)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
