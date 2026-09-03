"""Preuves du schéma de Σ déclaré par le domaine : genres, champ commun, fusion clé
par clé, protocole engendré, surface du contexte, schémas des deux domaines du banc.

@verifies docs/BACKLOG.md U31 — schéma de Σ déclaré par le domaine (amélioration
          générique désignée par la mesure du 2026-09-02)
@verifies docs/SPEC_HARNAIS.md §H15.9 (genres du noyau, `hypotheses` obligatoire,
          dictionnaire fusionné clé par clé avec retrait sur null, `arc-v1` défaut
          inchangé, protocole engendré, Σ relu sous son schéma), §H15.2 (null au
          niveau du champ = défaut), §H15.3 (refus nommé), §H15.5 (aller-retour)
@verifies docs/SPEC_BANCS.md §S6.5 (schémas Entrepôt et Dépôt, relevé nommant le
          schéma)
"""

from __future__ import annotations

import unittest

from avo.bancs.skillexec.adaptateur import SCHEMA_DEPOT, SCHEMA_ENTREPOT
from avo.config import Mode, charger
from avo.context.contexte import Contexte
from avo.context.etat import (
    ARC_V1,
    CHAINE,
    CHAMP_HYPOTHESES,
    DICTIONNAIRE,
    ENTIER_POSITIF,
    LISTE_CHAINES,
    ChampEtat,
    Etat,
    EtatInvalide,
    SchemaEtat,
    SchemaInvalide,
)
from avo.loop import prompts

SCHEMA = SchemaEtat(
    "essai-v1",
    (
        ChampEtat(CHAMP_HYPOTHESES, LISTE_CHAINES, "ce que je tiens pour vrai"),
        ChampEtat("registre", DICTIONNAIRE, "clé → valeur suivie"),
        ChampEtat("compteur", ENTIER_POSITIF),
    ),
)


class TestDeclaration(unittest.TestCase):
    """§H15.9 : le noyau valide la déclaration, et exige le champ commun."""

    def test_hypotheses_obligatoire(self) -> None:
        with self.assertRaises(SchemaInvalide) as arret:
            SchemaEtat("sans", (ChampEtat("registre", DICTIONNAIRE),))
        self.assertIn(CHAMP_HYPOTHESES, str(arret.exception))

    def test_genre_inconnu_refuse_et_nomme(self) -> None:
        with self.assertRaises(SchemaInvalide) as arret:
            SchemaEtat("x", (ChampEtat(CHAMP_HYPOTHESES, LISTE_CHAINES), ChampEtat("a", "pile")))
        self.assertIn("« a »", str(arret.exception))
        self.assertIn("pile", str(arret.exception))

    def test_champ_en_double_refuse(self) -> None:
        with self.assertRaises(SchemaInvalide):
            SchemaEtat(
                "x",
                (
                    ChampEtat(CHAMP_HYPOTHESES, LISTE_CHAINES),
                    ChampEtat(CHAMP_HYPOTHESES, LISTE_CHAINES),
                ),
            )

    def test_arc_v1_reste_le_defaut(self) -> None:
        """§H15.6 : sans déclaration, tout est comme avant."""
        self.assertEqual(Etat.initial().schema, ARC_V1)
        self.assertEqual(
            Etat.initial().en_dict(),
            {"position": None, "essai": 1, "hypotheses": [], "objets": []},
        )
        self.assertEqual(Contexte(config=charger(Mode.REJEU), systeme="P").schema_etat, ARC_V1)


class TestFusionDictionnaire(unittest.TestCase):
    """§H15.9 : fusion clé par clé, retrait sur null, défaut sur null de champ."""

    def test_initial_du_schema(self) -> None:
        self.assertEqual(
            Etat.initial(SCHEMA).en_dict(), {"hypotheses": [], "registre": {}, "compteur": 1}
        )

    def test_fusion_cle_par_cle(self) -> None:
        etat = Etat.initial(SCHEMA).fusionner({"registre": {"a": "x", "b": [1, 2]}})
        etat = etat.fusionner({"registre": {"c": {"d": 1}}})
        self.assertEqual(etat.en_dict()["registre"], {"a": "x", "b": [1, 2], "c": {"d": 1}})
        etat = etat.fusionner({"registre": {"a": None, "b": "y"}})
        self.assertEqual(etat.en_dict()["registre"], {"b": "y", "c": {"d": 1}})
        etat = etat.fusionner({"registre": None})
        self.assertEqual(etat.en_dict()["registre"], {})

    def test_immutabilite(self) -> None:
        avant = Etat.initial(SCHEMA).fusionner({"registre": {"a": 1}})
        avant.fusionner({"registre": {"a": None}})
        self.assertEqual(avant.en_dict()["registre"], {"a": 1})

    def test_refus_nommes(self) -> None:
        etat = Etat.initial(SCHEMA)
        with self.assertRaises(EtatInvalide) as arret:
            etat.fusionner({"registre": ["pas", "un", "objet"]})
        self.assertIn("registre", str(arret.exception))
        with self.assertRaises(EtatInvalide) as arret:
            etat.fusionner({"inconnu": 1})
        self.assertIn("essai-v1", str(arret.exception))
        with self.assertRaises(EtatInvalide):
            etat.fusionner({"compteur": 0})

    def test_aller_retour_sous_le_schema(self) -> None:
        etat = Etat.initial(SCHEMA).fusionner(
            {"registre": {"a": {"b": [1, "c"]}}, "hypotheses": ["h"], "compteur": 4}
        )
        relu = Etat.depuis_json(etat.vers_json(), SCHEMA)
        self.assertEqual(relu, etat)
        with self.assertRaises(EtatInvalide):
            Etat.depuis_json(etat.vers_json())  # sous arc-v1, « registre » est inconnu


