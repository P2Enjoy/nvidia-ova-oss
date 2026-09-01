"""Preuves du client ARC : garde anti-publication, typage des frames, historique.

@verifies docs/BACKLOG.md U17 — Client API ARC ; U22 — format de fil mesuré
@verifies docs/SPEC_ARCAGI3.md §A2.1 (`FrameResult`), §A2.2 (historique typé),
          §A2.3 (garde anti-publication), §A1.2 (protocole), §A1.4 (fil mesuré),
          §A4.2 (conversion (row, col) → {x, y})
@verifies docs/SPEC_HARNAIS.md §H4.5 (retries partagés), §H4.6 (aucun secret)
"""

from __future__ import annotations

import json
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from avo.arc.client import (
    HOTES_REJEU,
    ArcAuthError,
    ArcClient,
    ArcProtocoleError,
    ArcServeurError,
    ArcTransportError,
    EtatArc,
    PublicationInterdite,
    TypeFrame,
    verifier_hote,
)
from avo.config import Config, Mode, charger
from avo.transport import ATTENTES_RETRY

_GRILLE = [[0, 0], [0, 0]]


def _config(env: dict[str, str] | None = None, mode: Mode = Mode.REJEU) -> Config:
    """Configuration de test. L'environnement est passé explicitement : un `**dict`
    pourrait remplir `mode` par accident, ce que le typage strict a signalé."""
    base = {"ARC_API_KEY": "00000000-0000-0000-0000-000000000000"}
    if mode is Mode.LIVE:
        base |= {
            "OLLAMA_HOST": "https://exemple.test",
            "OLLAMA_API_KEY": "sk-secret-de-test",
            "OLLAMA_CONTEXT_LENGTH": "229376",
        }
    return charger(mode, env={**base, **(env or {})}, racine=Path("/inexistant"))


class _TransportScripte:
    """Transport de test : rend ou lève ce qu'on lui a scripté, et compte les appels."""

    def __init__(self, *reponses: tuple[int, Any] | Exception) -> None:
        self.reponses = list(reponses)
        self.appels: list[tuple[str, str, Any, dict[str, str]]] = []

    def __call__(
        self,
        methode: str,
        url: str,
        corps: bytes | None,
        entetes: Mapping[str, str],
        timeout: float,
    ) -> tuple[int, bytes]:
        self.appels.append((methode, url, json.loads(corps) if corps else None, dict(entetes)))
        suivante = self.reponses[min(len(self.appels) - 1, len(self.reponses) - 1)]
        if isinstance(suivante, Exception):
            raise suivante
        statut, charge = suivante
        return statut, json.dumps(charge).encode()


def _reponse(**surcharges: Any) -> dict[str, Any]:
    """Réponse au format de fil MESURÉ par la sonde U22 (§A1.4)."""
    return {
        "guid": "g1",
        "game_id": "cible-synthetique",
        "frame": [_GRILLE],
        "state": "NOT_FINISHED",
        "levels_completed": 0,
        "win_levels": 3,
        "action_input": {"id": 0, "data": {}, "reasoning": None},
        "full_reset": False,
        "available_actions": [1, 6],
        **surcharges,
    }


def _client(
    *reponses: tuple[int, Any] | Exception, env: dict[str, str] | None = None
) -> tuple[ArcClient, Any]:
    transport = _TransportScripte(*reponses)
    client = ArcClient(_config(env), transport=transport, dormir=lambda _: None, alea=lambda: 0.5)
    return client, transport


class TestGardeAntiPublication(unittest.TestCase):
    """§A2.3 : la protection est structurelle, pas une consigne à respecter."""

    def test_un_hote_distant_est_refuse_en_mode_rejeu(self) -> None:
        with self.assertRaises(PublicationInterdite) as capture:
            ArcClient(_config({"ARC_BASE_URL": "https://three.arcprize.org"}))
        message = str(capture.exception)
        self.assertIn("three.arcprize.org", message)
        self.assertIn("publierait un scorecard", message)

    def test_les_hotes_locaux_sont_acceptes(self) -> None:
        for hote in sorted(HOTES_REJEU - {"::1"}):
            with self.subTest(hote=hote):
                verifier_hote(f"http://{hote}:8765", Mode.REJEU)

    def test_l_hote_ipv6_local_est_accepte(self) -> None:
        verifier_hote("http://[::1]:8765", Mode.REJEU)

    def test_le_mode_live_n_est_pas_bride(self) -> None:
        """En live, viser l'API officielle est précisément l'intention."""
        verifier_hote("https://three.arcprize.org", Mode.LIVE)

    def test_le_defaut_du_mode_rejeu_pointe_la_pile_locale(self) -> None:
        self.assertEqual(_config().arc_base_url, "http://127.0.0.1:8765")

    def test_le_defaut_du_mode_live_pointe_l_api_officielle(self) -> None:
        self.assertEqual(_config(mode=Mode.LIVE).arc_base_url, "https://three.arcprize.org")


