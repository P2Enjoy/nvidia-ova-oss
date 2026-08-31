"""Preuves de l'interface de tâche : filtrage, validation, comptage, zéro indice.

@verifies docs/BACKLOG.md U19 — Interface de tâche direct-interaction ; U22 — fil mesuré
@verifies docs/SPEC_ARCAGI3.md §A5.1 (aucune règle de jeu nulle part), §A5.2 (outils
          filtrés par la frame, reset toujours offert, coordonnées validées),
          §A5.3 (comptage local : le fil ne rend aucun compteur par frame),
          §A1.2 (RESET initial gratuit, suivants comptés)
"""

from __future__ import annotations

import importlib
import json
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from avo.arc.client import ArcClient
from avo.arc.interface import (
    DESCRIPTIONS,
    ETIQUETTE_ACTION,
    ActionIndisponible,
    CoordonneesInvalides,
    InterfaceArc,
)
from avo.arc.rendu import COTE
from avo.config import Mode, charger
from avo.loop.etats import Evenement
from avo.tools.registre import Outil, RegistreOutils

_GRILLE = [[0] * COTE for _ in range(COTE)]


class _TransportScripte:
    def __init__(self, *reponses: tuple[int, Any]) -> None:
        self.reponses = list(reponses)
        self.appels: list[tuple[str, str, Any]] = []

    def __call__(
        self,
        methode: str,
        url: str,
        corps: bytes | None,
        entetes: Mapping[str, str],
        timeout: float,
    ) -> tuple[int, bytes]:
        self.appels.append((methode, url, json.loads(corps) if corps else None))
        statut, charge = self.reponses[min(len(self.appels) - 1, len(self.reponses) - 1)]
        return statut, json.dumps(charge).encode()


def _reponse(**surcharges: Any) -> tuple[int, dict[str, Any]]:
    """Réponse au format de fil MESURÉ par la sonde U22 (§A1.4) : RESET n'y est
    jamais déclaré, les actions sont des entiers, aucun compteur par frame."""
    return 200, {
        "guid": "g1",
        "game_id": "jeu",
        "frame": [_GRILLE],
        "state": "NOT_FINISHED",
        "levels_completed": 0,
        "win_levels": 3,
        "action_input": {"id": 0, "data": {}, "reasoning": None},
        "full_reset": False,
        "available_actions": [1, 2, 6],
        **surcharges,
    }


def _interface(*reponses: tuple[int, Any]) -> tuple[InterfaceArc, _TransportScripte]:
    transport = _TransportScripte(*reponses)
    config = charger(Mode.REJEU, env={}, racine=Path("/inexistant"))
    interface = InterfaceArc(ArcClient(config, transport=transport, dormir=lambda _: None))
    return interface, transport


class TestOutilsFiltres(unittest.TestCase):
    """§A5.2 : le filtrage vient de la frame, pas d'une liste figée."""

    def test_seules_les_commandes_declarees_deviennent_des_outils(self) -> None:
        interface, _ = _interface(_reponse())
        interface.demarrer()
        noms = sorted(outil.nom for outil in interface.outils())
        self.assertEqual(noms, ["action1", "action2", "action6", "reset"])

    def test_une_commande_retiree_disparait_des_outils(self) -> None:
        interface, _ = _interface(_reponse(), _reponse(available_actions=[], state="GAME_OVER"))
        interface.demarrer()
        interface.jouer("ACTION1")
        self.assertEqual([outil.nom for outil in interface.outils()], ["reset"])

    def test_les_outils_d_action_portent_l_etiquette_action(self) -> None:
        """C'est elle qui les réserve à la phase où agir est permis (§H7.1)."""
        interface, _ = _interface(_reponse())
        interface.demarrer()
        for outil in interface.outils():
            with self.subTest(outil=outil.nom):
                self.assertIn(ETIQUETTE_ACTION, outil.etiquettes)

    def test_seul_action6_exige_des_coordonnees(self) -> None:
        interface, _ = _interface(_reponse())
        interface.demarrer()
        par_nom = {outil.nom: outil for outil in interface.outils()}
        self.assertEqual(par_nom["action6"].parametres["required"], ["row", "col"])
        self.assertEqual(par_nom["action1"].parametres["properties"], {})

    def test_jouer_une_commande_non_declaree_est_refuse(self) -> None:
        interface, _ = _interface(_reponse())
        interface.demarrer()
        with self.assertRaises(ActionIndisponible) as capture:
            interface.jouer("ACTION5")
        self.assertIn("ACTION5", str(capture.exception))
        self.assertIn("ACTION1", str(capture.exception))