class TestGenreChaine(unittest.TestCase):
    """§H15.9 : genre `chaine` — scalaire textuel, défaut vide, null = défaut.

    Ajouté pour le schéma `ctf` (§S12.3, `repertoire_travail`), transposé du
    `working_dir` de la source (§3.1).
    """

    SCHEMA = SchemaEtat(
        "chaine-v1",
        (
            ChampEtat(CHAMP_HYPOTHESES, LISTE_CHAINES),
            ChampEtat("repertoire", CHAINE, "où je me trouve"),
        ),
    )

    def test_defaut_vide_et_remplacement(self) -> None:
        etat = Etat.initial(self.SCHEMA)
        self.assertEqual(etat.en_dict()["repertoire"], "")
        etat = etat.fusionner({"repertoire": "sous/dossier"})
        self.assertEqual(etat.en_dict()["repertoire"], "sous/dossier")

    def test_null_revient_au_defaut(self) -> None:
        etat = Etat.initial(self.SCHEMA).fusionner({"repertoire": "ailleurs"})
        etat = etat.fusionner({"repertoire": None})
        self.assertEqual(etat.en_dict()["repertoire"], "")

    def test_refus_nomme_hors_chaine(self) -> None:
        with self.assertRaises(EtatInvalide) as arret:
            Etat.initial(self.SCHEMA).fusionner({"repertoire": 7})
        self.assertIn("repertoire", str(arret.exception))
        self.assertIn("chaîne", str(arret.exception))

    def test_aller_retour(self) -> None:
        etat = Etat.initial(self.SCHEMA).fusionner({"repertoire": "x/y", "hypotheses": ["h"]})
        self.assertEqual(Etat.depuis_json(etat.vers_json(), self.SCHEMA), etat)


class TestProtocoleEngendre(unittest.TestCase):
    """§H15.9 : l'invite de protocole vient du schéma, la constante ARC en est le rendu."""

    def test_constante_arc_egale_au_rendu(self) -> None:
        self.assertEqual(prompts.PROTOCOLE_ETAT, prompts.protocole_etat(ARC_V1))
        self.assertIn("4 champs", prompts.PROTOCOLE_ETAT)
        self.assertNotIn("clé par clé", prompts.PROTOCOLE_ETAT)

    def test_schema_du_domaine_cite_champs_roles_et_fusion(self) -> None:
        texte = prompts.protocole_etat(SCHEMA)
        self.assertIn("3 champs", texte)
        for champ in SCHEMA.champs:
            self.assertIn(f"« {champ.nom} »", texte)
        self.assertIn("ce que je tiens pour vrai", texte)
        self.assertIn("clé par clé", texte)
        self.assertTrue(texte.startswith(prompts.PROTOCOLE_ETAT_FORMAT))

    def test_le_protocole_enonce_que_hypotheses_ne_se_vide_pas(self) -> None:
        """§H16.1 : le prompt dit comment se conformer à l'invariant que la structure impose."""
        for texte in (prompts.PROTOCOLE_ETAT, prompts.protocole_etat(SCHEMA)):
            self.assertIn("ne se vide jamais", texte)

    def test_le_protocole_annonce_l_exigence_documentaire(self) -> None:
        """§H16.0.7 : l'exigence « connaissances non vides avant d'agir » s'annonce
        d'emblée — mesuré, sa seule annonce en message de refus coûtait le premier
        pas de chaque run (3/3, journal 2026-09-02 suite 29)."""
        for texte in (prompts.PROTOCOLE_ETAT, prompts.protocole_etat(SCHEMA)):
            self.assertIn("aucune action n'est jouée", texte)
            self.assertIn("au moins une hypothèse", texte)

    def test_l_exigence_documentaire_clot_le_protocole_apres_la_parcimonie(self) -> None:
        """§H16.0.7 : l'exigence documentaire est la phrase FINALE, exception nommée
        à la parcimonie — annoncée avant elle, elle perdait quand la première
        observation ne laissait aucune incertitude (2/2 premiers pas refusés,
        journal 2026-09-03 suite 33)."""
        for texte in (prompts.PROTOCOLE_ETAT, prompts.protocole_etat(SCHEMA)):
            self.assertLess(
                texte.index("ce qui change réellement"),
                texte.index("au moins une hypothèse"),
            )
            self.assertTrue(texte.rstrip().endswith("hypothèse dans son patch."))

    def test_le_protocole_enonce_l_enseignement_d_un_refus(self) -> None:
        """§H16.0.7 : un refus nomme le point sur lequel Σ est faux — le protocole
        commande de corriger Σ d'après ce message (mesuré : 17 invalides répétant
        des refus jamais répercutés dans Σ, journal 2026-09-02 suite 29)."""
        for texte in (prompts.PROTOCOLE_ETAT, prompts.protocole_etat(SCHEMA)):
            self.assertIn("Un refus te renseigne", texte)
            self.assertIn("corrige Σ d'après ce message", texte)


class TestSchemasDuBanc(unittest.TestCase):
    """§S6.5 : les deux domaines déclarent un schéma valide, avec le champ commun."""

    def test_schemas_valides_et_distincts(self) -> None:
        for schema in (SCHEMA_ENTREPOT, SCHEMA_DEPOT):
            self.assertIsNotNone(schema.champ(CHAMP_HYPOTHESES))
            self.assertTrue(any(c.genre == DICTIONNAIRE for c in schema.champs))
            self.assertTrue(all(c.role for c in schema.champs))
        self.assertNotEqual(SCHEMA_ENTREPOT.noms, SCHEMA_DEPOT.noms)


if __name__ == "__main__":
    unittest.main()
