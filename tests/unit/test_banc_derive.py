"""Preuves de la dérive d'état (condition 3) : génération, application réelle,
alerte, mesure de récupération — sur les deux environnements du banc a.

@verifies docs/BACKLOG.md U29a4 — dérive d'état et campagne de banc
@verifies docs/SPEC_BANCS.md §S3.8 (dérive Entrepôt : unicité, pas forcé
          `commande`, alerte non structurée, erreur nommée sans candidat,
          génération inchangée à `derive` inactif, application réelle et cas de
          divergence), §S4.7 (dérive Dépôt : CI cassée par commit direct,
          événement `ci_verte` périmé forcé, obligation réelle `wait`),
          §S5.5 (pas_de_recuperation, recupere, champs absents sans dérive)
"""

from __future__ import annotations

import unittest

from avo.bancs.skillexec.depot import (
    CI_VERTE,
    ROUGE,
    DeriveDepot,
    EnvironnementDepot,
    EpisodeDepot,
    generer_episode_depot,
    nom_branche,
)
from avo.bancs.skillexec.entrepot import EnvironnementEntrepot
from avo.bancs.skillexec.generation import (
    COMMANDE,
    ENTETE_ALERTE,
    DeriveEntrepot,
    Episode,
    EvenementEntrepot,
    generer_episode,
)

# --------------------------------------------------------------------- entrepôt


def _episode_derive_manuel(
    *evenements: EvenementEntrepot, derive: DeriveEntrepot | None
) -> Episode:
    """Épisode Entrepôt construit à la main, porteur d'une dérive (§S3.8)."""
    return Episode(
        seed=0,
        horizon=len(evenements),
        bruit=0,
        evenements=tuple(evenements),
        telemetrie=tuple(() for _ in evenements),
        derive=derive,
    )


def _reception(article: str) -> EvenementEntrepot:
    return EvenementEntrepot("reception", article, None, f"Livraison reçue : {article}.")


def _commande(article: str) -> EvenementEntrepot:
    return EvenementEntrepot(COMMANDE, article, None, f"Commande client : {article}.")


_DERIVE_A0 = DeriveEntrepot(
    evenement=1,
    article="article_0",
    source="etagere_0",
    destination="etagere_1",
    alerte="[Audit externe] article_0 déplacé de etagere_0 vers etagere_1 "
    "par un opérateur externe.",
)


class GenerationDeriveEntrepot(unittest.TestCase):
    def test_derive_unique_deterministe_et_pas_force(self) -> None:
        """§S3.8 : une seule dérive, au premier pas ≥ horizon // 2, événement
        forcé `commande` de l'article déplacé, identique à seed égal."""
        episode = generer_episode(1, 10, derive=True)
        self.assertEqual(episode, generer_episode(1, 10, derive=True))
        derive = episode.derive
        assert derive is not None
        self.assertGreaterEqual(derive.evenement, 5)
        force = episode.evenements[derive.evenement]
        self.assertEqual(force.type, COMMANDE)
        self.assertEqual(force.article, derive.article)
        self.assertIn(derive.article, derive.alerte)
        self.assertIn(derive.source, derive.alerte)
        self.assertIn(derive.destination, derive.alerte)

    def test_generation_inchangee_sans_derive(self) -> None:
        """§S3.8 : à `derive` inactif, aucun champ et mêmes épisodes ; avec
        dérive, les pas AVANT `d` sont ceux de l'épisode sans dérive — le rng
        principal n'est pas consommé au pas forcé."""
        sans = generer_episode(1, 10)
        self.assertIsNone(sans.derive)
        avec = generer_episode(1, 10, derive=True)
        derive = avec.derive
        assert derive is not None
        self.assertEqual(avec.evenements[: derive.evenement], sans.evenements[: derive.evenement])

    def test_erreur_nommee_sans_candidat(self) -> None:
        """§S3.8 : aucun pas n'offre de candidat — l'erreur le nomme."""
        with self.assertRaises(ValueError) as arret:
            generer_episode(1, 1, derive=True)
        self.assertIn("aucun candidat de dérive", str(arret.exception))