class TestTypageDesFrames(unittest.TestCase):
    """§A2.2 : chaque frame reçoit le rôle qu'elle a réellement joué."""

    def test_le_reset_produit_une_frame_d_initialisation(self) -> None:
        client, _ = _client((200, _reponse()))
        resultat = client.reset(game_id="cible")
        self.assertIs(resultat.frames[-1].type, TypeFrame.INIT_RESET)
        self.assertIs(resultat.etat, EtatArc.EN_COURS)

    def test_les_frames_intermediaires_sont_transitoires(self) -> None:
        client, _ = _client((200, _reponse()), (200, _reponse(frame=[_GRILLE, _GRILLE])))
        client.reset()
        resultat = client.action(2, game_id="cible-synthetique", guid="g1")
        self.assertEqual(
            [frame.type for frame in resultat.frames],
            [TypeFrame.TRANSITOIRE, TypeFrame.DECISION],
        )

    def test_une_completion_de_niveau_donne_une_frame_d_init_de_niveau(self) -> None:
        client, _ = _client(
            (200, _reponse()), (200, _reponse(levels_completed=1, frame=[_GRILLE, _GRILLE]))
        )
        client.reset()
        resultat = client.action(6, game_id="cible-synthetique", guid="g1", coordonnees=(3, 4))
        self.assertIs(resultat.frames[-1].type, TypeFrame.INIT_NIVEAU)

    def test_une_victoire_donne_un_terminal_gagnant(self) -> None:
        client, _ = _client((200, _reponse()), (200, _reponse(state="WIN", levels_completed=3)))
        client.reset()
        resultat = client.action(6, game_id="cible-synthetique", guid="g1", coordonnees=(3, 4))
        self.assertIs(resultat.frames[-1].type, TypeFrame.TERMINAL_GAGNE)
        self.assertTrue(resultat.terminee)

    def test_une_perte_donne_un_terminal_perdant(self) -> None:
        client, _ = _client((200, _reponse()), (200, _reponse(state="GAME_OVER")))
        client.reset()
        resultat = client.action(6, game_id="cible-synthetique", guid="g1", coordonnees=(3, 4))
        self.assertIs(resultat.frames[-1].type, TypeFrame.TERMINAL_PERDU)

    def test_une_frame_terminale_n_est_pas_une_frame_de_decision(self) -> None:
        """On n'agit jamais depuis un terminal (§A2.2)."""
        client, _ = _client((200, _reponse()), (200, _reponse(state="WIN")))
        client.reset()
        resultat = client.action(6, game_id="cible-synthetique", guid="g1", coordonnees=(3, 4))
        self.assertIsNone(resultat.frame_de_decision)