class TestValidationDesCoordonnees(unittest.TestCase):
    """§A5.2 : (row, col) validés dans [0, 63]."""

    def setUp(self) -> None:
        self.interface, _ = _interface(_reponse())
        self.interface.demarrer()

    def test_des_coordonnees_valides_passent(self) -> None:
        self.interface.jouer("ACTION6", (0, 63))

    def test_une_coordonnee_hors_grille_est_refusee(self) -> None:
        for coordonnees in ((-1, 0), (0, COTE), (COTE, COTE)):
            with self.subTest(coordonnees=coordonnees), self.assertRaises(CoordonneesInvalides):
                self.interface.jouer("ACTION6", coordonnees)

    def test_action6_sans_coordonnees_est_refuse(self) -> None:
        with self.assertRaises(CoordonneesInvalides):
            self.interface.jouer("ACTION6")


class TestComptage(unittest.TestCase):
    """§A1.2 et §A5.3 : le RESET initial est gratuit, les suivants comptent."""

    def test_le_reset_initial_ne_compte_pas(self) -> None:
        interface, _ = _interface(_reponse())
        interface.demarrer()
        self.assertEqual(interface.comptage.actions_jeu, 0)

    def test_chaque_action_incremente_les_deux_compteurs(self) -> None:
        interface, _ = _interface(_reponse(), _reponse(), _reponse())
        interface.demarrer()
        interface.jouer("ACTION1")
        interface.jouer("ACTION2")
        self.assertEqual(interface.comptage.actions_jeu, 2)
        self.assertEqual(interface.comptage.actions_niveau, 2)

    def test_un_reset_en_cours_de_partie_compte(self) -> None:
        interface, _ = _interface(_reponse(), _reponse())
        interface.demarrer()
        interface.jouer("RESET")
        self.assertEqual(interface.comptage.actions_jeu, 1)

    def test_le_compteur_de_niveau_repart_a_zero(self) -> None:
        interface, _ = _interface(_reponse(), _reponse(), _reponse(levels_completed=1))
        interface.demarrer()
        interface.jouer("ACTION1")
        interface.jouer("ACTION1")
        self.assertEqual(interface.comptage.actions_niveau, 0)
        self.assertEqual(interface.comptage.actions_jeu, 2)

    def test_le_compteur_local_alimente_l_observation(self) -> None:
        """§A5.3 mesuré : le fil ne rend aucun compteur par frame — le compteur
        local fait l'affichage, la réconciliation officielle passant par le résumé
        de scorecard à la fermeture (preuve de campagne, U24)."""
        interface, _ = _interface(_reponse(), _reponse())
        interface.demarrer()
        observation = interface.jouer("ACTION1")
        self.assertIn("actions_niveau=1", observation.splitlines()[0])

    def test_reset_reste_jouable_sans_etre_declare(self) -> None:
        """§A5.2 : le fil ne déclare jamais RESET, le protocole le rend jouable."""
        interface, _ = _interface(_reponse(available_actions=[1]), _reponse())
        interface.demarrer()
        self.assertIn("reset", [outil.nom for outil in interface.outils()])
        interface.jouer("RESET")
        self.assertEqual(interface.comptage.actions_jeu, 1)


