"""Ledger du patron GVS5H : genre `liste_taches`, champ `plan`, dérivation, curation.

@verifies docs/BACKLOG.md U37 — Intégration du patron ledger dans la boucle et
          l'état existants
@verifies docs/SPEC_HARNAIS.md §H18.1 (genre `liste_taches` : validation nommée,
          fusion par `id`, statuts, borne `PLAN_TACHES_MAX`, purge des terminales,
          refus au-delà de la borne ouverte ; dérivation `avec_plan`, collision
          refusée ; protocole engendré énonçant la discipline de curation),
          §H18.3 (remplacement curé `remplacer_taches` : validation, restriction
          au champ, purge rendue à l'appelant), §H15.2 (`null` uniforme),
          §H15.9 (le genre est un genre du noyau)

Module pur : aucune entrée-sortie, aucun réseau — les preuves de la boucle et du
superviseur sont dans `tests/unit/test_ideation_curation.py`.
"""

from __future__ import annotations

import unittest

from avo.context.etat import (
    ARC_V1,
    PatchMalforme,
    decoder_pas,
    CHAMP_PLAN,
    LISTE_CHAINES,
    LISTE_TACHES,
    PLAN_TACHES_MAX,
    ChampEtat,
    Etat,
    EtatInvalide,
    SchemaEtat,
    SchemaInvalide,
    avec_plan,
    remplacer_taches,
    taches_purgees,
)
from avo.loop import prompts

#: Schéma de banc minimal, dérivé pour porter le ledger.
_SCHEMA = avec_plan(SchemaEtat("test-v1", (ChampEtat("hypotheses", LISTE_CHAINES, "acquis"),)))


def _tache(ident: str, statut: str = "a_faire", **extra: object) -> dict[str, object]:
    return {"id": ident, "description": f"tâche {ident}", "statut": statut, **extra}


class TestGenreListeTaches(unittest.TestCase):
    """§H18.1 : validation nommée du genre, jamais un rejet générique."""

    def setUp(self) -> None:
        self.etat = Etat.initial(_SCHEMA)

    def test_une_liste_valide_est_acceptee_et_les_cles_libres_conservees(self) -> None:
        etat = self.etat.fusionner({CHAMP_PLAN: [_tache("t1", resultat="acquis GVS5H")]})
        (tache,) = etat.champs[CHAMP_PLAN]
        self.assertEqual(tache["id"], "t1")
        self.assertEqual(tache["resultat"], "acquis GVS5H")

    def test_autre_chose_qu_une_liste_est_refusee_en_nommant_le_champ(self) -> None:
        with self.assertRaises(EtatInvalide) as capture:
            self.etat.fusionner({CHAMP_PLAN: {"id": "t1"}})
        self.assertIn(CHAMP_PLAN, str(capture.exception))

    def test_une_tache_sans_statut_est_refusee_en_nommant_l_entree(self) -> None:
        with self.assertRaises(EtatInvalide) as capture:
            self.etat.fusionner({CHAMP_PLAN: [{"id": "t1", "description": "d"}]})
        self.assertIn("[0]", str(capture.exception))

    def test_un_statut_inconnu_est_refuse_en_citant_les_admis(self) -> None:
        with self.assertRaises(EtatInvalide) as capture:
            self.etat.fusionner({CHAMP_PLAN: [_tache("t1", statut="abandonnee")]})
        self.assertIn("a_faire", str(capture.exception))

    def test_un_id_vide_est_refuse(self) -> None:
        with self.assertRaises(EtatInvalide):
            self.etat.fusionner({CHAMP_PLAN: [_tache("")]})

    def test_deux_taches_de_meme_id_dans_une_valeur_sont_refusees(self) -> None:
        with self.assertRaises(EtatInvalide) as capture:
            self.etat.fusionner({CHAMP_PLAN: [_tache("t1"), _tache("t1")]})
        self.assertIn("t1", str(capture.exception))


