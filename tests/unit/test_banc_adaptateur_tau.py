"""Preuves unitaires de l'adaptateur du banc c et de son branchement CLI.

@verifies docs/BACKLOG.md U29c2 — adaptateur + branchement au dispatch CLI `banc`
@verifies docs/SPEC_BANCS.md §S18.1 (huit outils étiquetés `action`, paramètre
          `prediction` selon le mode), §S18.2 (contexte : politique intégrale,
          jamais l'intention), §S18.3 (schéma de Σ `service`), §S18.4 (refus
          nommés du dispatch ; l'utilisateur simulé choisi par le mode),
          §S16.3 (utilisateur `llm` : réponses par un second LLM, historique
          propre append-only, premier message scripté), §S16.4 (déroulé :
          budget, `clore()`, observation), §S9.3 par analogie et
          docs/SPEC_HARNAIS.md §H15.8 (`refusee` = refus technique seul)
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from avo.bancs import BancInconnu, ParametreBancInvalide, annoncer_releve, executer_banc
from avo.bancs.tau.adaptateur import (
    CONTEXTE_TACHE_TAU,
    MOTIF_BUDGET,
    MOTIF_CLOS,
    SCHEMA_SERVICE,
    EnvironnementBancTau,
    UtilisateurLlm,
)
from avo.bancs.tau.scenario import SimulateurScripte, generer_episode_tau
from avo.bancs.tau.score import ReleveTau
from avo.config import Mode, charger
from avo.context.etat import CHAINE
from avo.llm.client import LLMClient, ReponseHTTP

SEED = 7


def _environnement(horizon: int = 10) -> EnvironnementBancTau:
    base, scenario, _ = generer_episode_tau(SEED)
    releve = ReleveTau(
        seed=SEED,
        domaine="detail",
        intention=scenario.famille,
        eligible=scenario.eligible,
        horizon=horizon,
    )
    return EnvironnementBancTau(base, scenario, SimulateurScripte(scenario), horizon, releve)


class TestOutilsEtObservation(unittest.TestCase):
    """§S18.1, §S16.4 : outils, budget, clôture, composition de l'observation."""

    def setUp(self) -> None:
        self.env = _environnement()
        self.addCleanup(self.env.base.fermer)

    def test_huit_outils_etiquetes_action_avec_prediction(self) -> None:
        outils = self.env.outils()
        self.assertEqual(len(outils), 8)
        self.assertEqual([outil.nom for outil in outils], list(self.env.actions_disponibles()))
        for outil in outils:
            self.assertIn("action", outil.etiquettes)
            self.assertIn("prediction", outil.parametres["properties"])

    def test_prediction_requise_en_transcript_seulement(self) -> None:
        requise = _environnement()
        self.addCleanup(requise.base.fermer)
        self.assertIn("prediction", requise.outils()[0].parametres["required"])
        base, scenario, _ = generer_episode_tau(SEED)
        self.addCleanup(base.fermer)
        libre = EnvironnementBancTau(
            base,
            scenario,
            SimulateurScripte(scenario),
            10,
            ReleveTau(SEED, "detail", scenario.famille, scenario.eligible, 10),
            avec_prediction=True,
            prediction_requise=False,
        )
        self.assertNotIn("prediction", libre.outils()[0].parametres.get("required", []))

    def test_observation_premier_tour_porte_le_premier_message(self) -> None:
        observation = self.env.observation()
        self.assertIn("Dernier message de l'utilisateur", observation)
        self.assertIn(self.env.scenario.commande_id, observation)

    def test_observation_apres_action_prefixe_l_issue(self) -> None:
        self.env._lire_commande(self.env.scenario.commande_id)  # noqa: SLF001 — l'unité testée
        observation = self.env.observation()
        self.assertIn("Issue de ta dernière action", observation)
        self.assertIn("Dernier message de l'utilisateur", observation)

    def test_refus_technique_porte_refusee(self) -> None:
        self.env._annuler_commande("commande_absente")  # noqa: SLF001
        issue = self.env.derniere_issue()
        assert issue is not None
        self.assertTrue(issue.refusee)

    def test_execution_contraire_a_la_politique_n_est_pas_refusee(self) -> None:
        cible = next(commande for commande, _ in self.env.base.commandes_par_statut(("expediee",)))
        self.env._retourner_commande(cible)  # noqa: SLF001 — possible technique
        issue = self.env.derniere_issue()
        assert issue is not None
        self.assertFalse(issue.refusee)

    def test_repondre_compte_la_replique_et_rend_la_reponse(self) -> None:
        self.env._repondre("Quel est votre nom ?")  # noqa: SLF001
        self.assertEqual(self.env.releve.repliques, 1)
        issue = self.env.derniere_issue()
        assert issue is not None
        self.assertIn(self.env.scenario.client_nom, issue.observation)
        self.assertIn(self.env.scenario.client_nom, self.env.observation())

    def test_clore_et_budget_terminent(self) -> None:
        self.assertIsNone(self.env.etat_terminal())
        self.env._clore()  # noqa: SLF001
        self.assertEqual(self.env.etat_terminal(), MOTIF_CLOS)
        court = _environnement(horizon=1)
        self.addCleanup(court.base.fermer)
        court._repondre("Bonjour.")  # noqa: SLF001
        self.assertEqual(court.etat_terminal(), MOTIF_BUDGET)


