"""Preuves du banc b : générateur des familles, matérialisation, terminal, relevé.

@verifies docs/BACKLOG.md U29b1 — générateur, terminal, relevé du banc b
@verifies docs/SPEC_BANCS.md §S9.1 (plan pur, déterminisme octet pour octet,
          famille premier tirage en `aleatoire`), §S9.2 (solvabilité de chaque
          famille par son chemin canonique, unicité du drapeau, leurres jamais
          en `FLAG{`), §S9.3 (capture, budget, soumission incorrecte qui
          continue, `refusee` selon le refus de forme seul), §S10.2 (exécution
          réelle, persistance fichiers sans persistance shell, troncature et
          délai nommés, refus de forme), §S11.1 (score binaire),
          §S11.2 (champs du relevé)
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from avo.bancs.ctf.defis import (
    ALEATOIRE,
    FAMILLES,
    GABARIT_INDICE,
    FamilleInconnue,
    PlanDefi,
    desarchiver,
    generer_defi,
    inverser_transformation,
    materialiser,
)
from avo.bancs.ctf.score import ReleveCtf
from avo.bancs.ctf.terminal import (
    MOTIF_BUDGET,
    MOTIF_CAPTURE,
    EnvironnementTerminal,
    EpisodeTermine,
    ExecuteurProcessus,
)

SEEDS = (1, 2, 3, 7, 42)


def _contenu(plan: PlanDefi, chemin: str) -> bytes:
    """Le contenu d'un fichier du plan, par son chemin."""
    for fichier in plan.fichiers:
        if fichier.chemin == chemin:
            return fichier.contenu
    raise AssertionError(f"chemin absent du plan : {chemin}")


class TestGenerateur(unittest.TestCase):
    """§S9.1 : plan pur, déterministe, famille tirée au seed en `aleatoire`."""

    def test_deterministe_a_seed_egal(self) -> None:
        for famille in FAMILLES + (ALEATOIRE,):
            for seed in SEEDS:
                self.assertEqual(
                    generer_defi(seed, famille),
                    generer_defi(seed, famille),
                    f"plan non déterministe : famille={famille} seed={seed}",
                )

    def test_famille_aleatoire_tiree_au_seed(self) -> None:
        familles_vues = {generer_defi(seed).famille for seed in range(20)}
        self.assertLessEqual(familles_vues, set(FAMILLES))
        self.assertGreater(len(familles_vues), 1, "le tirage n'explore pas les familles")

    def test_famille_inconnue_refusee_nommee(self) -> None:
        with self.assertRaises(FamilleInconnue) as refus:
            generer_defi(1, "inexistante")
        self.assertIn("inexistante", str(refus.exception))
        self.assertIn("fouille", str(refus.exception))

    def test_drapeau_au_format(self) -> None:
        for seed in SEEDS:
            plan = generer_defi(seed)
            self.assertRegex(plan.drapeau, r"^FLAG\{[0-9a-f]{16}\}$")

    def test_materialisation_relue_identique(self) -> None:
        plan = generer_defi(3, "fouille")
        with TemporaryDirectory() as temporaire:
            racine = Path(temporaire)
            materialiser(plan, racine)
            for fichier in plan.fichiers:
                self.assertEqual((racine / fichier.chemin).read_bytes(), fichier.contenu)


