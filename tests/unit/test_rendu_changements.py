"""Changements depuis l'observation précédente, rendus au pas (§H15.8, §A4.5).

@verifies docs/BACKLOG.md U31 — les changements observés sont RENDUS, pas seulement
          demandés : méthode facultative `rendu_changements` de l'environnement, bloc
          « Changements depuis l'observation précédente » entre l'observation et les
          actions disponibles ; un environnement sans la méthode compose comme avant
@verifies docs/SPEC_HARNAIS.md §H15.8 (bloc composé par la boucle, lecture par
          `getattr`, identique sur les relances d'un pas refusé)
@verifies docs/SPEC_ARCAGI3.md §A4.5 (première observation nommée, absence de
          changement nommée, changement de niveau nommé, différence de cellules
          bornée), §A4.3 (rendu de différence PUR partagé avec l'outil `diff`),
          §A5.1 (aucune interprétation)

Aucun réseau : transports scriptés pour le client ARC et le client LLM.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from avo.arc.client import ArcClient
from avo.arc.interface import InterfaceArc
from avo.arc.memoire import DIFF_CELLULES_MAX, MemoireFrames, rendre_difference
from avo.arc.rendu import COTE
from avo.config import Config, Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP
from avo.loop.boucle import BoucleAgent
from avo.memory.notes import Notes
from avo.tools.registre import Outil, RegistreOutils

_GRILLE = [[0] * COTE for _ in range(COTE)]


def _grille(**cellules: int) -> list[list[int]]:
    """Grille nulle dont quelques cellules `r{ligne}c{colonne}` sont posées."""
    grille = [ligne[:] for ligne in _GRILLE]
    for cle, valeur in cellules.items():
        ligne, colonne = cle[1:].split("c")
        grille[int(ligne)][int(colonne)] = valeur
    return grille


# ------------------------------------------------------------- rendu pur (A4.3)


class TestRendreDifference(unittest.TestCase):
    def test_aucune_cellule(self) -> None:
        self.assertEqual(rendre_difference(_GRILLE, _GRILLE), "aucune cellule modifiée")

    def test_une_cellule_au_singulier(self) -> None:
        self.assertEqual(
            rendre_difference(_GRILLE, _grille(r3c7=5)), "1 cellule modifiée\n(3,7):0→5"
        )

    def test_plusieurs_cellules_dans_l_ordre_ligne_colonne(self) -> None:
        rendu = rendre_difference(_grille(r0c1=2), _grille(r5c5=9, r2c3=4))
        self.assertEqual(rendu, "3 cellules modifiées\n(0,1):2→0 (2,3):0→4 (5,5):0→9")

    def test_la_liste_est_bornee_et_le_compte_reste_exact(self) -> None:
        apres = [[1] * COTE for _ in range(COTE)]
        rendu = rendre_difference(_GRILLE, apres)
        premiere, details = rendu.split("\n", 1)
        self.assertEqual(premiere, f"{COTE * COTE} cellules modifiées")
        self.assertEqual(details.count("):"), DIFF_CELLULES_MAX)
        self.assertTrue(details.endswith(f" … et {COTE * COTE - DIFF_CELLULES_MAX} autres"))

    def test_l_outil_diff_partage_le_rendu(self) -> None:
        memoire = MemoireFrames()
        memoire.enregistrer_tour([("decision", _GRILLE)])
        memoire.enregistrer_tour([("decision", _grille(r1c1=3))])
        self.assertEqual(memoire.diff(1, 2), "tours 1 → 2 : 1 cellule modifiée\n(1,1):0→3")


# ------------------------------------------------------- interface ARC (A4.5)


class _TransportScripte:
    def __init__(self, *reponses: tuple[int, Any]) -> None:
        self.reponses = list(reponses)
        self.appels = 0

    def __call__(
        self,
        methode: str,
        url: str,
        corps: bytes | None,
        entetes: Mapping[str, str],
        timeout: float,
    ) -> tuple[int, bytes]:
        self.appels += 1
        statut, charge = self.reponses[min(self.appels - 1, len(self.reponses) - 1)]
        return statut, json.dumps(charge).encode()


def _reponse(
    grille: list[list[int]] | None = None, **surcharges: Any
) -> tuple[int, dict[str, Any]]:
    return 200, {
        "guid": "g1",
        "game_id": "jeu",
        "frame": [grille or _GRILLE],
        "state": "NOT_FINISHED",
        "levels_completed": 0,
        "win_levels": 3,
        "action_input": {"id": 0, "data": {}, "reasoning": None},
        "full_reset": False,
        "available_actions": [1, 2],
        **surcharges,
    }


def _interface(*reponses: tuple[int, Any]) -> InterfaceArc:
    config = charger(Mode.REJEU, env={}, racine=Path("/inexistant"))
    client = ArcClient(config, transport=_TransportScripte(*reponses), dormir=lambda _: None)
    return InterfaceArc(client)


class TestRenduChangementsArc(unittest.TestCase):
    def test_avant_demarrage_c_est_une_erreur(self) -> None:
        with self.assertRaises(RuntimeError):
            _interface(_reponse()).rendu_changements()

    def test_premiere_observation(self) -> None:
        interface = _interface(_reponse())
        interface.demarrer()
        self.assertEqual(interface.rendu_changements(), "première observation : rien à comparer")

    def test_cellules_modifiees_par_l_action(self) -> None:
        interface = _interface(_reponse(), _reponse(_grille(r4c2=7, r4c3=7)))
        interface.demarrer()
        interface.jouer("ACTION1")
        self.assertEqual(interface.rendu_changements(), "2 cellules modifiées\n(4,2):0→7 (4,3):0→7")

    def test_aucun_changement_est_nomme(self) -> None:
        interface = _interface(_reponse(), _reponse())
        interface.demarrer()
        interface.jouer("ACTION1")
        self.assertEqual(interface.rendu_changements(), "aucune cellule modifiée")

    def test_changement_de_niveau(self) -> None:
        interface = _interface(_reponse(), _reponse(_grille(r0c0=1), levels_completed=1))
        interface.demarrer()
        interface.jouer("ACTION2")
        self.assertEqual(
            interface.rendu_changements(),
            # Le fil compte les niveaux complétés ; le niveau courant est le suivant.
            "niveau 1 → 2 : nouvelle grille (1 cellule modifiée)",
        )

    def test_ne_compare_que_les_deux_derniers_resultats(self) -> None:
        interface = _interface(_reponse(), _reponse(_grille(r1c1=1)), _reponse(_grille(r1c1=1)))
        interface.demarrer()
        interface.jouer("ACTION1")
        interface.jouer("ACTION1")
        self.assertEqual(interface.rendu_changements(), "aucune cellule modifiée")


# ------------------------------------------------------------ boucle (H15.8)


def _config() -> Config:
    return charger(
        Mode.REJEU,
        env={
            "OLLAMA_HOST": "http://capture.invalide",
            "OLLAMA_API_KEY": "cle-de-test",
            "AVO_CONTEXT_MODE": "state",
            "AVO_GARDES": "false",
            "AVO_IDEATION_OUVERTURE": "false",
            "AVO_PLAN_LEDGER": "false",
        },
        racine=Path("/inexistant"),
    )


class _Environnement:
    def __init__(self) -> None:
        self._derniere: Any = None

    def observation(self) -> str:
        return "grille-fixe"

    def actions_disponibles(self) -> list[str]:
        return ["avance"]

    def derniere_issue(self) -> Any:
        return self._derniere

    def etat_terminal(self) -> str | None:
        return None

    def jouer(self, action: str, **parametres: Any) -> Any:
        return None


class _EnvironnementAvecChangements(_Environnement):
    def rendu_changements(self) -> str:
        return "3 cellules modifiées\n(0,0):1→2 (0,1):1→2 (0,2):1→2"


class _TransportLLM:
    def __init__(self, reponses: list[dict[str, Any]]) -> None:
        self.reponses = list(reponses)
        self.corps_emis: list[dict[str, Any]] = []

    def __call__(self, url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
        self.corps_emis.append(json.loads(corps))
        return ReponseHTTP(200, json.dumps(self.reponses.pop(0)).encode())

    def invite(self, rang: int) -> str:
        return str(self.corps_emis[rang]["messages"][-1]["content"])


def _reponse_llm(contenu: str) -> dict[str, Any]:
    return {
        "message": {"role": "assistant", "content": contenu},
        "done_reason": "stop",
        "prompt_eval_count": 10,
        "eval_count": 5,
        "total_duration": 1_000_000,
    }


def _pas() -> dict[str, Any]:
    bloc = json.dumps({"state_patch": {"hypotheses": ["h1"]}, "action": "avance"})
    return _reponse_llm(f"réflexion\n```json\n{bloc}\n```")


class TestBlocChangementsDansLaBoucle(unittest.TestCase):
    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.notes = Notes(Path(self._dossier.name) / "notes")

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def _boucle(self, environnement: Any, reponses: list[dict[str, Any]]) -> _TransportLLM:
        transport = _TransportLLM(reponses)
        client = LLMClient(_config(), transport=transport, dormir=lambda _: None)
        registre = RegistreOutils(
            [
                Outil(
                    nom="avance",
                    description="Joue une action d'environnement",
                    parametres={"type": "object", "properties": {}},
                    fonction=lambda: "action jouée",
                    etiquettes=frozenset({"action"}),
                )
            ]
        )
        BoucleAgent(_config(), client, registre, environnement, self.notes).jouer_tour(1)
        return transport

    def test_le_bloc_suit_l_observation_et_precede_les_actions(self) -> None:
        transport = self._boucle(_EnvironnementAvecChangements(), [_pas()])
        invite = transport.invite(0)
        observation = invite.index("Observation :\ngrille-fixe")
        changements = invite.index(
            "Changements depuis l'observation précédente :\n3 cellules modifiées\n(0,0):1→2"
        )
        actions = invite.index("Actions disponibles :")
        self.assertLess(observation, changements)
        self.assertLess(changements, actions)

    def test_sans_la_methode_le_bloc_est_absent(self) -> None:
        transport = self._boucle(_Environnement(), [_pas()])
        invite = transport.invite(0)
        self.assertNotIn("Changements depuis", invite)
        self.assertIn("Observation :\ngrille-fixe\n\nActions disponibles :", invite)

    def test_la_relance_d_un_pas_refuse_porte_le_meme_bloc(self) -> None:
        transport = self._boucle(
            _EnvironnementAvecChangements(), [_reponse_llm("pas de bloc json ici"), _pas()]
        )
        marque = "Changements depuis l'observation précédente :"
        premier, relance = transport.invite(0), transport.invite(1)
        self.assertEqual(premier.split(marque)[1], relance.split(marque)[1])


if __name__ == "__main__":
    unittest.main()
