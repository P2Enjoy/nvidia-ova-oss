"""Preuves de l'environnement Dépôt logiciel du banc a : générateur, transitions,
score, résolution, bruit.

@verifies docs/BACKLOG.md U29a3 — environnement Dépôt logiciel du banc a
@verifies docs/SPEC_BANCS.md §S1.4 (déterminisme à seed égal), §S4.1 (l'état ne
          change pas sur action invalide), §S4.2 (validité et refus nommés,
          `merge` sur CI rouge valide et cassant), §S4.3 (cycle nominal, défaut
          tiré, bruit C.3 sans effet sur les événements), §S4.4 (score continu
          inchangé, résolution B.1, relevé), §S4.5 (obligations sur l'état réel,
          `wait` dû en divergence), §S4.6 (une action consomme l'événement,
          motif de fin), §S5.1 (score continu), §S5.2 (première action seule)
"""

from __future__ import annotations

import unittest

from avo.bancs.skillexec.depot import (
    AFFECTATION,
    CI_VERTE,
    ECHEC_CI,
    REVUE,
    ROUGE,
    VERTE,
    EnvironnementDepot,
    EpisodeDepot,
    EvenementDepot,
    generer_episode_depot,
    nom_branche,
    nom_demande,
    nom_fichier,
)
from avo.bancs.skillexec.entrepot import MOTIF_EPUISE
from avo.bancs.skillexec.generation import ENTETE_TELEMETRIE


def _affectation(demande: int) -> EvenementDepot:
    return EvenementDepot(
        AFFECTATION,
        demande,
        None,
        f"Issue affectée : {nom_demande(demande)} — "
        f"écrire {nom_fichier(demande)} sur {nom_branche(demande)}.",
    )


def _revue(demande: int) -> EvenementDepot:
    return EvenementDepot(
        REVUE,
        demande,
        None,
        f"Revue approuvée pour {nom_branche(demande)} : la PR peut être ouverte.",
    )


def _echec_ci(demande: int, pr: int) -> EvenementDepot:
    return EvenementDepot(
        ECHEC_CI,
        demande,
        pr,
        f"CI en échec pour PR #{pr} ({nom_branche(demande)}) : erreur de lint.",
    )


def _ci_verte(demande: int, pr: int) -> EvenementDepot:
    return EvenementDepot(
        CI_VERTE,
        demande,
        pr,
        f"CI verte pour PR #{pr} ({nom_branche(demande)}) : prête à fusionner.",
    )


def _episode_manuel(
    *evenements: EvenementDepot, defauts: tuple[bool, ...] = (), bruit: int = 0
) -> EpisodeDepot:
    """Épisode construit à la main pour éprouver une transition précise."""
    nb_demandes = 1 + max((e.demande for e in evenements), default=-1)
    if len(defauts) < nb_demandes:
        defauts = defauts + (False,) * (nb_demandes - len(defauts))
    return EpisodeDepot(
        seed=0,
        horizon=len(evenements),
        bruit=bruit,
        evenements=tuple(evenements),
        telemetrie=tuple(() for _ in evenements),
        defauts=defauts,
    )


