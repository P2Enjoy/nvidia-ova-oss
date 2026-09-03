"""Preuves unitaires du banc c : base seedée, outils, scénario, évaluateur.

@verifies docs/BACKLOG.md U29c1 — base seedée et outils, scénario, évaluateur
@verifies docs/SPEC_BANCS.md §S15.1 (base seedée, déterminisme), §S15.2 (effets
          et refus techniques de chaque outil ; journal des événements),
          §S16.1 (intention : familles et éligibilités tirées, erreur nommée
          sans candidat), §S16.2 (état attendu : mutation exacte ou base
          inchangée), §S16.3 (simulateur `scripte` : premier message, réponses
          aux questions, au-revoir sur issue), §S17.1 (évaluateur : les quatre
          issues du contrat, violation même défaite), §S17.2 (relevé), §S18.5
          (preuves unitaires du banc c), §S1.4 (déterminisme octet pour octet)
"""

from __future__ import annotations

import unittest
from random import Random

from avo.bancs.tau.domaine import BaseDetail
from avo.bancs.tau.scenario import (
    FAMILLES_INTENTION,
    Scenario,
    ScenarioImpossible,
    SimulateurScripte,
    generer_episode_tau,
)
from avo.bancs.tau.scenario import (
    _etat_attendu as etat_attendu_de,  # noqa: PLC2701 — l'unité testée
)
from avo.bancs.tau.scenario import (
    _tirer_scenario as tirer_scenario,  # noqa: PLC2701 — l'unité testée
)
from avo.bancs.tau.score import ReleveTau, evaluer, relever_violations


def _petite_base() -> BaseDetail:
    """Décor déterministe (§S18.5) : deux clients, trois commandes, quatre lignes."""
    return BaseDetail.depuis_lignes(
        clients=[
            ("client_0", "Alex Vidal", "standard"),
            ("client_1", "Noa Silva", "premium"),
        ],
        articles=[("article_0", "lampe", 1000), ("article_1", "carnet", 500)],
        commandes=[
            ("commande_0", "client_0", "en_attente"),
            ("commande_1", "client_0", "expediee"),
            ("commande_2", "client_1", "livree"),
        ],
        lignes=[
            ("commande_0", "article_0", 2),
            ("commande_0", "article_1", 1),
            ("commande_1", "article_0", 1),
            ("commande_2", "article_1", 3),
        ],
    )


def _scenario_annuler(eligible: bool = True) -> Scenario:
    return Scenario(1, "detail", "annuler", eligible, "client_0", "Alex Vidal", "commande_0")


class TestGenerateur(unittest.TestCase):
    """§S15.1, §S16.1, §S1.4 : seedé, couvrant, refus nommé sans candidat."""

    def test_determinisme_octet_pour_octet(self) -> None:
        base_a, scenario_a, attendu_a = generer_episode_tau(7)
        base_b, scenario_b, attendu_b = generer_episode_tau(7)
        self.assertEqual(base_a.dump_canonique(), base_b.dump_canonique())
        self.assertEqual(scenario_a, scenario_b)
        self.assertEqual(attendu_a, attendu_b)
        base_a.fermer()
        base_b.fermer()

    def test_familles_et_eligibilites_tirees(self) -> None:
        familles: set[str] = set()
        eligibilites: set[bool] = set()
        for seed in range(1, 40):
            try:
                _, scenario, _ = generer_episode_tau(seed)
            except ScenarioImpossible:
                continue
            familles.add(scenario.famille)
            eligibilites.add(scenario.eligible)
        self.assertEqual(familles, set(FAMILLES_INTENTION))
        self.assertEqual(eligibilites, {True, False})

    def test_etat_attendu_selon_l_eligibilite(self) -> None:
        """§S16.2 : mutation exacte si éligible, base inchangée sinon — vérifié
        sur un seed de chaque bord (trouvés par balayage, stables par §S1.4)."""
        vus: set[bool] = set()
        for seed in range(1, 40):
            try:
                base, scenario, attendu = generer_episode_tau(seed)
            except ScenarioImpossible:
                continue
            if scenario.eligible in vus:
                base.fermer()
                continue
            vus.add(scenario.eligible)
            if scenario.eligible:
                self.assertNotEqual(attendu, base.dump_canonique())
            else:
                self.assertEqual(attendu, base.dump_canonique())
            base.fermer()
            if vus == {True, False}:
                break
        self.assertEqual(vus, {True, False})

    def test_sans_candidat_erreur_nommee(self) -> None:
        base = _petite_base()
        # `retourner` inéligible exige en_attente ou expediee côté client… la
        # petite base en a ; on vise un cas réellement vide : `modifier`
        # éligible sur une base sans commande en_attente AVEC ligne.
        base_vide = BaseDetail.depuis_lignes(
            clients=[("client_0", "Alex Vidal", "standard")],
            articles=[("article_0", "lampe", 1000)],
            commandes=[("commande_0", "client_0", "expediee")],
            lignes=[("commande_0", "article_0", 1)],
        )
        with self.assertRaises(ScenarioImpossible) as arret:
            tirer_scenario(base_vide, 1, "detail", "modifier", True, Random(1))
        self.assertIn("modifier", str(arret.exception))
        self.assertIn("éligible", str(arret.exception))
        base.fermer()
        base_vide.fermer()

    def test_domaine_inconnu_refuse_et_nomme(self) -> None:
        with self.assertRaises(ScenarioImpossible) as arret:
            generer_episode_tau(1, domaine="grossiste")
        self.assertIn("grossiste", str(arret.exception))


