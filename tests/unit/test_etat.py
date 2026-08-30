"""Preuves de l'état d'exécution structuré : fusion, validation, retries, sérialisation.

@verifies docs/BACKLOG.md U26 — Spécification H15 et runtime d'état structuré
@verifies docs/SPEC_HARNAIS.md §H15.1 (contrat de pas), §H15.2 (opérateur ⊕),
          §H15.3 (schéma possédé par le runtime), §H15.4 (rollback-retry borné),
          §H15.5 (sérialisation), §H15.6 (schéma ARC v1)

Les trois classes de la taxonomie d'erreurs du papier (§5.7) sont couvertes chacune
par un test dédié : écrasement/omission de clé (68 %), incohérence de type/structure
(20 %), JSON malformé (12 %).
"""

from __future__ import annotations

import unittest

from avo.context.etat import (
    RETRIES_MAX,
    CompteurRetries,
    Etat,
    EtatInvalide,
    PatchMalforme,
    RetriesEpuises,
    appliquer,
    decoder_pas,
)


class TestEtatInitial(unittest.TestCase):
    """§H15.6 : Σ₀ porte les quatre champs à leur défaut."""

    def test_etat_initial_porte_les_quatre_champs_par_defaut(self) -> None:
        etat = Etat.initial()
        self.assertEqual(
            etat.en_dict(),
            {"position": None, "essai": 1, "hypotheses": [], "objets": []},
        )


class TestFusionNominale(unittest.TestCase):
    """§H15.2 : une clé absente du patch survit — c'est le cœur de la propriété."""

    def test_une_cle_existante_absente_du_patch_survit(self) -> None:
        """Le mode d'erreur dominant du papier (68 %) : ne PAS écraser en silence."""
        etat = Etat.initial().fusionner({"hypotheses": ["la porte nord est bloquée"]})
        suite = etat.fusionner({"essai": 2})
        self.assertEqual(suite.en_dict()["hypotheses"], ["la porte nord est bloquée"])
        self.assertEqual(suite.en_dict()["essai"], 2)

    def test_fusionner_rend_un_nouvel_etat_sans_muter_celui_qui_existe(self) -> None:
        """Σₜ ⊕ ΔΣₜ ne mute jamais son entrée (propriété du module, comme Transcript)."""
        original = Etat.initial()
        avant = original.en_dict()
        _ = original.fusionner({"essai": 5})
        self.assertEqual(original.en_dict(), avant)

    def test_valeur_null_reinitialise_le_champ_a_son_defaut(self) -> None:
        """§H15.2 : null réinitialise, il ne retire jamais la clé du schéma."""
        etat = Etat.initial().fusionner({"essai": 7})
        reinitialise = etat.fusionner({"essai": None})
        self.assertEqual(reinitialise.en_dict()["essai"], 1)
        self.assertIn("essai", reinitialise.en_dict())

    def test_position_se_pose_puis_se_remplace(self) -> None:
        etat = Etat.initial().fusionner({"position": {"x": 3, "y": 4}})
        self.assertEqual(etat.en_dict()["position"], {"x": 3, "y": 4})
        deplace = etat.fusionner({"position": {"x": 3, "y": 5}})
        self.assertEqual(deplace.en_dict()["position"], {"x": 3, "y": 5})

    def test_objets_identifies_s_accumulent_par_patchs_successifs(self) -> None:
        etat = Etat.initial().fusionner(
            {"objets": [{"id": "clef-1", "description": "clef dorée au sol"}]}
        )
        suite = etat.fusionner(
            {
                "objets": [
                    {"id": "clef-1", "description": "clef dorée au sol"},
                    {"id": "porte-1", "description": "porte verrouillée nord"},
                ]
            }
        )
        self.assertEqual(len(suite.en_dict()["objets"]), 2)


class TestValidationSchemaComprehension(unittest.TestCase):
    """§5.7 (20%) : incohérences de type/structure — nommées, jamais absorbées."""

    def test_essai_non_entier_est_refuse_en_nommant_le_champ(self) -> None:
        with self.assertRaises(EtatInvalide) as capture:
            Etat.initial().fusionner({"essai": "deux"})
        self.assertIn("essai", str(capture.exception))

    def test_essai_booleen_est_refuse_malgre_bool_sous_classe_de_int(self) -> None:
        with self.assertRaises(EtatInvalide):
            Etat.initial().fusionner({"essai": True})

    def test_essai_zero_est_refuse(self) -> None:
        with self.assertRaises(EtatInvalide):
            Etat.initial().fusionner({"essai": 0})

    def test_hypotheses_comme_dict_au_lieu_de_liste_est_refuse(self) -> None:
        with self.assertRaises(EtatInvalide) as capture:
            Etat.initial().fusionner({"hypotheses": {"0": "une hypothèse"}})
        self.assertIn("hypotheses", str(capture.exception))

    def test_objets_sans_description_est_refuse_en_nommant_l_index(self) -> None:
        with self.assertRaises(EtatInvalide) as capture:
            Etat.initial().fusionner({"objets": [{"id": "clef-1"}]})
        self.assertIn("objets[0]", str(capture.exception))

    def test_position_avec_une_seule_coordonnee_est_refusee(self) -> None:
        with self.assertRaises(EtatInvalide):
            Etat.initial().fusionner({"position": {"x": 1}})

    def test_cle_hors_schema_est_refusee_en_la_nommant(self) -> None:
        with self.assertRaises(EtatInvalide) as capture:
            Etat.initial().fusionner({"inventaire": ["clef"]})
        self.assertIn("inventaire", str(capture.exception))

    def test_patch_refuse_n_atteint_jamais_l_etat(self) -> None:
        """§H15.3 : un patch invalide laisse l'état d'origine strictement inchangé."""
        etat = Etat.initial().fusionner({"essai": 3})
        with self.assertRaises(EtatInvalide):
            etat.fusionner({"essai": -1})
        self.assertEqual(etat.en_dict()["essai"], 3)