class TestGenerateur(unittest.TestCase):
    def test_deterministe_a_seed_egal(self) -> None:
        a = generer_episode_depot(seed=42, horizon=60, bruit=5)
        b = generer_episode_depot(seed=42, horizon=60, bruit=5)
        self.assertEqual(a, b)

    def test_seeds_differents_episodes_differents(self) -> None:
        a = generer_episode_depot(seed=42, horizon=60)
        b = generer_episode_depot(seed=43, horizon=60)
        self.assertNotEqual(a.evenements, b.evenements)

    def test_cycle_nominal_respecte(self) -> None:
        """Chaque demande suit affectation → revue → [echec_ci si défaut] →
        ci_verte, les PR nominales croissent depuis 1 (§S4.3)."""
        episode = generer_episode_depot(seed=7, horizon=120)
        etapes: dict[int, list[str]] = {}
        prs: dict[int, int] = {}
        pr_attendue = 1
        for evenement in episode.evenements:
            etapes.setdefault(evenement.demande, []).append(evenement.type)
            if evenement.type == REVUE:
                prs[evenement.demande] = pr_attendue
                pr_attendue += 1
            if evenement.pr is not None:
                self.assertEqual(evenement.pr, prs[evenement.demande])
        for demande, suite in etapes.items():
            attendu = [AFFECTATION, REVUE]
            if episode.defauts[demande]:
                attendu.append(ECHEC_CI)
            attendu.append(CI_VERTE)
            self.assertEqual(suite, attendu[: len(suite)], f"demande {demande}")

    def test_echec_ci_seulement_sur_defaut(self) -> None:
        episode = generer_episode_depot(seed=11, horizon=200)
        en_echec = {e.demande for e in episode.evenements if e.type == ECHEC_CI}
        self.assertTrue(en_echec, "le seed doit produire au moins un défaut jugé")
        for demande in en_echec:
            self.assertTrue(episode.defauts[demande])

    def test_bruit_ne_change_pas_les_evenements(self) -> None:
        """Le niveau de bruit ne change jamais la suite d'événements (§S4.3)."""
        sans = generer_episode_depot(seed=5, horizon=40, bruit=0)
        avec = generer_episode_depot(seed=5, horizon=40, bruit=20)
        self.assertEqual(sans.evenements, avec.evenements)
        self.assertEqual(sans.defauts, avec.defauts)
        self.assertTrue(all(len(lignes) == 20 for lignes in avec.telemetrie))
        self.assertTrue(all(ligne.startswith("[Syslog]") for ligne in avec.telemetrie[0]))

    def test_parametres_negatifs_refuses(self) -> None:
        with self.assertRaises(ValueError):
            generer_episode_depot(seed=1, horizon=-1)
        with self.assertRaises(ValueError):
            generer_episode_depot(seed=1, horizon=1, bruit=-1)


class TestTransitions(unittest.TestCase):
    def test_commit_cree_la_branche_et_materialise_le_defaut(self) -> None:
        environnement = EnvironnementDepot(
            _episode_manuel(_affectation(0), _revue(0), defauts=(True,))
        )
        issue = environnement.commit(nom_branche(0), nom_fichier(0))
        self.assertTrue(issue.valide)
        self.assertTrue(issue.correcte)
        self.assertEqual(environnement.ci_branche(nom_branche(0)), ROUGE)

    def test_commit_sans_defaut_ci_verte(self) -> None:
        environnement = EnvironnementDepot(_episode_manuel(_affectation(0), defauts=(False,)))
        environnement.commit(nom_branche(0), nom_fichier(0))
        self.assertEqual(environnement.ci_branche(nom_branche(0)), VERTE)

    def test_commit_branche_inconnue_invalide(self) -> None:
        """Une branche jamais annoncée est refusée, l'état ne change pas (§S4.2)."""
        environnement = EnvironnementDepot(_episode_manuel(_affectation(0)))
        issue = environnement.commit("branche_9", "fichier_9")
        self.assertFalse(issue.valide)
        self.assertIn("error: branche inconnue ou fermée", issue.observation)
        self.assertIsNone(environnement.ci_branche("branche_9"))

    def test_create_pr_exige_une_branche_reelle(self) -> None:
        environnement = EnvironnementDepot(_episode_manuel(_affectation(0), _revue(0)))
        issue = environnement.create_pr(nom_branche(0))
        self.assertFalse(issue.valide)
        self.assertIn("error: branche_0 n'existe pas.", issue.observation)

    def test_create_pr_refuse_le_doublon(self) -> None:
        environnement = EnvironnementDepot(
            _episode_manuel(_affectation(0), _revue(0), _revue(0), _revue(0))
        )
        environnement.commit(nom_branche(0), nom_fichier(0))
        premiere = environnement.create_pr(nom_branche(0))
        self.assertTrue(premiere.valide)
        self.assertIn("PR #1 ouverte", premiere.observation)
        doublon = environnement.create_pr(nom_branche(0))
        self.assertFalse(doublon.valide)
        self.assertIn("déjà ouverte", doublon.observation)

    def test_fix_ci_exige_une_ci_rouge(self) -> None:
        environnement = EnvironnementDepot(
            _episode_manuel(_affectation(0), _revue(0), defauts=(False,))
        )
        environnement.commit(nom_branche(0), nom_fichier(0))
        issue = environnement.fix_ci(nom_branche(0))
        self.assertFalse(issue.valide)
        self.assertIn("n'est pas en échec", issue.observation)

    def test_fix_ci_corrige_et_le_defaut_ne_revient_pas(self) -> None:
        environnement = EnvironnementDepot(
            _episode_manuel(_affectation(0), _echec_ci(0, 1), _revue(0), _revue(0), defauts=(True,))
        )
        environnement.commit(nom_branche(0), nom_fichier(0))
        issue = environnement.fix_ci(nom_branche(0))
        self.assertTrue(issue.valide)
        self.assertEqual(environnement.ci_branche(nom_branche(0)), VERTE)
        environnement.commit(nom_branche(0), "fichier_9")
        self.assertEqual(environnement.ci_branche(nom_branche(0)), VERTE)

    def test_merge_pr_fermee_invalide(self) -> None:
        environnement = EnvironnementDepot(_episode_manuel(_affectation(0)))
        issue = environnement.merge(3)
        self.assertFalse(issue.valide)
        self.assertIn("error: PR #3 n'est pas ouverte.", issue.observation)

    def test_merge_supprime_la_branche_et_ferme_la_pr(self) -> None:
        environnement = EnvironnementDepot(
            _episode_manuel(
                _affectation(0), _revue(0), _ci_verte(0, 1), _affectation(1), _affectation(1)
            )
        )
        environnement.commit(nom_branche(0), nom_fichier(0))
        environnement.create_pr(nom_branche(0))
        issue = environnement.merge(1)
        self.assertTrue(issue.valide)
        self.assertTrue(issue.correcte)
        self.assertEqual(environnement.fichier_master(nom_fichier(0)), "contenu de fichier_0")
        self.assertIsNone(environnement.pr_ouverte(1))
        self.assertIsNone(environnement.ci_branche(nom_branche(0)))
        relance = environnement.commit(nom_branche(0), nom_fichier(0))
        self.assertFalse(relance.valide)
        self.assertIn("branche inconnue ou fermée", relance.observation)

    def test_merge_ci_rouge_valide_mais_casse(self) -> None:
        """`merge` sur CI rouge est VALIDE, nomme la casse et n'est jamais
        correct (§S4.2, §S4.5)."""
        environnement = EnvironnementDepot(
            _episode_manuel(_affectation(0), _revue(0), _ci_verte(0, 1), defauts=(True,))
        )
        environnement.commit(nom_branche(0), nom_fichier(0))
        environnement.create_pr(nom_branche(0))
        issue = environnement.merge(1)
        self.assertTrue(issue.valide)
        self.assertFalse(issue.correcte)
        self.assertIn("La CI de master est CASSÉE.", issue.observation)