class DeriveEntrepotReelle(unittest.TestCase):
    def test_alerte_application_reelle_et_recuperation_immediate(self) -> None:
        """§S3.8, §S5.5 : l'alerte accompagne le pas porteur, l'état réel est
        déplacé, et l'action correcte au pas `d` rend une récupération de 0."""
        env = EnvironnementEntrepot(
            _episode_derive_manuel(
                _reception("article_0"), _commande("article_0"), derive=_DERIVE_A0
            )
        )
        env.store("article_0", "etagere_0")
        observation = env.observation()
        self.assertIn(ENTETE_ALERTE, observation)
        self.assertIn(_DERIVE_A0.alerte, observation)
        self.assertEqual(env.etagere("etagere_1"), "article_0")
        self.assertIsNone(env.etagere("etagere_0"))
        issue = env.ship("article_0", "etagere_1")
        self.assertTrue(issue.correcte)
        releve = env.completer_releve()
        self.assertEqual(releve.champs_libres["derive_evenement"], 1)
        self.assertEqual(releve.champs_libres["pas_de_recuperation"], 0)
        self.assertTrue(releve.champs_libres["recupere"])

    def test_etat_perime_paye_et_non_recupere(self) -> None:
        """§S3.8, §S5.5 : expédier depuis l'étagère d'avant la dérive est
        invalide, et l'épisode se clôt non récupéré."""
        env = EnvironnementEntrepot(
            _episode_derive_manuel(
                _reception("article_0"), _commande("article_0"), derive=_DERIVE_A0
            )
        )
        env.store("article_0", "etagere_0")
        env.observation()
        issue = env.ship("article_0", "etagere_0")
        self.assertFalse(issue.valide)
        releve = env.completer_releve()
        self.assertIsNone(releve.champs_libres["pas_de_recuperation"])
        self.assertFalse(releve.champs_libres["recupere"])

    def test_recuperation_apres_retard(self) -> None:
        """§S5.5 : la première action correcte APRÈS le pas porteur compte le
        retard en événements consommés depuis la dérive."""
        env = EnvironnementEntrepot(
            _episode_derive_manuel(
                _reception("article_0"),
                _commande("article_0"),
                _reception("article_1"),
                derive=_DERIVE_A0,
            )
        )
        env.store("article_0", "etagere_0")
        env.observation()
        env.ship("article_0", "etagere_0")
        issue = env.store("article_1", "etagere_0")
        self.assertTrue(issue.correcte)
        self.assertEqual(env.completer_releve().champs_libres["pas_de_recuperation"], 1)

    def test_divergence_etat_reel_inchange(self) -> None:
        """§S3.8 : l'agent a divergé — l'article n'est nulle part — l'alerte est
        émise telle quelle et l'état réel ne bouge pas."""
        env = EnvironnementEntrepot(
            _episode_derive_manuel(
                _reception("article_0"), _commande("article_0"), derive=_DERIVE_A0
            )
        )
        env.wait()
        observation = env.observation()
        self.assertIn(ENTETE_ALERTE, observation)
        self.assertIsNone(env.etagere("etagere_1"))

    def test_sans_derive_aucun_champ(self) -> None:
        """§S5.5 : un épisode sans dérive ne porte aucun champ de récupération."""
        env = EnvironnementEntrepot(_episode_derive_manuel(_reception("article_0"), derive=None))
        env.store("article_0", "etagere_0")
        self.assertNotIn("derive_evenement", env.completer_releve().champs_libres)


# ----------------------------------------------------------------------- dépôt


def _episode_depot_derive(derive: DeriveDepot | None = None) -> EpisodeDepot:
    """Épisode Dépôt minimal : affectation, revue, `ci_verte` périmé porteur."""
    from tests.unit.test_banc_depot import _affectation, _ci_verte, _revue

    return EpisodeDepot(
        seed=0,
        horizon=3,
        bruit=0,
        evenements=(_affectation(0), _revue(0), _ci_verte(0, 1)),
        telemetrie=((), (), ()),
        defauts=(False,),
        derive=derive,
    )