class TestSolvabilite(unittest.TestCase):
    """§S9.2 : chaque famille se recouvre par son chemin canonique, drapeau unique."""

    def test_fouille_drapeau_en_clair_et_unique(self) -> None:
        for seed in SEEDS:
            plan = generer_defi(seed, "fouille")
            occurrences = sum(
                fichier.contenu.count(plan.drapeau.encode()) for fichier in plan.fichiers
            )
            self.assertEqual(occurrences, 1)
            self.assertIn(plan.drapeau.encode(), _contenu(plan, plan.chemin_drapeau))

    def test_fouille_leurres_jamais_flag(self) -> None:
        for seed in SEEDS:
            plan = generer_defi(seed, "fouille")
            occurrences_prefixe = sum(fichier.contenu.count(b"FLAG{") for fichier in plan.fichiers)
            self.assertEqual(occurrences_prefixe, 1, "un leurre porte le préfixe du drapeau")

    def test_encodage_composition_inversible(self) -> None:
        for seed in SEEDS:
            plan = generer_defi(seed, "encodage")
            self.assertTrue(1 <= len(plan.transformations) <= 3)
            texte = _contenu(plan, plan.chemin_drapeau).decode().strip()
            for transformation in reversed(plan.transformations):
                texte = inverser_transformation(transformation, texte)
            self.assertEqual(texte, plan.drapeau)

    def test_archive_couches_inversibles(self) -> None:
        for seed in SEEDS:
            plan = generer_defi(seed, "archive")
            self.assertTrue(2 <= len(plan.transformations) <= 4)
            donnees = _contenu(plan, plan.chemin_drapeau)
            for couche in reversed(plan.transformations):
                donnees = desarchiver(couche, donnees)
            self.assertIn(plan.drapeau.encode(), donnees)

    def test_binaire_drapeau_extractible(self) -> None:
        for seed in SEEDS:
            plan = generer_defi(seed, "binaire")
            blob = _contenu(plan, plan.chemin_drapeau)
            self.assertEqual(blob.count(plan.drapeau.encode()), 1)

    def test_piste_suivie_de_la_racine_au_drapeau(self) -> None:
        for seed in SEEDS:
            plan = generer_defi(seed, "piste")
            self.assertNotIn("/", plan.etapes[0], "la piste doit s'ouvrir à la racine")
            for position, chemin in enumerate(plan.etapes[:-1]):
                indice = GABARIT_INDICE + plan.etapes[position + 1]
                self.assertIn(indice.encode(), _contenu(plan, chemin))
            self.assertIn(plan.drapeau.encode(), _contenu(plan, plan.etapes[-1]))
            self.assertEqual(plan.chemin_drapeau, plan.etapes[-1])


class TestExecuteurProcessus(unittest.TestCase):
    """§S10.2 : exécution réelle, persistance fichiers, troncature, délai, refus."""

    def _environnement(
        self, seed: int = 1, famille: str = "fouille", horizon: int = 30, delai_s: float = 10.0
    ) -> EnvironnementTerminal:
        plan = generer_defi(seed, famille)
        environnement = EnvironnementTerminal(
            plan, horizon=horizon, executeur=ExecuteurProcessus(delai_s=delai_s)
        )
        self.addCleanup(environnement.fermer)
        return environnement

    def test_premiere_observation_et_actions(self) -> None:
        environnement = self._environnement()
        self.assertIn("Terminal prêt", environnement.observation())
        self.assertEqual(environnement.actions_disponibles(), ("bash", "soumettre"))
        self.assertIsNone(environnement.derniere_issue())

    def test_commande_reelle_et_code_de_retour(self) -> None:
        environnement = self._environnement()
        issue = environnement.commande("echo bonjour")
        self.assertIn("bonjour", issue.observation)
        self.assertIn("[code de retour : 0]", issue.observation)
        self.assertFalse(issue.refusee)
        self.assertEqual(environnement.observation(), issue.observation)

    def test_recherche_recursive_trouve_le_drapeau(self) -> None:
        environnement = self._environnement(seed=2, famille="fouille")
        issue = environnement.commande("grep -r 'FLAG{' .")
        self.assertIn("FLAG{", issue.observation)

    def test_code_de_retour_non_nul_est_une_information(self) -> None:
        environnement = self._environnement()
        issue = environnement.commande("false")
        self.assertIn("[code de retour : 1]", issue.observation)
        self.assertFalse(issue.refusee, "un échec exécuté n'est pas un refus (§S9.3)")

    def test_persistance_fichiers_sans_persistance_shell(self) -> None:
        environnement = self._environnement()
        environnement.commande("mkdir -p atelier && echo trace > atelier/note.txt")
        relecture = environnement.commande("cat atelier/note.txt")
        self.assertIn("trace", relecture.observation)
        environnement.commande("cd atelier")
        ou_suis_je = environnement.commande("pwd")
        self.assertNotIn("atelier", ou_suis_je.observation, "le shell ne doit pas persister")

    def test_troncature_nommee(self) -> None:
        environnement = self._environnement()
        issue = environnement.commande("head -c 9000 /dev/zero | tr '\\0' 'x'")
        self.assertIn("sortie tronquée", issue.observation)
        self.assertIn("9000 octets au total", issue.observation)
        self.assertIn("4096 affichés", issue.observation)

    def test_delai_nomme(self) -> None:
        environnement = self._environnement(delai_s=1.0)
        issue = environnement.commande("sleep 5")
        self.assertIn("délai de 1 s dépassé", issue.observation)
        self.assertFalse(issue.refusee)

    def test_refus_de_forme_commande_vide(self) -> None:
        environnement = self._environnement()
        issue = environnement.commande("   ")
        self.assertTrue(issue.refusee)
        self.assertIn("Commande vide refusée", issue.observation)
        self.assertEqual(environnement.releve.refus_forme, 1)
        self.assertEqual(environnement.releve.actions, 1, "le refus consomme le budget (§S10.2)")


