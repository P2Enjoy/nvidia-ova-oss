"""Résolution générique du champ `action` du mode `state` : normalisations §H15.8.

@verifies docs/BACKLOG.md U27 — mode `state` de la boucle ; U31 — amélioration
          générique sur mesures (relevé live du banc, 2026-09-01)
@verifies docs/SPEC_HARNAIS.md §H15.8 (résolution générique : ordre des paramètres
          requis du schéma, coercition par type déclaré, normalisation de la
          ponctuation traînante, de la syntaxe d'appel de fonction, de la syntaxe
          d'argument nommé « cle=valeur », repli de découpage par espaces et
          paramètre requis unique reçu verbatim — jamais un nom ni un compte
          codés en dur)

La résolution est une fonction de parsing pure : elle s'éprouve directement, sans
appel LLM ni environnement réel. Les bruits de format couverts ici sont tous
MESURÉS en conditions réelles, jamais supposés.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

from avo.config import Mode, charger
from avo.llm.client import LLMClient
from avo.loop.boucle import BoucleAgent
from avo.memory.notes import Notes
from avo.tools.registre import Outil, RegistreOutils


class _EnvironnementInerte:
    def observation(self) -> str:
        return "observation"

    def actions_disponibles(self) -> list[str]:
        return ["poser", "avance"]

    def derniere_issue(self) -> None:
        return None

    def etat_terminal(self) -> str | None:
        return None


def _boucle(dossier: Path) -> BoucleAgent:
    config = charger(
        Mode.REJEU,
        env={"AVO_CONTEXT_MODE": "state", "AVO_GARDES": "false"},
        racine=Path("/inexistant"),
    )
    registre = RegistreOutils(
        [
            Outil(
                nom="poser",
                description="Pose un objet : deux paramètres requis.",
                parametres={
                    "type": "object",
                    "properties": {"objet": {"type": "string"}, "case": {"type": "integer"}},
                    "required": ["objet", "case"],
                },
                fonction=lambda objet, case: "ok",
                etiquettes=frozenset({"action"}),
            ),
            Outil(
                nom="avance",
                description="Avance : aucun paramètre.",
                parametres={"type": "object", "properties": {}},
                fonction=lambda: "ok",
                etiquettes=frozenset({"action"}),
            ),
            Outil(
                nom="dire",
                description="Texte libre : un seul paramètre requis.",
                parametres={
                    "type": "object",
                    "properties": {"texte": {"type": "string"}},
                    "required": ["texte"],
                },
                fonction=lambda texte: "ok",
                etiquettes=frozenset({"action"}),
            ),
        ]
    )
    return BoucleAgent(
        config,
        LLMClient(
            config,
            transport=lambda *a, **k: (_ for _ in ()).throw(AssertionError()),
            dormir=lambda _: None,
        ),
        registre,
        _EnvironnementInerte(),
        Notes(dossier / "notes"),
    )


class TestResolutionAction(unittest.TestCase):
    """§H15.8 : chaque normalisation, et les refus nommés quand rien ne colle."""

    def setUp(self) -> None:
        import tempfile

        self._dossier = tempfile.TemporaryDirectory()
        self.boucle = _boucle(Path(self._dossier.name))
        self.addCleanup(self._dossier.cleanup)

    def _resoudre(self, texte: str) -> Any:
        return self.boucle._resoudre_action(texte)  # noqa: SLF001 — l'unité testée

    def test_forme_canonique(self) -> None:
        appel = self._resoudre("poser cle_1, 4")
        self.assertTrue(appel.valide)
        self.assertEqual(appel.arguments, {"objet": "cle_1", "case": 4})

    def test_appel_de_fonction_sans_parametre(self) -> None:
        """Mesuré : cinq tours perdus sur « wait() » (relevé live du banc)."""
        appel = self._resoudre("avance()")
        self.assertTrue(appel.valide)
        self.assertEqual(appel.nom, "avance")

    def test_appel_de_fonction_avec_parametres(self) -> None:
        """Mesuré : « store(article_1, etagere_2) » refusé avant normalisation."""
        appel = self._resoudre("poser(cle_1, 4)")
        self.assertTrue(appel.valide)
        self.assertEqual(appel.arguments, {"objet": "cle_1", "case": 4})

    def test_valeurs_separees_par_espaces(self) -> None:
        """Mesuré : « 2 valeur(s) attendue(s), 1 reçue(s) » sur « store a b »."""
        appel = self._resoudre("poser cle_1 4")
        self.assertTrue(appel.valide)
        self.assertEqual(appel.arguments, {"objet": "cle_1", "case": 4})

    def test_les_virgules_priment_quand_elles_rendent_le_compte(self) -> None:
        """Le repli par espaces ne s'applique que si les virgules échouent :
        une valeur qui contient des espaces reste lisible."""
        appel = self._resoudre("poser grande cle, 4")
        self.assertTrue(appel.valide)
        self.assertEqual(appel.arguments, {"objet": "grande cle", "case": 4})

    def test_nom_inconnu_reste_un_refus_nomme(self) -> None:
        appel = self._resoudre("saute()")
        self.assertFalse(appel.valide)
        self.assertIn("outil_inconnu", appel.erreur_arguments or "")

    def test_compte_incorrect_reste_un_refus_nomme(self) -> None:
        appel = self._resoudre("poser cle_1")
        self.assertFalse(appel.valide)
        self.assertIn("2 valeur(s) attendue(s)", appel.erreur_arguments or "")

    def test_coercition_echouee_reste_un_refus_nomme(self) -> None:
        appel = self._resoudre("poser cle_1, quatre")
        self.assertFalse(appel.valide)
        self.assertIn("integer", appel.erreur_arguments or "")

    def test_argument_nomme_se_lit_comme_sa_valeur(self) -> None:
        """Mesuré : deux tours perdus sur « pr=2 »/« pr=4 » (banc dépôt h25
        bruit 5, 2026-09-02) — « cle=valeur » se lit « valeur » quand « cle »
        est exactement le paramètre requis que la position destine."""
        appel = self._resoudre("poser objet=cle_1, case=4")
        self.assertTrue(appel.valide)
        self.assertEqual(appel.arguments, {"objet": "cle_1", "case": 4})

    def test_argument_nomme_en_syntaxe_d_appel_de_fonction(self) -> None:
        appel = self._resoudre("poser(objet=cle_1, case=4)")
        self.assertTrue(appel.valide)
        self.assertEqual(appel.arguments, {"objet": "cle_1", "case": 4})

    def test_egalite_etrangere_reste_une_valeur(self) -> None:
        """Une clé qui n'est pas le paramètre attendu ne se retire pas : la
        valeur peut contenir un « = » légitime."""
        appel = self._resoudre("poser case=cle_1, 4")
        self.assertTrue(appel.valide)
        self.assertEqual(appel.arguments, {"objet": "case=cle_1", "case": 4})

    def test_parametre_unique_recoit_le_reste_verbatim(self) -> None:
        """§H15.8 : un seul paramètre requis — ni découpage par virgules, ni
        repli par espaces. Une ligne de commande contient légitimement les deux
        (règle désignée par la conception du banc b, §S12.1)."""
        appel = self._resoudre("dire grep -rn 'a, b' . | sort")
        self.assertTrue(appel.valide)
        self.assertEqual(appel.arguments, {"texte": "grep -rn 'a, b' . | sort"})

    def test_parametre_unique_en_syntaxe_d_appel_de_fonction(self) -> None:
        appel = self._resoudre("dire(bonjour, monde)")
        self.assertTrue(appel.valide)
        self.assertEqual(appel.arguments, {"texte": "bonjour, monde"})

    def test_parametre_unique_argument_nomme(self) -> None:
        """La normalisation « cle=valeur » s'applique avant le verbatim."""
        appel = self._resoudre("dire texte=bonjour, monde")
        self.assertTrue(appel.valide)
        self.assertEqual(appel.arguments, {"texte": "bonjour, monde"})

    def test_parametre_unique_absent_reste_un_refus_nomme(self) -> None:
        appel = self._resoudre("dire")
        self.assertFalse(appel.valide)
        self.assertIn("1 valeur(s) attendue(s)", appel.erreur_arguments or "")

    def test_refus_de_compte_se_clot_par_la_forme_attendue(self) -> None:
        """§H15.8 : mesuré (suite 46), 82 appels à coordonnées sans valeur sur la
        campagne U25 tranche 1 — le refus qui ne nomme que le compte laisse le
        modèle deviner la forme."""
        appel = self._resoudre("poser")
        self.assertFalse(appel.valide)
        erreur = appel.erreur_arguments or ""
        self.assertIn("2 valeur(s) attendue(s)", erreur)
        self.assertIn("Forme attendue : « poser objet, case »", erreur)
        self.assertIn("objet : string", erreur)
        self.assertIn("case : integer", erreur)

    def test_refus_de_valeurs_en_trop_se_clot_sans_valeur(self) -> None:
        """§H15.8 : mesuré (suite 46), 47 valeurs données à un outil qui n'en
        prend pas."""
        appel = self._resoudre("avance 3, 4")
        self.assertFalse(appel.valide)
        erreur = appel.erreur_arguments or ""
        self.assertIn("0 valeur(s) attendue(s)", erreur)
        self.assertIn("Forme attendue : « avance » seul, sans valeur.", erreur)

    def test_refus_de_type_se_clot_par_la_forme_attendue(self) -> None:
        appel = self._resoudre("poser cle_1, quatre")
        self.assertFalse(appel.valide)
        erreur = appel.erreur_arguments or ""
        self.assertIn("« case » : integer attendu", erreur)
        self.assertIn("Forme attendue : « poser objet, case »", erreur)

    def test_nom_inconnu_liste_les_formes_disponibles(self) -> None:
        """§H15.8 : mesuré (suite 46), 19 noms d'outils inventés — la liste des
        seuls noms n'enseignait pas les valeurs requises."""
        appel = self._resoudre("bouger 1, 2")
        self.assertFalse(appel.valide)
        erreur = appel.erreur_arguments or ""
        self.assertIn("outil_inconnu", erreur)
        self.assertIn("avance (aucune valeur)", erreur)
        self.assertIn("poser (valeurs requises : objet, case)", erreur)
        self.assertIn("dire (valeurs requises : texte)", erreur)

    def test_actions_disponibles_annoncees_avec_valeurs_requises(self) -> None:
        """§H15.8 : la ligne « Actions disponibles » du message composé annonce
        les paramètres requis de chaque action, lus au registre."""
        contenu = self.boucle._avec_observation("invite")  # noqa: SLF001 — l'unité testée
        self.assertIn(
            "Actions disponibles : poser (valeurs requises : objet, case), avance (aucune valeur)",
            contenu,
        )

    def test_action_sans_schema_reste_nue_dans_l_annonce(self) -> None:
        """Un nom que l'environnement déclare mais que le registre ne porte pas
        reste nu : rien n'est inventé."""
        self.boucle.environnement.actions_disponibles = lambda: ["poser", "mystere"]  # type: ignore[method-assign]
        contenu = self.boucle._avec_observation("invite")  # noqa: SLF001 — l'unité testée
        self.assertIn("poser (valeurs requises : objet, case), mystere", contenu)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