class TestEvenements(unittest.TestCase):
    """L'environnement dit ce qui s'est produit ; le modèle ne tranche pas (§H8.1)."""

    def test_une_progression_ordinaire(self) -> None:
        interface, _ = _interface(_reponse(), _reponse())
        interface.demarrer()
        interface.jouer("ACTION1")
        issue = interface.derniere_issue()
        assert issue is not None
        self.assertIs(issue.evenement, Evenement.PREDICTION_CONFIRMEE)

    def test_une_completion_de_niveau_est_signalee(self) -> None:
        interface, _ = _interface(_reponse(), _reponse(levels_completed=1))
        interface.demarrer()
        interface.jouer("ACTION1")
        issue = interface.derniere_issue()
        assert issue is not None
        self.assertIs(issue.evenement, Evenement.NIVEAU_COMPLETE)

    def test_une_partie_perdue_est_signalee(self) -> None:
        interface, _ = _interface(_reponse(), _reponse(state="GAME_OVER"))
        interface.demarrer()
        interface.jouer("ACTION1")
        issue = interface.derniere_issue()
        assert issue is not None
        self.assertIs(issue.evenement, Evenement.GAME_OVER)


class TestObservation(unittest.TestCase):
    def test_l_observation_porte_l_etat_puis_la_grille(self) -> None:
        interface, _ = _interface(_reponse())
        observation = interface.demarrer()
        lignes = observation.splitlines()
        self.assertTrue(lignes[0].startswith("niveau=1"))
        self.assertEqual(len(lignes), COTE + 1)

    def test_les_frames_transitoires_sont_annoncees_sans_etre_rendues(self) -> None:
        """Regarder les intermédiaires reste au choix de l'agent (§A4.3)."""
        interface, _ = _interface(_reponse(), _reponse(frame=[_GRILLE, _GRILLE]))
        interface.demarrer()
        observation = interface.jouer("ACTION1")
        self.assertIn("frame(s) intermédiaire(s)", observation)
        self.assertIn("inspect", observation)
        self.assertEqual(len(observation.splitlines()), COTE + 2)

    def test_jouer_avant_de_demarrer_est_refuse(self) -> None:
        interface, _ = _interface(_reponse())
        with self.assertRaises(RuntimeError):
            interface.jouer("ACTION1")


class TestZeroIndiceDeJeu(unittest.TestCase):
    """§A5.1 : la revue « zéro indice de jeu », rendue exécutable."""

    #: Termes qui trahiraient une connaissance des règles, des objets ou du but.
    INTERDITS = (
        "cible",
        "curseur",
        "bordure",
        "cliquer sur",
        "déplace",
        "deplace",
        "haut",
        "bas",
        "gauche",
        "droite",
        "gagner",
        "objectif",
        "target",
        "cursor",
    )

    def test_aucune_description_d_outil_ne_decrit_un_effet(self) -> None:
        for nom, description in DESCRIPTIONS.items():
            for interdit in self.INTERDITS:
                with self.subTest(outil=nom, interdit=interdit):
                    self.assertNotIn(interdit, description.lower())

    def test_les_descriptions_nomment_la_commande_et_son_cout(self) -> None:
        """Ce qu'elles disent est vrai du protocole, pas du jeu (§A1.2)."""
        for nom, description in DESCRIPTIONS.items():
            with self.subTest(outil=nom):
                self.assertIn(nom.upper().replace("ACTION", "ACTION"), description.upper())
                self.assertIn("coûte une action", description.lower())

    def test_le_rendu_de_l_observation_ne_porte_aucun_indice(self) -> None:
        interface, _ = _interface(_reponse())
        observation = interface.demarrer().lower()
        for interdit in ("cible", "curseur", "bordure", "target", "cursor"):
            with self.subTest(interdit=interdit):
                self.assertNotIn(interdit, observation)


