"""Preuves unitaires de l'adaptateur du banc b et de son branchement CLI.

@verifies docs/BACKLOG.md U29b2 — adaptateur + branchement au dispatch CLI `banc`
@verifies docs/SPEC_BANCS.md §S12.1 (outils `bash` et `soumettre`, étiquette
          `action`, paramètre `prediction`), §S12.2 (contexte de tâche : le
          cadre, jamais la famille ni la méthode — §S8.4), §S12.3 (schéma de Σ
          `ctf`), §S12.4 (dispatch : `--env` porte la famille, `--bruit` et
          `--derive` refusés, `--executeur` paramètre d'infrastructure),
          §S10.1 (énoncé sans chemin d'hôte), §S10.3 (`processus` refusé en
          mode live ; exécuteur inconnu nommé), §S9.3 (`refusee` réservé aux
          refus de forme)
@verifies docs/SPEC_HARNAIS.md §H15.8 (drapeau `refusee` de l'issue), §H16.2
          (paramètre `prediction` selon le mode de contexte)
"""

from __future__ import annotations

import unittest

from avo.bancs import BancInconnu, ParametreBancInvalide, executer_banc
from avo.bancs.ctf.adaptateur import (
    CONTEXTE_TACHE_CTF,
    SCHEMA_CTF,
    EnvironnementBancCtf,
    construire_executeur,
)
from avo.bancs.ctf.defis import FAMILLES, generer_defi
from avo.bancs.ctf.terminal import MOTIF_CAPTURE, EnvironnementTerminal, ExecuteurProcessus
from avo.context.etat import CHAINE, LISTE_CHAINES


def _environnement(seed: int = 1, horizon: int = 6) -> EnvironnementBancCtf:
    plan = generer_defi(seed, "fouille")
    moteur = EnvironnementTerminal(plan, horizon, ExecuteurProcessus())
    return EnvironnementBancCtf(moteur)


class TestOutils(unittest.TestCase):
    """§S12.1 : deux outils d'action, prédiction selon le mode (§H16.2)."""

    def test_deux_outils_etiquetes_action(self) -> None:
        env = _environnement()
        self.addCleanup(env.moteur.fermer)
        outils = env.outils()
        self.assertEqual([outil.nom for outil in outils], ["bash", "soumettre"])
        for outil in outils:
            self.assertIn("action", outil.etiquettes)
            self.assertIn("prediction", outil.parametres["properties"])

    def test_prediction_requise_en_transcript_seulement(self) -> None:
        plan = generer_defi(1, "fouille")
        moteur = EnvironnementTerminal(plan, 3, ExecuteurProcessus())
        self.addCleanup(moteur.fermer)
        requise = EnvironnementBancCtf(moteur, avec_prediction=True, prediction_requise=True)
        self.assertIn("prediction", requise.outils()[0].parametres["required"])
        libre = EnvironnementBancCtf(moteur, avec_prediction=True, prediction_requise=False)
        self.assertNotIn("prediction", libre.outils()[0].parametres["required"])

    def test_actions_disponibles(self) -> None:
        env = _environnement()
        self.addCleanup(env.moteur.fermer)
        self.assertEqual(env.actions_disponibles(), ("bash", "soumettre"))


class TestIssueEtObservation(unittest.TestCase):
    """§S9.3, §S10.1 : `refusee` réservé aux refus de forme, énoncé sans chemin."""

    def test_enonce_sans_chemin_d_hote(self) -> None:
        env = _environnement()
        self.addCleanup(env.moteur.fermer)
        enonce = env.observation()
        self.assertIn("racine du défi", enonce)
        self.assertNotIn("/", enonce)

    def test_commande_reelle_non_refusee(self) -> None:
        env = _environnement()
        self.addCleanup(env.moteur.fermer)
        env._bash("echo bonjour", prediction=None)  # noqa: SLF001 — l'unité testée
        issue = env.derniere_issue()
        assert issue is not None
        self.assertFalse(issue.refusee)
        self.assertIn("$ echo bonjour", issue.observation)
        self.assertIn("code de retour : 0", issue.observation)

    def test_code_de_retour_non_nul_reste_une_information(self) -> None:
        env = _environnement()
        self.addCleanup(env.moteur.fermer)
        env._bash("false", prediction=None)  # noqa: SLF001
        issue = env.derniere_issue()
        assert issue is not None
        self.assertFalse(issue.refusee)

    def test_refus_de_forme_porte_refusee(self) -> None:
        env = _environnement()
        self.addCleanup(env.moteur.fermer)
        env._bash("   ", prediction=None)  # noqa: SLF001
        issue = env.derniere_issue()
        assert issue is not None
        self.assertTrue(issue.refusee)

    def test_soumission_incorrecte_continue_sans_refus(self) -> None:
        env = _environnement()
        self.addCleanup(env.moteur.fermer)
        env._soumettre("FLAG{faux}", prediction=None)  # noqa: SLF001
        issue = env.derniere_issue()
        assert issue is not None
        self.assertFalse(issue.refusee)
        self.assertIn("incorrect", issue.observation)
        self.assertIsNone(env.etat_terminal())

    def test_capture_termine_l_episode(self) -> None:
        plan = generer_defi(3, "fouille")
        moteur = EnvironnementTerminal(plan, 6, ExecuteurProcessus())
        self.addCleanup(moteur.fermer)
        env = EnvironnementBancCtf(moteur)
        env._soumettre(plan.drapeau, prediction=None)  # noqa: SLF001
        self.assertEqual(env.etat_terminal(), MOTIF_CAPTURE)