class TestSerialisationAllerRetour(unittest.TestCase):
    """§H15.5 : relire un état sérialisé rend un état égal à celui qui l'a produit."""

    def test_aller_retour_json_est_identique(self) -> None:
        etat = Etat.initial().fusionner(
            {
                "position": {"x": 2, "y": 9},
                "essai": 4,
                "hypotheses": ["le levier ouvre la trappe"],
                "objets": [{"id": "levier-1", "description": "levier rouge"}],
            }
        )
        reconstruit = Etat.depuis_json(etat.vers_json())
        self.assertEqual(reconstruit.en_dict(), etat.en_dict())
        self.assertEqual(reconstruit, etat)

    def test_json_illisible_est_refuse(self) -> None:
        with self.assertRaises(EtatInvalide):
            Etat.depuis_json("{ceci n'est pas du json")

    def test_json_qui_n_est_pas_un_objet_est_refuse(self) -> None:
        with self.assertRaises(EtatInvalide):
            Etat.depuis_json("[1, 2, 3]")


class TestDecoderPasJsonMalforme(unittest.TestCase):
    """§5.7 (12%) : JSON syntaxiquement invalide ou hors contrat — nommé, pas absorbé."""

    def test_reponse_sans_bloc_json_est_refusee(self) -> None:
        with self.assertRaises(PatchMalforme):
            decoder_pas("je pense qu'il faut avancer vers le nord.")

    def test_bloc_json_syntaxiquement_invalide_est_refuse(self) -> None:
        texte = 'raisonnement...\n```json\n{"state_patch": {}, "action": \n```'
        with self.assertRaises(PatchMalforme):
            decoder_pas(texte)

    def test_bloc_avec_clef_en_trop_est_refuse(self) -> None:
        texte = (
            "raisonnement...\n```json\n"
            '{"state_patch": {}, "action": "MOVE_UP", "commentaire": "extra"}\n```'
        )
        with self.assertRaises(PatchMalforme):
            decoder_pas(texte)

    def test_bloc_avec_clef_manquante_est_refuse(self) -> None:
        texte = 'raisonnement...\n```json\n{"state_patch": {}}\n```'
        with self.assertRaises(PatchMalforme):
            decoder_pas(texte)

    def test_action_vide_est_refusee(self) -> None:
        texte = 'raisonnement...\n```json\n{"state_patch": {}, "action": ""}\n```'
        with self.assertRaises(PatchMalforme):
            decoder_pas(texte)

    def test_state_patch_qui_n_est_pas_un_objet_est_refuse(self) -> None:
        texte = 'raisonnement...\n```json\n{"state_patch": [], "action": "MOVE_UP"}\n```'
        with self.assertRaises(PatchMalforme):
            decoder_pas(texte)

    def test_bloc_bien_forme_rend_le_patch_et_l_action_sans_le_raisonnement(self) -> None:
        texte = (
            "Je crois que la clef ouvre la porte nord, je vais la tester.\n"
            "```json\n"
            '{"state_patch": {"essai": 2}, "action": "MOVE_UP"}\n'
            "```"
        )
        pas = decoder_pas(texte)
        self.assertEqual(pas.patch, {"essai": 2})
        self.assertEqual(pas.action, "MOVE_UP")


class TestAppliquer(unittest.TestCase):
    """Décodage + fusion en un seul appel, sans gestion de nouvelle tentative."""

    def test_appliquer_decode_puis_fusionne(self) -> None:
        texte = 'raison...\n```json\n{"state_patch": {"essai": 3}, "action": "RESET"}\n```'
        nouvel_etat, action = appliquer(Etat.initial(), texte)
        self.assertEqual(nouvel_etat.en_dict()["essai"], 3)
        self.assertEqual(action, "RESET")

    def test_appliquer_propage_patch_malforme_sans_toucher_a_l_etat(self) -> None:
        etat = Etat.initial()
        with self.assertRaises(PatchMalforme):
            appliquer(etat, "réponse sans bloc JSON")
        texte = '```json\n{"state_patch": {}, "action": "X"}\n```'
        self.assertEqual(appliquer(etat, texte)[0], etat)


class TestCompteurRetries(unittest.TestCase):
    """§H15.4 : budget borné, jamais une boucle infinie."""

    def test_plafond_par_defaut_est_la_constante_du_module(self) -> None:
        self.assertEqual(CompteurRetries().plafond, RETRIES_MAX)

    def test_compteur_neuf_n_est_pas_epuise(self) -> None:
        self.assertFalse(CompteurRetries().epuise)

    def test_echec_consomme_une_tentative_sans_muter_le_compteur_d_origine(self) -> None:
        compteur = CompteurRetries()
        suite = compteur.echec()
        self.assertEqual(compteur.consommees, 0)
        self.assertEqual(suite.consommees, 1)

    def test_budget_epuise_apres_le_nombre_de_tentatives_configure(self) -> None:
        compteur = CompteurRetries(plafond=2)
        compteur = compteur.echec()
        self.assertFalse(compteur.epuise)
        compteur = compteur.echec()
        self.assertTrue(compteur.epuise)

    def test_echec_sur_compteur_deja_epuise_leve_retries_epuises(self) -> None:
        compteur = CompteurRetries(plafond=1).echec()
        self.assertTrue(compteur.epuise)
        with self.assertRaises(RetriesEpuises):
            compteur.echec()


if __name__ == "__main__":
    unittest.main()
