"""Preuves de l'environnement Entrepôt du banc a : générateur, transitions, score, bruit.

@verifies docs/BACKLOG.md U29a1 — environnement Entrepôt du banc a
@verifies docs/SPEC_BANCS.md §S1.4 (déterminisme à seed égal), §S3.2 (validité et
          refus nommés, l'état ne change pas sur action invalide), §S3.3 (types
          faisables seulement), §S3.4 (résolution nominale, divergence payée au
          score), §S3.5 (obligations, `wait` dû sur maintenance d'étagère vide),
          §S3.6 (bruit : en-tête, comptage, aucun effet d'état), §S3.7 (une action
          consomme l'événement, motif de fin), §S5.1 (score continu),
          §S5.2 (première action seule, invalide et valide-mais-autre valent 0)
"""

from __future__ import annotations

import unittest

from avo.bancs.skillexec.entrepot import (
    MOTIF_EPUISE,
    EnvironnementEntrepot,
    IssueBanc,
)
from avo.bancs.skillexec.generation import (
    COMMANDE,
    ENTETE_TELEMETRIE,
    MAINTENANCE,
    RECEPTION,
    Episode,
    EvenementEntrepot,
    generer_episode,
    nom_etagere,
)


def _episode_manuel(*evenements: EvenementEntrepot, bruit: int = 0) -> Episode:
    """Épisode construit à la main pour éprouver une transition précise."""
    return Episode(
        seed=0,
        horizon=len(evenements),
        bruit=bruit,
        evenements=tuple(evenements),
        telemetrie=tuple(() for _ in evenements),
    )


def _reception(article: str) -> EvenementEntrepot:
    return EvenementEntrepot(RECEPTION, article, None, f"Livraison reçue : {article}.")


def _commande(article: str) -> EvenementEntrepot:
    return EvenementEntrepot(COMMANDE, article, None, f"Commande client : {article}.")


def _maintenance(article: str, etagere: str) -> EvenementEntrepot:
    return EvenementEntrepot(MAINTENANCE, article, etagere, f"Maintenance requise sur {etagere}.")


class TestGenerateur(unittest.TestCase):
    def test_deterministe_a_seed_egal(self) -> None:
        a = generer_episode(seed=42, horizon=50, bruit=5)
        b = generer_episode(seed=42, horizon=50, bruit=5)
        self.assertEqual(a, b)

    def test_seeds_differents_episodes_differents(self) -> None:
        a = generer_episode(seed=42, horizon=50)
        b = generer_episode(seed=43, horizon=50)
        self.assertNotEqual(a.evenements, b.evenements)

    def test_types_faisables_seulement(self) -> None:
        """Une commande ou une maintenance ne peut viser qu'un article présent à
        l'état nominal — rejouer le jeu parfait le vérifie pas à pas (§S3.3)."""
        episode = generer_episode(seed=7, horizon=120)
        nominal: dict[str, str | None] = {}
        for evenement in episode.evenements:
            presents = {a for a in nominal.values() if a is not None}
            if evenement.type == RECEPTION:
                self.assertNotIn(evenement.article, presents)
                cible = min(
                    (n for n in range(500) if nominal.get(nom_etagere(n)) is None),
                )
                nominal[nom_etagere(cible)] = evenement.article
            elif evenement.type == COMMANDE:
                self.assertIn(evenement.article, presents)
                for nom, article in nominal.items():
                    if article == evenement.article:
                        nominal[nom] = None
            else:
                self.assertEqual(evenement.type, MAINTENANCE)
                assert evenement.etagere is not None
                self.assertEqual(nominal.get(evenement.etagere), evenement.article)
                cible = min(
                    (n for n in range(500) if nominal.get(nom_etagere(n)) is None),
                )
                nominal[evenement.etagere] = None
                nominal[nom_etagere(cible)] = evenement.article

    def test_premier_evenement_est_une_reception(self) -> None:
        for seed in range(5):
            episode = generer_episode(seed=seed, horizon=1)
            self.assertEqual(episode.evenements[0].type, RECEPTION)

    def test_bruit_compte_et_deterministe(self) -> None:
        episode = generer_episode(seed=3, horizon=10, bruit=4)
        self.assertEqual(len(episode.telemetrie), 10)
        for lignes in episode.telemetrie:
            self.assertEqual(len(lignes), 4)

    def test_parametres_negatifs_refuses(self) -> None:
        with self.assertRaises(ValueError):
            generer_episode(seed=1, horizon=-1)
        with self.assertRaises(ValueError):
            generer_episode(seed=1, horizon=1, bruit=-1)