class TestContexteEtSchema(unittest.TestCase):
    """§S18.2, §S18.3 : la politique intégrale, jamais l'intention ; le schéma."""

    def test_le_contexte_porte_la_politique_entiere(self) -> None:
        for attendu in (
            "Identification",
            "en_attente",
            "livree",
            "Une seule affaire",
            "repondre",
            "clore",
        ):
            self.assertIn(attendu, CONTEXTE_TACHE_TAU)

    def test_le_contexte_ne_nomme_aucune_intention_tiree(self) -> None:
        _, scenario, _ = generer_episode_tau(SEED)
        self.assertNotIn(scenario.commande_id, CONTEXTE_TACHE_TAU)
        self.assertNotIn(scenario.client_nom, CONTEXTE_TACHE_TAU)

    def test_schema_service(self) -> None:
        self.assertEqual(SCHEMA_SERVICE.nom, "service")
        self.assertEqual(
            SCHEMA_SERVICE.noms,
            ("hypotheses", "client_identifie", "demande", "faits", "reste_a_faire"),
        )
        champ = SCHEMA_SERVICE.champ("client_identifie")
        assert champ is not None
        self.assertEqual(champ.genre, CHAINE)


class TestUtilisateurLlm(unittest.TestCase):
    """§S16.3 : premier message scripté, réponses par le second LLM, fil propre."""

    def _client(self, contenus: list[str]) -> LLMClient:
        config = charger(
            Mode.REJEU,
            env={"OLLAMA_HOST": "http://simulateur.invalide", "OLLAMA_API_KEY": "sk-x"},
            racine=Path("/inexistant"),
        )
        reponses = iter(contenus)

        def transport(url: str, corps: bytes, entetes: object, timeout: float) -> ReponseHTTP:
            del url, entetes, timeout
            charge = json.loads(corps)
            self.assertIsNone(charge.get("tools"))
            corps_reponse = {
                "model": "essai",
                "message": {"role": "assistant", "content": next(reponses)},
                "done": True,
                "prompt_eval_count": 1,
                "eval_count": 1,
            }
            return ReponseHTTP(200, json.dumps(corps_reponse).encode())

        return LLMClient(config, transport=transport, dormir=lambda _: None)

    def test_premier_message_scripte_et_reponses_llm(self) -> None:
        _, scenario, _ = generer_episode_tau(SEED)
        utilisateur = UtilisateurLlm(scenario, self._client(["Je m'appelle X.", "Au revoir."]))
        premier = utilisateur.premier_message()
        self.assertEqual(premier, SimulateurScripte(scenario).premier_message())
        self.assertEqual(utilisateur.repondre("Votre nom ?"), "Je m'appelle X.")
        self.assertEqual(utilisateur.repondre("Merci."), "Au revoir.")

    def test_le_prompt_d_utilisateur_ne_revele_pas_l_attendu(self) -> None:
        _, scenario, _ = generer_episode_tau(SEED)
        utilisateur = UtilisateurLlm(scenario, self._client([]))
        systeme = utilisateur._messages[0]["content"]  # noqa: SLF001 — l'unité testée
        self.assertIn(scenario.client_nom, systeme)
        self.assertNotIn("état attendu", systeme)
        self.assertIn("Ne révèle JAMAIS", systeme)


class TestDispatch(unittest.TestCase):
    """§S18.4 : refus nommés avant tout montage ; annonce du relevé."""

    def test_domaine_inconnu(self) -> None:
        with self.assertRaises(BancInconnu) as arret:
            executer_banc("tau", "grossiste", seed=1, horizon=5)
        self.assertIn("detail", str(arret.exception))

    def test_bruit_refuse(self) -> None:
        with self.assertRaises(ParametreBancInvalide) as arret:
            executer_banc("tau", "detail", seed=1, horizon=5, bruit=5)
        self.assertIn("--bruit", str(arret.exception))

    def test_derive_refusee(self) -> None:
        with self.assertRaises(ParametreBancInvalide) as arret:
            executer_banc("tau", "detail", seed=1, horizon=5, derive=True)
        self.assertIn("--derive", str(arret.exception))

    def test_executeur_refuse(self) -> None:
        with self.assertRaises(ParametreBancInvalide) as arret:
            executer_banc("tau", "detail", seed=1, horizon=5, executeur="conteneur")
        self.assertIn("--executeur", str(arret.exception))

    def test_annonce_du_releve(self) -> None:
        releve = ReleveTau(seed=3, domaine="detail", intention="annuler", eligible=True, horizon=20)
        releve.reussi = True
        releve.arret = MOTIF_CLOS
        releve.actions = 6
        releve.repliques = 2
        releve.transactions = 1
        lignes = annoncer_releve(releve)
        self.assertEqual(len(lignes), 1)
        self.assertIn("intention annuler (éligible)", lignes[0])
        self.assertIn("réussi", lignes[0])
        self.assertIn("clos par l'agent", lignes[0])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