class TestContexteEtSchema(unittest.TestCase):
    """§S12.2, §S12.3, §S8.4 : le cadre sans la méthode, le schéma transposé."""

    def test_le_contexte_ne_nomme_aucune_famille(self) -> None:
        for famille in FAMILLES:
            self.assertNotIn(famille, CONTEXTE_TACHE_CTF.lower())

    def test_le_contexte_enonce_le_cadre(self) -> None:
        for attendu in ("FLAG{", "bash", "soumettre", "shell neuf", "budget"):
            self.assertIn(attendu, CONTEXTE_TACHE_CTF)

    def test_schema_ctf(self) -> None:
        self.assertEqual(SCHEMA_CTF.nom, "ctf")
        self.assertEqual(
            SCHEMA_CTF.noms,
            (
                "hypotheses",
                "drapeaux_testes",
                "fichiers_actifs",
                "repertoire_travail",
                "resume_commandes",
            ),
        )
        champ = SCHEMA_CTF.champ("repertoire_travail")
        assert champ is not None
        self.assertEqual(champ.genre, CHAINE)
        champ = SCHEMA_CTF.champ("resume_commandes")
        assert champ is not None
        self.assertEqual(champ.genre, LISTE_CHAINES)


class TestDispatch(unittest.TestCase):
    """§S12.4 : chaque refus est nommé et tombe AVANT tout montage."""

    def test_banc_inconnu(self) -> None:
        with self.assertRaises(BancInconnu) as arret:
            executer_banc("tau", "retail", seed=1, horizon=3)
        self.assertIn("skillexec, ctf", str(arret.exception))

    def test_famille_inconnue(self) -> None:
        with self.assertRaises(BancInconnu) as arret:
            executer_banc("ctf", "poterie", seed=1, horizon=3)
        self.assertIn("aleatoire", str(arret.exception))

    def test_bruit_refuse(self) -> None:
        with self.assertRaises(ParametreBancInvalide) as arret:
            executer_banc("ctf", "fouille", seed=1, horizon=3, bruit=5)
        self.assertIn("--bruit", str(arret.exception))

    def test_derive_refusee(self) -> None:
        with self.assertRaises(ParametreBancInvalide) as arret:
            executer_banc("ctf", "fouille", seed=1, horizon=3, derive=True)
        self.assertIn("--derive", str(arret.exception))

    def test_executeur_inconnu_refuse(self) -> None:
        with self.assertRaises(ParametreBancInvalide) as arret:
            executer_banc("ctf", "fouille", seed=1, horizon=3, executeur="hyperviseur")
        self.assertIn("hyperviseur", str(arret.exception))

    def test_processus_refuse_en_live(self) -> None:
        with self.assertRaises(ParametreBancInvalide) as arret:
            executer_banc("ctf", "fouille", seed=1, horizon=3, mode="live", executeur="processus")
        self.assertIn("live", str(arret.exception))

    def test_executeur_sans_objet_pour_skillexec(self) -> None:
        with self.assertRaises(ParametreBancInvalide) as arret:
            executer_banc("skillexec", "entrepot", seed=1, horizon=3, executeur="conteneur")
        self.assertIn("sans objet", str(arret.exception))

    def test_constructeur_d_executeur_nomme_l_inconnu(self) -> None:
        with self.assertRaises(ValueError) as arret:
            construire_executeur("machine-a-cafe")
        self.assertIn("machine-a-cafe", str(arret.exception))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