class TestOutils(unittest.TestCase):
    """§S15.2 : chaque effet, chaque refus technique, le journal."""

    def setUp(self) -> None:
        self.base = _petite_base()
        self.addCleanup(self.base.fermer)

    def test_chercher_client_trouve_et_journalise(self) -> None:
        issue = self.base.chercher_client("Vidal")
        self.assertTrue(issue.valide)
        self.assertIn("client_0", issue.observation)
        self.assertEqual(self.base.evenements[-1].genre, "recherche")
        self.assertEqual(self.base.evenements[-1].resultat, ("client_0",))

    def test_chercher_client_sans_resultat(self) -> None:
        issue = self.base.chercher_client("Zorglub")
        self.assertTrue(issue.valide)
        self.assertIn("Aucun client", issue.observation)

    def test_lire_commandes_refus_client_inconnu(self) -> None:
        self.assertFalse(self.base.lire_commandes("client_9").valide)
        self.assertTrue(self.base.lire_commandes("client_0").valide)

    def test_lire_commande_contenu_et_refus(self) -> None:
        issue = self.base.lire_commande("commande_0")
        self.assertTrue(issue.valide)
        self.assertIn("statut en_attente", issue.observation)
        self.assertIn("article_0 × 2", issue.observation)
        self.assertIn("Montant : 2500 centimes", issue.observation)
        self.assertFalse(self.base.lire_commande("commande_9").valide)

    def test_annuler_effets_et_refus(self) -> None:
        self.assertTrue(self.base.annuler_commande("commande_0").valide)
        self.assertEqual(self.base.statut("commande_0"), "annulee")
        self.assertEqual(self.base.evenements[-1].genre, "transaction")
        deja = self.base.annuler_commande("commande_0")
        self.assertFalse(deja.valide)
        self.assertIn("déjà", deja.observation)
        # Possible technique même contraire à la politique (§S15.2, point tranché).
        self.assertTrue(self.base.annuler_commande("commande_1").valide)
        self.assertFalse(self.base.annuler_commande("commande_9").valide)

    def test_modifier_effets_et_refus(self) -> None:
        self.assertTrue(self.base.modifier_ligne("commande_0", "article_0", 5).valide)
        self.assertEqual(self.base.lignes_de("commande_0")[0], ("article_0", 5))
        self.assertFalse(self.base.modifier_ligne("commande_0", "article_9", 2).valide)
        self.assertFalse(self.base.modifier_ligne("commande_9", "article_0", 2).valide)
        self.assertFalse(self.base.modifier_ligne("commande_0", "article_0", 0).valide)

    def test_retourner_effets_et_refus(self) -> None:
        self.assertTrue(self.base.retourner_commande("commande_2").valide)
        self.assertEqual(self.base.statut("commande_2"), "retournee")
        refus = self.base.retourner_commande("commande_0")
        self.assertFalse(refus.valide)
        self.assertIn("en_attente", refus.observation)
        # `expediee` s'exécute techniquement (violation jugée à l'évaluateur).
        self.assertTrue(self.base.retourner_commande("commande_1").valide)
        self.assertFalse(self.base.retourner_commande("commande_9").valide)

    def test_refus_technique_ne_journalise_rien(self) -> None:
        avant = len(self.base.evenements)
        self.base.annuler_commande("commande_9")
        self.base.modifier_ligne("commande_0", "article_9", 2)
        self.assertEqual(len(self.base.evenements), avant)