class TestTransitions(unittest.TestCase):
    def test_store_valide_et_correct(self) -> None:
        env = EnvironnementEntrepot(_episode_manuel(_reception("article_0")))
        issue = env.store("article_0", "etagere_9")
        self.assertEqual(issue, IssueBanc("Succès : article_0 rangé sur etagere_9.", True, True))
        self.assertEqual(env.etagere("etagere_9"), "article_0")

    def test_store_refuse_etagere_occupee_sans_changer_l_etat(self) -> None:
        env = EnvironnementEntrepot(
            _episode_manuel(_reception("article_0"), _reception("article_1"))
        )
        env.store("article_0", "etagere_0")
        issue = env.store("article_1", "etagere_0")
        self.assertFalse(issue.valide)
        self.assertIn("occupée", issue.observation)
        self.assertTrue(issue.observation.startswith("error:"))
        self.assertEqual(env.etagere("etagere_0"), "article_0")

    def test_store_refuse_article_hors_quai(self) -> None:
        env = EnvironnementEntrepot(_episode_manuel(_reception("article_0")))
        issue = env.store("article_99", "etagere_0")
        self.assertFalse(issue.valide)
        self.assertIn("attente de rangement", issue.observation)

    def test_store_refuse_etagere_inconnue(self) -> None:
        env = EnvironnementEntrepot(_episode_manuel(_reception("article_0")))
        issue = env.store("article_0", "etagere_500")
        self.assertFalse(issue.valide)
        self.assertIn("inconnue", issue.observation)

    def test_ship_valide_et_correct(self) -> None:
        env = EnvironnementEntrepot(
            _episode_manuel(_reception("article_0"), _commande("article_0"))
        )
        env.store("article_0", "etagere_4")
        issue = env.ship("article_0", "etagere_4")
        self.assertTrue(issue.valide)
        self.assertTrue(issue.correcte)
        self.assertIsNone(env.etagere("etagere_4"))

    def test_ship_refuse_mauvaise_etagere(self) -> None:
        env = EnvironnementEntrepot(
            _episode_manuel(_reception("article_0"), _commande("article_0"))
        )
        env.store("article_0", "etagere_4")
        issue = env.ship("article_0", "etagere_5")
        self.assertFalse(issue.valide)
        self.assertEqual(env.etagere("etagere_4"), "article_0")

    def test_move_valide_et_correct(self) -> None:
        env = EnvironnementEntrepot(
            _episode_manuel(_reception("article_0"), _maintenance("article_0", "etagere_2"))
        )
        env.store("article_0", "etagere_2")
        issue = env.move("article_0", "etagere_2", "etagere_7")
        self.assertTrue(issue.valide)
        self.assertTrue(issue.correcte)
        self.assertIsNone(env.etagere("etagere_2"))
        self.assertEqual(env.etagere("etagere_7"), "article_0")

    def test_move_refuse_destination_occupee(self) -> None:
        env = EnvironnementEntrepot(
            _episode_manuel(
                _reception("article_0"),
                _reception("article_1"),
                _maintenance("article_0", "etagere_0"),
            )
        )
        env.store("article_0", "etagere_0")
        env.store("article_1", "etagere_1")
        issue = env.move("article_0", "etagere_0", "etagere_1")
        self.assertFalse(issue.valide)
        self.assertEqual(env.etagere("etagere_0"), "article_0")
        self.assertEqual(env.etagere("etagere_1"), "article_1")

    def test_store_tardif_reste_valide_mais_jamais_correct(self) -> None:
        """Une réception non honorée laisse l'article au quai : le ranger plus
        tard est valide, mais ce n'est plus l'obligation d'aucun événement."""
        env = EnvironnementEntrepot(
            _episode_manuel(_reception("article_0"), _reception("article_1"))
        )
        env.wait()
        issue = env.store("article_0", "etagere_0")
        self.assertTrue(issue.valide)
        self.assertFalse(issue.correcte)