class TestSynchronisationDuRegistre(unittest.TestCase):
    """§A5.2 : ce que le modèle voit suit la frame, pas une liste figée."""

    def test_le_registre_recoit_les_outils_de_la_frame_initiale(self) -> None:
        registre = RegistreOutils()
        interface, _ = _interface(_reponse())
        interface.registre = registre
        interface.demarrer()
        self.assertEqual(
            [schema["function"]["name"] for schema in registre.schemas((ETIQUETTE_ACTION,))],
            ["action1", "action2", "action6", "reset"],
        )

    def test_une_commande_retiree_disparait_de_ce_que_voit_le_modele(self) -> None:
        registre = RegistreOutils()
        interface, _ = _interface(_reponse(), _reponse(available_actions=[], state="GAME_OVER"))
        interface.registre = registre
        interface.demarrer()
        interface.jouer("ACTION1")
        self.assertEqual(
            [schema["function"]["name"] for schema in registre.schemas((ETIQUETTE_ACTION,))],
            ["reset"],
        )

    def test_les_outils_hors_action_du_registre_survivent(self) -> None:
        """L'inspection reste offerte : elle ne dépend pas de la frame (§A4.3)."""
        registre = RegistreOutils(
            [
                Outil(
                    nom="inspect",
                    description="Réaffiche une frame conservée.",
                    parametres={"type": "object", "properties": {}},
                    fonction=lambda: "vue",
                    etiquettes=frozenset({"inspection"}),
                )
            ]
        )
        interface, _ = _interface(_reponse(), _reponse())
        interface.registre = registre
        interface.demarrer()
        interface.jouer("ACTION1")
        self.assertIn("inspect", registre.noms)


class TestRevueZeroIndiceSurToutesLesSurfaces(unittest.TestCase):
    """§A5.1 : la revue « zéro indice de jeu », étendue à tout ce que le modèle lit.

    Les descriptions d'outils ne sont pas la seule porte d'entrée : les prompts de
    phase, l'invitation de continuation, les schémas d'inspection, les outils de
    notes et le message du superviseur atteignent eux aussi le modèle. Cette preuve
    les balaie tous, et échouera le jour où un indice sera glissé dans l'un d'eux.

    Le balayage porte sur les CONSTANTES des modules, pas sur leurs docstrings :
    celles-ci commentent le code pour nous et ne partent jamais dans une requête —
    l'une d'elles cite d'ailleurs, en contre-exemple, la formulation interdite.
    """

    #: Termes qui nommeraient un objet, un effet ou un but du jeu.
    INTERDITS = (
        "cible",
        "target",
        "curseur",
        "cursor",
        "bordure",
        "cliquer sur",
        "déplace",
        "deplace",
        "vers le haut",
        "vers le bas",
        "vers la gauche",
        "vers la droite",
        "coin ",
        "case verte",
        "aligner",
    )

    #: Tout module dont une constante peut se retrouver dans une requête.
    MODULES = (
        "avo.arc.interface",
        "avo.arc.memoire",
        "avo.arc.rendu",
        "avo.context.contexte",
        "avo.loop.prompts",
        "avo.memory.notes",
        "avo.supervisor",
    )

    @staticmethod
    def _chaines(valeur: object, profondeur: int = 0) -> list[str]:
        """Chaînes atteignables depuis une constante, conteneurs compris."""
        if isinstance(valeur, str):
            return [valeur]
        if profondeur >= 3:
            return []
        if isinstance(valeur, Mapping):
            valeur = [*valeur.keys(), *valeur.values()]
        if isinstance(valeur, list | tuple | set | frozenset):
            trouvees: list[str] = []
            for element in valeur:
                trouvees.extend(
                    TestRevueZeroIndiceSurToutesLesSurfaces._chaines(element, profondeur + 1)
                )
            return trouvees
        return []

    def test_aucune_constante_visible_par_le_modele_ne_porte_un_indice(self) -> None:
        for nom_module in self.MODULES:
            module = importlib.import_module(nom_module)
            for nom, valeur in vars(module).items():
                if nom.startswith("_"):
                    continue
                for texte in self._chaines(valeur):
                    for interdit in self.INTERDITS:
                        with self.subTest(module=nom_module, constante=nom, interdit=interdit):
                            self.assertNotIn(interdit, texte.lower())

    def test_le_balayage_couvre_bien_les_prompts_de_phase(self) -> None:
        """Garde-fou : une preuve qui ne lirait rien passerait sans rien prouver."""
        module = importlib.import_module("avo.loop.prompts")
        textes = [
            texte
            for nom, valeur in vars(module).items()
            if not nom.startswith("_")
            for texte in self._chaines(valeur)
        ]
        self.assertIn(module.IMPLEMENTATION, textes)
        self.assertIn(module.SYSTEME, textes)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