class TestFusionParId(unittest.TestCase):
    """§H18.1 : jamais la réémission entière — remplacer, ajouter, laisser."""

    def setUp(self) -> None:
        self.etat = Etat.initial(_SCHEMA).fusionner(
            {CHAMP_PLAN: [_tache("t1"), _tache("t2", statut="en_cours")]}
        )

    def test_une_tache_de_meme_id_est_remplacee_sur_place(self) -> None:
        etat = self.etat.fusionner({CHAMP_PLAN: [_tache("t1", statut="fait")]})
        taches = list(etat.champs[CHAMP_PLAN])
        self.assertEqual([t["id"] for t in taches], ["t1", "t2"], "l'ordre est conservé")
        self.assertEqual(taches[0]["statut"], "fait")

    def test_clore_une_tache_existante_s_ecrit_id_statut_seuls(self) -> None:
        """§H18.1 révisé (mesure u38-depot-s2) : la fusion est champ à champ —
        la clé absente est conservée, jamais réémise."""
        etat = self.etat.fusionner({CHAMP_PLAN: [{"id": "t1", "statut": "ecartee"}]})
        (t1, t2) = etat.champs[CHAMP_PLAN]
        self.assertEqual(t1["statut"], "ecartee")
        self.assertEqual(t1["description"], "tâche t1", "la description est conservée")
        self.assertEqual(t2["statut"], "en_cours", "les autres tâches sont intactes")

    def test_une_tache_nouvelle_incomplete_est_refusee_en_la_nommant(self) -> None:
        with self.assertRaises(EtatInvalide) as capture:
            self.etat.fusionner({CHAMP_PLAN: [{"id": "t9", "statut": "a_faire"}]})
        self.assertIn("t9", str(capture.exception))
        self.assertIn("description", str(capture.exception))

    def test_un_statut_invalide_sur_une_tache_existante_reste_refuse(self) -> None:
        with self.assertRaises(EtatInvalide):
            self.etat.fusionner({CHAMP_PLAN: [{"id": "t1", "statut": "bidon"}]})

    def test_un_id_numerique_est_normalise_en_chaine(self) -> None:
        """§H18.1 (mesure u38-ctf-s6) : bruit de format, jamais une mort de run."""
        etat = self.etat.fusionner(
            {CHAMP_PLAN: [{"id": 3, "description": "tâche 3", "statut": "a_faire"}]}
        )
        ids = [t["id"] for t in etat.champs[CHAMP_PLAN]]
        self.assertIn("3", ids)
        # Et la fusion champ à champ retrouve la tâche sous sa chaîne.
        clos = etat.fusionner({CHAMP_PLAN: [{"id": 3, "statut": "fait"}]})
        (t3,) = [t for t in clos.champs[CHAMP_PLAN] if t["id"] == "3"]
        self.assertEqual(t3["statut"], "fait")

    def test_un_id_booleen_reste_refuse(self) -> None:
        with self.assertRaises(EtatInvalide):
            self.etat.fusionner(
                {CHAMP_PLAN: [{"id": True, "description": "d", "statut": "a_faire"}]}
            )

    def test_une_tache_nouvelle_s_ajoute_et_les_absentes_restent(self) -> None:
        etat = self.etat.fusionner({CHAMP_PLAN: [_tache("t3")]})
        self.assertEqual([t["id"] for t in etat.champs[CHAMP_PLAN]], ["t1", "t2", "t3"])

    def test_null_reinitialise_le_champ_entier_au_defaut(self) -> None:
        """§H15.2 : la sémantique de `null` reste uniforme — seul `hypotheses` a
        une conservation propre, mesurée (§H16.1)."""
        etat = self.etat.fusionner({CHAMP_PLAN: None})
        self.assertEqual(etat.champs[CHAMP_PLAN], ())

    def test_l_aller_retour_serialise_est_identique(self) -> None:
        """§H15.5 : Σ avec ledger se relit sous le schéma dérivé."""
        relu = Etat.depuis_json(self.etat.vers_json(), _SCHEMA)
        self.assertEqual(relu.en_dict(), self.etat.en_dict())