class TestHistorique(unittest.TestCase):
    """§A2.2 : chaque action est rattachée à la frame d'où elle a été choisie."""

    def test_l_action_est_rattachee_a_la_frame_de_decision_precedente(self) -> None:
        client, _ = _client((200, _reponse()), (200, _reponse(frame=[_GRILLE, _GRILLE])))
        client.reset()
        client.action(2, game_id="cible-synthetique", guid="g1")
        entrees = client.historique.entrees
        self.assertIsNone(entrees[0].frame_de_decision, "le RESET ne suit aucune décision")
        self.assertEqual(entrees[1].frame_de_decision, 0)

    def test_les_coordonnees_du_clic_sont_conservees(self) -> None:
        client, _ = _client((200, _reponse()), (200, _reponse()))
        client.reset()
        client.action(6, game_id="cible-synthetique", guid="g1", coordonnees=(12, 34))
        self.assertEqual(client.historique.entrees[-1].coordonnees, (12, 34))

    def test_l_historique_s_ecrit_par_niveau(self) -> None:
        client, _ = _client(
            (200, _reponse()),
            (200, _reponse(levels_completed=1)),
            (200, _reponse(levels_completed=1)),
        )
        client.reset()
        client.action(6, game_id="cible-synthetique", guid="g1", coordonnees=(3, 4))
        client.action(1, game_id="cible-synthetique", guid="g1")
        with tempfile.TemporaryDirectory() as dossier:
            client.historique.ecrire(Path(dossier))
            fichiers = sorted(chemin.name for chemin in Path(dossier).glob("*.jsonl"))
            self.assertEqual(fichiers, ["niveau_01.jsonl", "niveau_02.jsonl"])
            lignes = (Path(dossier) / "niveau_02.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lignes), 2)
            self.assertEqual(json.loads(lignes[0])["commande"], "ACTION6")


class TestFilMesure(unittest.TestCase):
    """§A1.4/§A4.2 : le client émet et lit exactement le fil mesuré par la sonde."""

    def test_le_reset_porte_game_id_et_card_id(self) -> None:
        client, transport = _client((200, _reponse()))
        client.reset(game_id="cible-synthetique", card_id="carte-1")
        self.assertEqual(
            transport.appels[0][2], {"game_id": "cible-synthetique", "card_id": "carte-1"}
        )

    def test_une_action_porte_game_id_et_guid_sans_card_id(self) -> None:
        client, transport = _client((200, _reponse()), (200, _reponse()))
        client.reset()
        client.action(1, game_id="cible-synthetique", guid="g1")
        self.assertEqual(transport.appels[1][2], {"game_id": "cible-synthetique", "guid": "g1"})

    def test_action6_convertit_row_col_en_x_y(self) -> None:
        """(row, col) internes → x = col, y = row sur le fil ; jamais row/col (§A4.2)."""
        client, transport = _client((200, _reponse()), (200, _reponse()))
        client.reset()
        client.action(6, game_id="cible-synthetique", guid="g1", coordonnees=(12, 34))
        corps = transport.appels[1][2]
        self.assertEqual((corps["x"], corps["y"]), (34, 12))
        self.assertNotIn("row", corps)
        self.assertNotIn("col", corps)

    def test_les_actions_disponibles_sont_normalisees_en_noms(self) -> None:
        client, _ = _client((200, _reponse(available_actions=[0, 1, 6, 7])))
        resultat = client.reset()
        self.assertEqual(resultat.actions_disponibles, ("RESET", "ACTION1", "ACTION6", "ACTION7"))

    def test_le_niveau_se_derive_des_niveaux_completes(self) -> None:
        """Le fil ne porte pas de niveau courant : niveau = complétés + 1, borné (§A1.4)."""
        client, _ = _client(
            (200, _reponse()),
            (200, _reponse(levels_completed=1)),
            (200, _reponse(levels_completed=3, state="WIN")),
        )
        self.assertEqual(client.reset().niveau, 1)
        self.assertEqual(client.action(1, game_id="cible-synthetique", guid="g1").niveau, 2)
        gagne = client.action(1, game_id="cible-synthetique", guid="g1")
        self.assertEqual(gagne.niveau, 3, "borné par win_levels, jamais au-delà")
        self.assertEqual(gagne.score, 3)

    def test_le_drapeau_de_remise_a_zero_complete_est_lu(self) -> None:
        client, _ = _client((200, _reponse(full_reset=True)))
        self.assertTrue(client.reset().remise_a_zero_complete)


class TestErreursEtRetries(unittest.TestCase):
    """§H4.5 : mêmes règles que le client d'inférence, par partage du code."""

    def test_401_est_fatal_et_non_retente(self) -> None:
        client, transport = _client((401, {"error": "refus"}))
        with self.assertRaises(ArcAuthError):
            client.games()
        self.assertEqual(len(transport.appels), 1)

    def test_une_erreur_serveur_est_retentee_puis_leve(self) -> None:
        # Preuve révisée le 2026-09-01 (§H4.5 amendé) : cinq nouvelles tentatives
        # après l'échec initial, la politique patiente mesurée sur `pilote-u24c`.
        client, transport = _client((503, {"error": "panne"}))
        with self.assertRaises(ArcServeurError):
            client.games()
        self.assertEqual(len(transport.appels), len(ATTENTES_RETRY) + 1, "retries épuisés")

    def test_une_erreur_serveur_puis_succes(self) -> None:
        client, transport = _client((500, {}), (200, [{"game_id": "x"}]))
        self.assertEqual(client.games(), [{"game_id": "x"}])
        self.assertEqual(len(transport.appels), 2)

    def test_une_erreur_de_transport_est_retentee(self) -> None:
        client, transport = _client(ArcTransportError("réseau"), (200, []))
        client.games()
        self.assertEqual(len(transport.appels), 2)

    def test_un_400_n_est_pas_retente(self) -> None:
        client, transport = _client((400, {"error": "coordonnées manquantes"}))
        with self.assertRaises(ArcProtocoleError) as capture:
            client.games()
        self.assertIn("coordonnées", str(capture.exception))
        self.assertEqual(len(transport.appels), 1)


class TestAucunSecretJournalise(unittest.TestCase):
    def test_la_cle_part_en_en_tete_mais_le_resume_n_en_porte_rien(self) -> None:
        client, transport = _client((200, _reponse()))
        resultat = client.reset()
        self.assertEqual(
            transport.appels[0][3]["X-API-Key"], "00000000-0000-0000-0000-000000000000"
        )
        self.assertNotIn("00000000", str(resultat.resume()))

    def test_le_resume_ne_porte_aucune_grille(self) -> None:
        client, _ = _client((200, _reponse(frame=[_GRILLE, _GRILLE])))
        resume = client.reset().resume()
        self.assertEqual(resume["frames"], 2)
        self.assertNotIn("[[0, 0]", str(resume))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