class TestObligationsEtScore(unittest.TestCase):
    def test_partie_parfaite_score_et_resolution_pleins(self) -> None:
        """Le jeu parfait sur un épisode engendré vaut score 1.0 et résolution
        1.0 (§S4.4, §S4.5) — les numéros de PR réels y suivent les nominaux."""
        episode = generer_episode_depot(seed=3, horizon=60)
        environnement = EnvironnementDepot(episode)
        for evenement in episode.evenements:
            if evenement.type == AFFECTATION:
                issue = environnement.commit(
                    nom_branche(evenement.demande), nom_fichier(evenement.demande)
                )
            elif evenement.type == REVUE:
                issue = environnement.create_pr(nom_branche(evenement.demande))
            elif evenement.type == ECHEC_CI:
                issue = environnement.fix_ci(nom_branche(evenement.demande))
            else:
                assert evenement.pr is not None
                issue = environnement.merge(evenement.pr)
            self.assertTrue(issue.valide, issue.observation)
            self.assertTrue(issue.correcte, issue.observation)
        releve = environnement.completer_releve()
        self.assertEqual(releve.score, 1.0)
        self.assertEqual(releve.correctes, 60)
        self.assertGreater(environnement.demandes_jugees(), 0)
        self.assertEqual(releve.champs_libres["resolution"], 1.0)
        self.assertEqual(environnement.etat_terminal(), MOTIF_EPUISE)

    def test_action_valide_mais_autre_vaut_zero(self) -> None:
        """Un commit valide qui ne répond pas à l'affectation compte 0 (§S5.2)."""
        environnement = EnvironnementDepot(_episode_manuel(_affectation(0), _affectation(1)))
        environnement.commit(nom_branche(0), nom_fichier(0))
        issue = environnement.commit(nom_branche(0), "fichier_7")
        self.assertTrue(issue.valide)
        self.assertFalse(issue.correcte)
        self.assertEqual(environnement.releve.incorrectes, 1)

    def test_action_invalide_consomme_et_vaut_zero(self) -> None:
        environnement = EnvironnementDepot(_episode_manuel(_affectation(0)))
        environnement.merge(1)
        self.assertEqual(environnement.releve.invalides, 1)
        self.assertEqual(environnement.etat_terminal(), MOTIF_EPUISE)
        self.assertEqual(environnement.releve.score, 0.0)

    def test_wait_du_sur_revue_sans_branche(self) -> None:
        """Divergence : la branche n'a jamais été commitée, `wait` est dû (§S4.5)."""
        environnement = EnvironnementDepot(_episode_manuel(_affectation(0), _revue(0)))
        environnement.wait()
        issue = environnement.wait()
        self.assertTrue(issue.correcte)

    def test_wait_du_sur_echec_ci_sans_rouge(self) -> None:
        environnement = EnvironnementDepot(
            _episode_manuel(_affectation(0), _echec_ci(0, 1), defauts=(False,))
        )
        environnement.commit(nom_branche(0), nom_fichier(0))
        issue = environnement.wait()
        self.assertTrue(issue.correcte)

    def test_wait_du_sur_ci_verte_pr_absente(self) -> None:
        environnement = EnvironnementDepot(_episode_manuel(_affectation(0), _ci_verte(0, 1)))
        environnement.commit(nom_branche(0), nom_fichier(0))
        issue = environnement.wait()
        self.assertTrue(issue.correcte)

    def test_wait_indu_face_a_une_affectation(self) -> None:
        environnement = EnvironnementDepot(_episode_manuel(_affectation(0)))
        issue = environnement.wait()
        self.assertTrue(issue.valide)
        self.assertFalse(issue.correcte)

    def test_apres_la_fin_les_actions_ne_comptent_plus(self) -> None:
        environnement = EnvironnementDepot(_episode_manuel(_affectation(0)))
        environnement.wait()
        issue = environnement.wait()
        self.assertFalse(issue.valide)
        self.assertIn(MOTIF_EPUISE, issue.observation)
        self.assertEqual(environnement.releve.evenements_consommes, 1)