class TestBorneEtPurge(unittest.TestCase):
    """§H18.1 : la borne purge les terminales, refuse les ouvertes en excès."""

    def test_au_dela_de_la_borne_les_terminales_les_plus_anciennes_sont_purgees(
        self,
    ) -> None:
        pleines = [_tache("f1", "fait"), _tache("f2", "ecartee")] + [
            _tache(f"o{i}") for i in range(PLAN_TACHES_MAX - 2)
        ]
        etat = Etat.initial(_SCHEMA).fusionner({CHAMP_PLAN: pleines})
        patch = {CHAMP_PLAN: [_tache("o-nouvelle")]}
        apres = etat.fusionner(patch)
        ids = [t["id"] for t in apres.champs[CHAMP_PLAN]]
        self.assertEqual(len(ids), PLAN_TACHES_MAX)
        self.assertNotIn("f1", ids, "la terminale la plus ancienne est purgée")
        self.assertIn("f2", ids, "une seule purge suffit à la borne")
        self.assertIn("o-nouvelle", ids)
        self.assertEqual(taches_purgees(etat, patch, apres), ("f1",))

    def test_des_ouvertes_seules_au_dela_de_la_borne_refusent_le_patch(self) -> None:
        ouvertes = [_tache(f"o{i}") for i in range(PLAN_TACHES_MAX)]
        etat = Etat.initial(_SCHEMA).fusionner({CHAMP_PLAN: ouvertes})
        with self.assertRaises(EtatInvalide) as capture:
            etat.fusionner({CHAMP_PLAN: [_tache("o-de-trop")]})
        self.assertIn(str(PLAN_TACHES_MAX), str(capture.exception))
        self.assertEqual(len(etat.champs[CHAMP_PLAN]), PLAN_TACHES_MAX, "Σ inchangé")

    def test_sans_purge_taches_purgees_est_vide(self) -> None:
        etat = Etat.initial(_SCHEMA)
        patch = {CHAMP_PLAN: [_tache("t1")]}
        self.assertEqual(taches_purgees(etat, patch, etat.fusionner(patch)), ())

    def test_null_n_est_pas_une_purge(self) -> None:
        etat = Etat.initial(_SCHEMA).fusionner({CHAMP_PLAN: [_tache("t1")]})
        patch: dict[str, object] = {CHAMP_PLAN: None}
        self.assertEqual(taches_purgees(etat, patch, etat.fusionner(patch)), ())


class TestDerivationAvecPlan(unittest.TestCase):
    """§H18.1 : le ledger se DÉRIVE — aucun schéma déclaré ne le porte."""

    def test_le_schema_derive_ajoute_plan_et_se_nomme_plus_plan(self) -> None:
        self.assertEqual(_SCHEMA.nom, "test-v1+plan")
        champ = _SCHEMA.champ(CHAMP_PLAN)
        assert champ is not None
        self.assertEqual(champ.genre, LISTE_TACHES)
        self.assertTrue(champ.role, "le protocole cite un rôle")

    def test_arc_v1_se_derive_aussi(self) -> None:
        derive = avec_plan(ARC_V1)
        self.assertEqual(derive.nom, "arc-v1+plan")
        self.assertEqual(derive.noms[:-1], ARC_V1.noms, "les champs déclarés d'abord")

    def test_un_schema_qui_declare_deja_plan_est_refuse(self) -> None:
        with self.assertRaises(SchemaInvalide) as capture:
            avec_plan(_SCHEMA)
        self.assertIn(CHAMP_PLAN, str(capture.exception))

    def test_le_schema_declare_reste_intact_sans_derivation(self) -> None:
        """Interrupteur inactif = schéma déclaré tel quel (§H18.1) : ARC v1 n'a
        pas gagné de champ."""
        self.assertNotIn(CHAMP_PLAN, ARC_V1.noms)