_DERIVE_D0 = DeriveDepot(
    evenement=2,
    demande=0,
    pr=1,
    alerte="[Alerte] Commit direct sur branche_0 : sa CI est repassée au rouge.",
)


class GenerationDeriveDepot(unittest.TestCase):
    def test_derive_unique_deterministe_et_pas_force(self) -> None:
        """§S4.7 : une seule dérive, pas ≥ horizon // 2, événement forcé
        `ci_verte` de la PR nominale de la demande cassée."""
        episode = generer_episode_depot(1, 16, derive=True)
        self.assertEqual(episode, generer_episode_depot(1, 16, derive=True))
        derive = episode.derive
        assert derive is not None
        self.assertGreaterEqual(derive.evenement, 8)
        force = episode.evenements[derive.evenement]
        self.assertEqual(force.type, CI_VERTE)
        self.assertEqual(force.demande, derive.demande)
        self.assertEqual(force.pr, derive.pr)
        self.assertIn(nom_branche(derive.demande), derive.alerte)

    def test_generation_inchangee_sans_derive(self) -> None:
        """§S4.7 : mêmes pas avant `d`, aucun champ à `derive` inactif."""
        sans = generer_episode_depot(1, 16)
        self.assertIsNone(sans.derive)
        avec = generer_episode_depot(1, 16, derive=True)
        derive = avec.derive
        assert derive is not None
        self.assertEqual(avec.evenements[: derive.evenement], sans.evenements[: derive.evenement])

    def test_erreur_nommee_sans_candidat(self) -> None:
        """§S4.7 : aucune demande prête à fusionner — l'erreur le nomme."""
        with self.assertRaises(ValueError) as arret:
            generer_episode_depot(1, 1, derive=True)
        self.assertIn("aucun candidat de dérive", str(arret.exception))


class DeriveDepotReelle(unittest.TestCase):
    def _prepare(self) -> EnvironnementDepot:
        env = EnvironnementDepot(_episode_depot_derive(_DERIVE_D0))
        env.commit("branche_0", "fichier_0")
        env.create_pr("branche_0")
        return env

    def test_alerte_ci_cassee_et_wait_du(self) -> None:
        """§S4.7, §S5.5 : au pas porteur la CI réelle passe rouge, l'alerte
        accompagne l'événement périmé, et `wait` est l'obligation — récupération
        immédiate."""
        env = self._prepare()
        observation = env.observation()
        self.assertIn(ENTETE_ALERTE, observation)
        self.assertIn(_DERIVE_D0.alerte, observation)
        self.assertEqual(env.ci_branche("branche_0"), ROUGE)
        issue = env.wait()
        self.assertTrue(issue.correcte)
        releve = env.completer_releve()
        self.assertEqual(releve.champs_libres["derive_evenement"], 2)
        self.assertEqual(releve.champs_libres["pas_de_recuperation"], 0)
        self.assertTrue(releve.champs_libres["recupere"])

    def test_fusion_perimee_casse_master_et_non_recuperee(self) -> None:
        """§S4.7 : fusionner sur la notification périmée est valide mais
        incorrect, casse master, et la demande n'est pas résolue."""
        env = self._prepare()
        env.observation()
        issue = env.merge("1")
        self.assertTrue(issue.valide)
        self.assertFalse(issue.correcte)
        self.assertIn("CASSÉE", issue.observation)
        releve = env.completer_releve()
        self.assertEqual(releve.champs_libres["resolution"], 0.0)
        self.assertFalse(releve.champs_libres["recupere"])

    def test_divergence_etat_reel_inchange(self) -> None:
        """§S4.7 : la branche n'existe pas réellement — l'état réel ne bouge
        pas, l'alerte est émise, et `wait` reste dû (§S4.5)."""
        env = EnvironnementDepot(_episode_depot_derive(_DERIVE_D0))
        env.wait()
        env.wait()
        observation = env.observation()
        self.assertIn(ENTETE_ALERTE, observation)
        self.assertIsNone(env.ci_branche("branche_0"))
        self.assertTrue(env.wait().correcte)


if __name__ == "__main__":
    unittest.main()
