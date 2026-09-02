"""Résolution générique du champ `action` du mode `state` : normalisations §H15.8.

@verifies docs/BACKLOG.md U27 — mode `state` de la boucle ; U31 — amélioration
          générique sur mesures (relevé live du banc, 2026-09-01)
@verifies docs/SPEC_HARNAIS.md §H15.8 (résolution générique : ordre des paramètres
          requis du schéma, coercition par type déclaré, normalisation de la
          ponctuation traînante, de la syntaxe d'appel de fonction, de la syntaxe
          d'argument nommé « cle=valeur » et repli de découpage par espaces —
          jamais un nom ni un compte codés en dur)

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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