class TestEpisode(unittest.TestCase):
    """§S9.3 et §S11 : capture, budget, soumission incorrecte, relevé."""

    def _environnement(self, horizon: int = 5) -> EnvironnementTerminal:
        plan = generer_defi(1, "fouille")
        environnement = EnvironnementTerminal(plan, horizon=horizon, executeur=ExecuteurProcessus())
        self.addCleanup(environnement.fermer)
        return environnement

    def test_capture_clot_l_episode(self) -> None:
        environnement = self._environnement()
        drapeau = generer_defi(1, "fouille").drapeau
        issue = environnement.soumettre(drapeau)
        self.assertIn("Drapeau accepté", issue.observation)
        self.assertEqual(environnement.etat_terminal(), MOTIF_CAPTURE)
        releve = environnement.completer_releve()
        self.assertTrue(releve.reussi)
        self.assertEqual(releve.arret, MOTIF_CAPTURE)

    def test_soumission_incorrecte_continue(self) -> None:
        environnement = self._environnement()
        issue = environnement.soumettre("FLAG{0000000000000000}")
        self.assertIn("Drapeau incorrect", issue.observation)
        self.assertFalse(issue.refusee, "une soumission incorrecte est une information (§S9.3)")
        self.assertIsNone(environnement.etat_terminal())
        self.assertEqual(environnement.releve.soumissions_incorrectes, 1)

    def test_budget_epuise_et_garde_apres_terminal(self) -> None:
        environnement = self._environnement(horizon=2)
        environnement.commande("true")
        environnement.commande("true")
        self.assertEqual(environnement.etat_terminal(), MOTIF_BUDGET)
        self.assertEqual(environnement.observation(), MOTIF_BUDGET)
        with self.assertRaises(EpisodeTermine):
            environnement.commande("true")
        releve = environnement.completer_releve()
        self.assertFalse(releve.reussi)
        self.assertEqual(releve.arret, MOTIF_BUDGET)

    def test_capture_au_dernier_souffle_prime_le_budget(self) -> None:
        environnement = self._environnement(horizon=1)
        environnement.soumettre(generer_defi(1, "fouille").drapeau)
        self.assertEqual(environnement.etat_terminal(), MOTIF_CAPTURE)

    def test_releve_serialise_ses_champs(self) -> None:
        releve = ReleveCtf(seed=4, famille="piste", horizon=30)
        releve.actions = 3
        releve.commandes = 2
        releve.soumissions = 1
        releve.soumissions_incorrectes = 1
        releve.arret = MOTIF_BUDGET
        releve.champs_libres["schema_etat"] = "ctf"
        forme = releve.en_dict()
        self.assertEqual(forme["seed"], 4)
        self.assertEqual(forme["famille"], "piste")
        self.assertFalse(forme["reussi"])
        self.assertEqual(forme["actions"], 3)
        self.assertEqual(forme["commandes"], 2)
        self.assertEqual(forme["soumissions_incorrectes"], 1)
        self.assertEqual(forme["arret"], MOTIF_BUDGET)
        self.assertEqual(forme["schema_etat"], "ctf")
        self.assertIsNone(forme["tokens_consommes"])


if __name__ == "__main__":
    unittest.main()