class TestRemplacementCure(unittest.TestCase):
    """§H18.3 : le geste de manager — remplacement entier, validé, restreint."""

    def setUp(self) -> None:
        self.etat = Etat.initial(_SCHEMA).fusionner(
            {
                "hypotheses": ["h1"],
                CHAMP_PLAN: [_tache("t1"), _tache("t1bis"), _tache("t2", "fait")],
            }
        )

    def test_le_remplacement_permet_de_fusionner_les_doublons(self) -> None:
        cure, purgees = remplacer_taches(self.etat, [_tache("t1"), _tache("t2", "fait")])
        self.assertEqual([t["id"] for t in cure.champs[CHAMP_PLAN]], ["t1", "t2"])
        self.assertEqual(purgees, ())
        self.assertEqual(cure.champs["hypotheses"], ("h1",), "aucun autre champ touché")

    def test_une_liste_invalide_est_refusee_sans_toucher_l_etat(self) -> None:
        with self.assertRaises(EtatInvalide):
            remplacer_taches(self.etat, [_tache("t1", statut="bidon")])
        self.assertEqual(len(self.etat.champs[CHAMP_PLAN]), 3)

    def test_la_borne_s_applique_au_remplacement_et_la_purge_est_rendue(self) -> None:
        liste = [_tache("vieille", "fait")] + [_tache(f"o{i}") for i in range(PLAN_TACHES_MAX)]
        cure, purgees = remplacer_taches(self.etat, liste)
        self.assertEqual(purgees, ("vieille",))
        self.assertEqual(len(cure.champs[CHAMP_PLAN]), PLAN_TACHES_MAX)

    def test_un_schema_sans_ledger_refuse_le_remplacement(self) -> None:
        with self.assertRaises(EtatInvalide) as capture:
            remplacer_taches(Etat.initial(ARC_V1), [_tache("t1")])
        self.assertIn("ledger", str(capture.exception))


class TestProtocoleEngendre(unittest.TestCase):
    """§H18.1 : la discipline de curation s'annonce d'emblée (§H16.0.7)."""

    def test_avec_ledger_le_protocole_enonce_fusion_statuts_et_borne(self) -> None:
        texte = prompts.protocole_etat(_SCHEMA)
        self.assertIn("fusionne par « id »", texte)
        self.assertIn("ecartee", texte)
        self.assertIn(str(PLAN_TACHES_MAX), texte)

    def test_sans_ledger_le_protocole_est_octet_pour_octet_celui_d_avant(self) -> None:
        """Interrupteur inactif = protocole inchangé : la constante `PROTOCOLE_ETAT`
        (schéma ARC v1) ne mentionne aucune tâche."""
        self.assertEqual(prompts.protocole_etat(ARC_V1), prompts.PROTOCOLE_ETAT)
        self.assertNotIn("liste de tâches", prompts.PROTOCOLE_ETAT)


class TestInvitesIdeation(unittest.TestCase):
    """§H18.2 : les invites annoncent ce que la structure imposera (§H16.0.7)."""

    def test_l_invite_du_mode_state_annonce_l_action_non_jouee(self) -> None:
        texte = prompts.ideation_etat(ledger=True)
        self.assertIn("Aucune action ne sera jouée", texte)
        self.assertIn("hypotheses", texte)
        self.assertIn(CHAMP_PLAN, texte)

    def test_sans_ledger_l_invite_ne_cite_pas_le_plan(self) -> None:
        self.assertNotIn(CHAMP_PLAN, prompts.ideation_etat(ledger=False))

    def test_l_invite_du_mode_transcript_vise_working(self) -> None:
        self.assertIn("WORKING.md", prompts.IDEATION_TRANSCRIPT)
        self.assertIn(prompts.IDEATION, prompts.IDEATION_TRANSCRIPT)

    def test_l_invite_du_mode_state_dit_la_forme_de_l_action(self) -> None:
        """§H16.0.7 (mesure u38-ctf-s6) : l'invite dit quoi mettre dans « action »."""
        self.assertIn("aucune", prompts.ideation_etat(ledger=True))


class TestActionOptionnelleIdeation(unittest.TestCase):
    """§H18.2 : le pas d'idéation — et lui seul — tolère une action vide."""

    def test_le_contrat_strict_refuse_toujours_l_action_vide(self) -> None:
        bloc = '```json\n{"state_patch": {}, "action": ""}\n```'
        with self.assertRaises(PatchMalforme):
            decoder_pas(bloc)

    def test_le_pas_d_ideation_accepte_l_action_vide(self) -> None:
        bloc = '```json\n{"state_patch": {}, "action": ""}\n```'
        pas = decoder_pas(bloc, action_optionnelle=True)
        self.assertEqual(pas.action, "")

    def test_une_action_non_chaine_reste_refusee_meme_optionnelle(self) -> None:
        bloc = '```json\n{"state_patch": {}, "action": null}\n```'
        with self.assertRaises(PatchMalforme):
            decoder_pas(bloc, action_optionnelle=True)


if __name__ == "__main__":
    unittest.main()