class TestResolution(unittest.TestCase):
    def test_resolution_none_sans_demande_jugee(self) -> None:
        """Une demande coupée en milieu de cycle n'est pas jugée (§S4.4)."""
        environnement = EnvironnementDepot(_episode_manuel(_affectation(0), _revue(0)))
        self.assertIsNone(environnement.resolution())
        releve = environnement.completer_releve()
        self.assertIsNone(releve.champs_libres["resolution"])
        self.assertEqual(releve.champs_libres["demandes_jugees"], 0)

    def test_fusion_cassee_ne_resout_pas(self) -> None:
        """La demande fusionnée en CI rouge n'est pas correctement résolue (§S4.4)."""
        environnement = EnvironnementDepot(
            _episode_manuel(_affectation(0), _revue(0), _ci_verte(0, 1), defauts=(True,))
        )
        environnement.commit(nom_branche(0), nom_fichier(0))
        environnement.create_pr(nom_branche(0))
        environnement.merge(1)
        self.assertEqual(environnement.demandes_jugees(), 1)
        self.assertEqual(environnement.demandes_resolues(), 0)
        self.assertEqual(environnement.resolution(), 0.0)

    def test_demande_jugee_non_fusionnee_non_resolue(self) -> None:
        environnement = EnvironnementDepot(
            _episode_manuel(_affectation(0), _revue(0), _ci_verte(0, 1))
        )
        environnement.commit(nom_branche(0), nom_fichier(0))
        environnement.create_pr(nom_branche(0))
        environnement.wait()
        self.assertEqual(environnement.resolution(), 0.0)


class TestObservation(unittest.TestCase):
    def test_observation_porte_le_bruit_sous_en_tete(self) -> None:
        episode = generer_episode_depot(seed=9, horizon=3, bruit=4)
        environnement = EnvironnementDepot(episode)
        observation = environnement.observation()
        self.assertIn(ENTETE_TELEMETRIE, observation)
        lignes = observation.split("\n")
        self.assertEqual(len(lignes), 1 + 1 + 4)

    def test_observation_apres_la_fin_rend_le_motif(self) -> None:
        environnement = EnvironnementDepot(_episode_manuel(_affectation(0)))
        environnement.wait()
        self.assertEqual(environnement.observation(), MOTIF_EPUISE)


if __name__ == "__main__":
    unittest.main()