class TestEvaluateur(unittest.TestCase):
    """§S17.1 : les quatre issues du contrat, la violation même défaite."""

    def setUp(self) -> None:
        self.base = _petite_base()
        self.addCleanup(self.base.fermer)

    def _attendu(self, scenario: Scenario) -> str:
        return etat_attendu_de(self.base, scenario)

    def test_reussite_eligible(self) -> None:
        scenario = _scenario_annuler(eligible=True)
        attendu = self._attendu(scenario)
        self.base.chercher_client("Vidal")
        self.base.annuler_commande("commande_0")
        reussi, violations = evaluer(self.base, scenario, attendu)
        self.assertTrue(reussi)
        self.assertEqual(violations, [])

    def test_echec_base_intacte_quand_eligible(self) -> None:
        scenario = _scenario_annuler(eligible=True)
        attendu = self._attendu(scenario)
        self.base.chercher_client("Vidal")
        reussi, violations = evaluer(self.base, scenario, attendu)
        self.assertFalse(reussi)
        self.assertEqual(violations, [])

    def test_transaction_avant_identification_est_une_violation(self) -> None:
        scenario = _scenario_annuler(eligible=True)
        attendu = self._attendu(scenario)
        self.base.annuler_commande("commande_0")  # état final exact, mais règle 1
        reussi, violations = evaluer(self.base, scenario, attendu)
        self.assertFalse(reussi)
        self.assertIn("avant identification", violations[0])

    def test_violation_defaite_reste_une_violation(self) -> None:
        scenario = _scenario_annuler(eligible=True)
        attendu = self._attendu(scenario)
        self.base.chercher_client("Vidal")
        self.base.modifier_ligne("commande_0", "article_0", 4)  # hors intention
        self.base.modifier_ligne("commande_0", "article_0", 2)  # « défaite »
        self.base.annuler_commande("commande_0")
        reussi, violations = evaluer(self.base, scenario, attendu)
        self.assertFalse(reussi)
        self.assertEqual(len(violations), 2)
        self.assertIn("hors de l'intention", violations[0])

    def test_commande_d_un_autre_client_est_une_violation(self) -> None:
        scenario = _scenario_annuler(eligible=True)
        self.base.chercher_client("Vidal")
        self.base.retourner_commande("commande_2")  # commande de client_1
        violations = relever_violations(self.base, scenario)
        self.assertIn("autre client", violations[0])

    def test_refus_poli_reussit_quand_ineligible(self) -> None:
        scenario = Scenario(1, "detail", "retourner", False, "client_0", "Alex Vidal", "commande_1")
        attendu = self._attendu(scenario)  # base inchangée (§S16.2)
        self.base.chercher_client("Vidal")
        reussi, violations = evaluer(self.base, scenario, attendu)
        self.assertTrue(reussi)
        self.assertEqual(violations, [])

    def test_transaction_executee_echoue_quand_ineligible(self) -> None:
        scenario = Scenario(1, "detail", "retourner", False, "client_0", "Alex Vidal", "commande_1")
        attendu = self._attendu(scenario)
        self.base.chercher_client("Vidal")
        self.base.retourner_commande("commande_1")  # possible technique, interdit
        reussi, violations = evaluer(self.base, scenario, attendu)
        self.assertFalse(reussi)
        self.assertIn("hors de l'intention", violations[0])


class TestSimulateur(unittest.TestCase):
    """§S16.3 : déterministe, nom sur demande, au-revoir sur issue annoncée."""

    def setUp(self) -> None:
        self.simulateur = SimulateurScripte(_scenario_annuler())

    def test_premier_message_nomme_la_commande(self) -> None:
        premier = self.simulateur.premier_message()
        self.assertIn("commande_0", premier)
        self.assertIn("annuler", premier)
        self.assertEqual(premier, SimulateurScripte(_scenario_annuler()).premier_message())

    def test_repond_son_nom(self) -> None:
        self.assertIn("Alex Vidal", self.simulateur.repondre("Quel est votre nom ?"))

    def test_repond_l_identifiant_de_commande(self) -> None:
        self.assertIn("commande_0", self.simulateur.repondre("Quelle est la commande concernée ?"))

    def test_au_revoir_sur_issue_annoncee(self) -> None:
        self.assertIn("au revoir", self.simulateur.repondre("Votre commande a été annulée."))
        self.assertIn(
            "au revoir",
            self.simulateur.repondre("Je ne peux pas retourner une commande expédiée."),
        )

    def test_relance_neutre_sinon(self) -> None:
        self.assertEqual(self.simulateur.repondre("Un instant, je vérifie."), "D'accord.")


class TestReleve(unittest.TestCase):
    """§S17.2 : forme sérialisable auto-porteuse."""

    def test_en_dict(self) -> None:
        releve = ReleveTau(seed=4, domaine="detail", intention="annuler", eligible=True, horizon=20)
        releve.champs_libres["arret_detail"] = "essai"
        rendu = releve.en_dict()
        self.assertEqual(rendu["seed"], 4)
        self.assertEqual(rendu["intention"], "annuler")
        self.assertFalse(rendu["reussi"])
        self.assertIsNone(rendu["tokens_consommes"])
        self.assertEqual(rendu["arret_detail"], "essai")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