class TestObligationsEtScore(unittest.TestCase):
    def test_jeu_parfait_score_1(self) -> None:
        """Jouer l'obligation de chaque événement rend un score de 1 (§S5.1)."""
        episode = generer_episode(seed=11, horizon=40)
        env = EnvironnementEntrepot(episode)
        positions: dict[str, str] = {}
        vides = [nom_etagere(n) for n in range(500)]
        for evenement in episode.evenements:
            if evenement.type == RECEPTION:
                cible = vides.pop(0)
                issue = env.store(evenement.article, cible)
                positions[evenement.article] = cible
            elif evenement.type == COMMANDE:
                ou = positions.pop(evenement.article)
                vides.insert(0, ou)
                vides.sort(key=lambda n: int(n.split("_")[1]))
                issue = env.ship(evenement.article, ou)
            else:
                assert evenement.etagere is not None
                cible = vides.pop(0)
                issue = env.move(evenement.article, evenement.etagere, cible)
                vides.insert(0, evenement.etagere)
                vides.sort(key=lambda n: int(n.split("_")[1]))
                positions[evenement.article] = cible
            self.assertTrue(issue.correcte, issue.observation)
        self.assertEqual(env.releve.score, 1.0)
        self.assertEqual(env.releve.correctes, 40)
        self.assertEqual(env.etat_terminal(), MOTIF_EPUISE)

    def test_action_valide_mais_autre_vaut_zero(self) -> None:
        """Ranger le bon article pendant une commande est valide, pas correct."""
        env = EnvironnementEntrepot(
            _episode_manuel(
                _reception("article_0"), _reception("article_1"), _commande("article_0")
            )
        )
        env.store("article_0", "etagere_0")
        env.wait()
        issue = env.store("article_1", "etagere_1")
        self.assertTrue(issue.valide)
        self.assertFalse(issue.correcte)
        self.assertEqual(env.releve.correctes, 1)
        self.assertEqual(env.releve.incorrectes, 2)
        self.assertEqual(env.releve.score, 1 / 3)

    def test_action_invalide_consomme_et_vaut_zero(self) -> None:
        env = EnvironnementEntrepot(
            _episode_manuel(_reception("article_0"), _reception("article_1"))
        )
        env.ship("article_9", "etagere_3")
        self.assertEqual(env.releve.invalides, 1)
        self.assertIn("Livraison reçue : article_1.", env.observation())

    def test_wait_du_sur_maintenance_d_etagere_vide(self) -> None:
        """Divergence §S3.4 : la maintenance vise une étagère nominale que l'agent
        a laissée vide — l'obligation devient `wait` (§S3.5)."""
        env = EnvironnementEntrepot(
            _episode_manuel(_reception("article_0"), _maintenance("article_0", "etagere_0"))
        )
        env.store("article_0", "etagere_8")
        issue = env.wait()
        self.assertTrue(issue.correcte)

    def test_wait_indu_vaut_zero(self) -> None:
        env = EnvironnementEntrepot(_episode_manuel(_reception("article_0")))
        issue = env.wait()
        self.assertTrue(issue.valide)
        self.assertFalse(issue.correcte)
        self.assertEqual(env.releve.incorrectes, 1)

    def test_score_horizon_nul(self) -> None:
        env = EnvironnementEntrepot(_episode_manuel())
        self.assertEqual(env.releve.score, 0.0)
        self.assertEqual(env.etat_terminal(), MOTIF_EPUISE)

    def test_action_apres_la_fin_ni_comptee_ni_appliquee(self) -> None:
        env = EnvironnementEntrepot(_episode_manuel(_reception("article_0")))
        env.store("article_0", "etagere_0")
        issue = env.wait()
        self.assertFalse(issue.valide)
        self.assertIn(MOTIF_EPUISE, issue.observation)
        self.assertEqual(env.releve.evenements_consommes, 1)

    def test_releve_en_dict(self) -> None:
        env = EnvironnementEntrepot(_episode_manuel(_reception("article_0")))
        env.store("article_0", "etagere_0")
        d = env.releve.en_dict()
        self.assertEqual(d["score"], 1.0)
        self.assertEqual(d["horizon"], 1)
        self.assertIsNone(d["tokens_consommes"])


class TestBruit(unittest.TestCase):
    def test_observation_porte_l_entete_et_les_lignes(self) -> None:
        episode = generer_episode(seed=5, horizon=3, bruit=2)
        env = EnvironnementEntrepot(episode)
        observation = env.observation()
        self.assertIn(ENTETE_TELEMETRIE, observation)
        self.assertEqual(observation.splitlines()[0], episode.evenements[0].observation)
        self.assertEqual(len(observation.splitlines()), 1 + 1 + 2)

    def test_sans_bruit_pas_d_entete(self) -> None:
        env = EnvironnementEntrepot(generer_episode(seed=5, horizon=3))
        self.assertNotIn(ENTETE_TELEMETRIE, env.observation())

    def test_le_bruit_n_altere_pas_l_etat(self) -> None:
        """Deux épisodes de même seed, avec et sans bruit, portent exactement les
        mêmes événements (§S3.6) — le bruit est purement observationnel."""
        avec = generer_episode(seed=9, horizon=30, bruit=8)
        sans = generer_episode(seed=9, horizon=30, bruit=0)
        self.assertEqual(avec.evenements, sans.evenements)


if __name__ == "__main__":
    unittest.main()
