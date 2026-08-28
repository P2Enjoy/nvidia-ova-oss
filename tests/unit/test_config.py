"""Preuves de la configuration : sources, validation, budgets, secrets.

@verifies docs/BACKLOG.md U6 — Configuration `avo.config`
@verifies docs/SPEC_HARNAIS.md §H3.1 (env puis .env), §H3.2 (budget utile),
          §H3.3 (validation nommée), §H3.4 (modes), §H4.6 (aucun secret journalisé)
"""

from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

from avo.config import (
    ARC_REJEU,
    CONTEXTE_DEFAUT_REJEU,
    HOTE_REJEU,
    JETON_REJEU,
    MARGE_PROXY,
    NUM_PREDICT_MIN_AVEC_THINK,
    Config,
    ConfigInvalide,
    Mode,
    charger,
    lire_fichier_env,
)

_LIVE_MINIMAL = {
    "OLLAMA_HOST": "https://exemple.test:1234",
    "OLLAMA_API_KEY": "sk-secret-de-test",
    "OLLAMA_CONTEXT_LENGTH": "224000",
    "ARC_API_KEY": "00000000-0000-0000-0000-000000000000",
}


class TestFichierEnv(unittest.TestCase):
    def _ecrire(self, contenu: str) -> Path:
        dossier = tempfile.mkdtemp()
        chemin = Path(dossier) / ".env"
        chemin.write_text(contenu, encoding="utf-8")
        return chemin

    def test_lit_les_paires_ignore_commentaires_et_lignes_vides(self) -> None:
        chemin = self._ecrire("# commentaire\n\nA=1\n  B = deux  \n")
        self.assertEqual(lire_fichier_env(chemin), {"A": "1", "B": "deux"})

    def test_retire_les_guillemets_encadrants(self) -> None:
        chemin = self._ecrire("A=\"avec espaces\"\nB='simple'\n")
        self.assertEqual(lire_fichier_env(chemin), {"A": "avec espaces", "B": "simple"})

    def test_tolere_le_prefixe_export(self) -> None:
        chemin = self._ecrire("export A=1\n")
        self.assertEqual(lire_fichier_env(chemin), {"A": "1"})

    def test_ligne_ininterpretable_est_une_erreur_nommee(self) -> None:
        chemin = self._ecrire("A=1\nligne sans egal\n")
        with self.assertRaises(ConfigInvalide) as capture:
            lire_fichier_env(chemin)
        self.assertIn("ligne 2", str(capture.exception))

    def test_fichier_absent_donne_un_dictionnaire_vide(self) -> None:
        self.assertEqual(lire_fichier_env(Path("/inexistant/.env")), {})


class TestModeRejeu(unittest.TestCase):
    """En rejeu, aucun secret n'est requis (§H3.4)."""

    def test_sans_aucune_variable_la_configuration_pointe_la_pile_locale(self) -> None:
        config = charger(Mode.REJEU, env={}, racine=Path("/inexistant"))
        self.assertEqual(config.ollama_host, HOTE_REJEU)
        self.assertEqual(config.ollama_api_key, JETON_REJEU)
        self.assertEqual(config.contexte_demande, CONTEXTE_DEFAUT_REJEU)
        self.assertIsNone(config.arc_api_key)

    def test_les_defauts_documentes_sont_appliques(self) -> None:
        config = charger(Mode.REJEU, env={}, racine=Path("/inexistant"))
        self.assertEqual(config.modele, "qwen3.6:35b")
        self.assertFalse(config.think)
        self.assertEqual(config.num_predict, 4096)
        self.assertEqual(config.temperature, 0.7)
        self.assertEqual(config.timeout_s, 900)
        self.assertEqual(config.ratio_continuation, 0.85)
        self.assertEqual(config.runs_dir, Path("runs"))
        # En rejeu, la base ARC pointe la pile locale : le mode ne doit atteindre
        # aucun service qui publierait un scorecard (§H3.4, §A2.3).
        self.assertEqual(config.arc_base_url, ARC_REJEU)


class TestModeLive(unittest.TestCase):
    """En live, un secret manquant est une erreur nommée (§H3.3)."""

    def test_la_base_arc_officielle_est_le_defaut_en_live(self) -> None:
        config = charger(Mode.LIVE, env=_LIVE_MINIMAL, racine=Path("/inexistant"))
        self.assertEqual(config.arc_base_url, "https://three.arcprize.org")

    def test_configuration_live_complete(self) -> None:
        config = charger(Mode.LIVE, env=_LIVE_MINIMAL, racine=Path("/inexistant"))
        self.assertEqual(config.mode, Mode.LIVE)
        self.assertEqual(config.ollama_host, "https://exemple.test:1234")
        self.assertEqual(config.contexte_demande, 224000)

    def test_chaque_variable_requise_manquante_est_nommee(self) -> None:
        for manquante in ("OLLAMA_HOST", "OLLAMA_API_KEY", "OLLAMA_CONTEXT_LENGTH", "ARC_API_KEY"):
            with self.subTest(variable=manquante):
                env = {k: v for k, v in _LIVE_MINIMAL.items() if k != manquante}
                with self.assertRaises(ConfigInvalide) as capture:
                    charger(Mode.LIVE, env=env, racine=Path("/inexistant"))
                self.assertIn(manquante, str(capture.exception))

    def test_aucun_secret_par_defaut_en_live(self) -> None:
        """Le jeton de rejeu ne doit JAMAIS servir de valeur par défaut en live."""
        env = {k: v for k, v in _LIVE_MINIMAL.items() if k != "OLLAMA_API_KEY"}
        with self.assertRaises(ConfigInvalide):
            charger(Mode.LIVE, env=env, racine=Path("/inexistant"))


class TestPrecedenceDesSources(unittest.TestCase):
    def test_l_environnement_prime_sur_le_fichier(self) -> None:
        dossier = tempfile.mkdtemp()
        (Path(dossier) / ".env").write_text("AVO_MODEL=depuis-fichier\n", encoding="utf-8")
        config = charger(Mode.REJEU, env={"AVO_MODEL": "depuis-env"}, racine=Path(dossier))
        self.assertEqual(config.modele, "depuis-env")

    def test_le_fichier_sert_de_repli(self) -> None:
        dossier = tempfile.mkdtemp()
        (Path(dossier) / ".env").write_text("AVO_MODEL=depuis-fichier\n", encoding="utf-8")
        config = charger(Mode.REJEU, env={}, racine=Path(dossier))
        self.assertEqual(config.modele, "depuis-fichier")


class TestValidation(unittest.TestCase):
    def _charger(self, **surcharges: str) -> Config:
        return charger(Mode.REJEU, env=surcharges, racine=Path("/inexistant"))

    def test_entier_invalide_nomme_la_variable(self) -> None:
        with self.assertRaises(ConfigInvalide) as capture:
            self._charger(AVO_NUM_PREDICT="beaucoup")
        self.assertIn("AVO_NUM_PREDICT", str(capture.exception))

    def test_entier_negatif_refuse(self) -> None:
        with self.assertRaises(ConfigInvalide) as capture:
            self._charger(AVO_TIMEOUT_S="-1")
        self.assertIn("AVO_TIMEOUT_S", str(capture.exception))

    def test_booleen_invalide_nomme_la_variable(self) -> None:
        with self.assertRaises(ConfigInvalide) as capture:
            self._charger(AVO_THINK="peut-etre")
        self.assertIn("AVO_THINK", str(capture.exception))

    def test_booleen_accepte_les_formes_usuelles(self) -> None:
        # Activer le raisonnement impose un budget de sortie plancher (§H12.1) :
        # les formes vraies sont donc éprouvées avec un budget conforme.
        budget = str(NUM_PREDICT_MIN_AVEC_THINK)
        for valeur in ("true", "1", "oui", "ON"):
            self.assertTrue(self._charger(AVO_THINK=valeur, AVO_NUM_PREDICT=budget).think, valeur)
        for valeur in ("false", "0", "non", "OFF"):
            self.assertFalse(self._charger(AVO_THINK=valeur).think, valeur)

    def test_url_sans_schema_refusee(self) -> None:
        with self.assertRaises(ConfigInvalide) as capture:
            self._charger(OLLAMA_HOST="exemple.test:1234")
        self.assertIn("OLLAMA_HOST", str(capture.exception))

    def test_url_sans_hote_refusee(self) -> None:
        with self.assertRaises(ConfigInvalide):
            self._charger(OLLAMA_HOST="https:///chemin")

    def test_slash_final_retire(self) -> None:
        self.assertEqual(self._charger(OLLAMA_HOST="https://x.test/").ollama_host, "https://x.test")

    def test_ratio_hors_bornes_refuse(self) -> None:
        with self.assertRaises(ConfigInvalide) as capture:
            self._charger(AVO_CONTEXT_SOFT_RATIO="1.5")
        self.assertIn("AVO_CONTEXT_SOFT_RATIO", str(capture.exception))


class TestPlancherDeSortieAvecRaisonnement(unittest.TestCase):
    """§H12.1 : le raisonnement natif consomme le budget de sortie avant le contenu."""

    def test_think_actif_avec_budget_court_est_refuse(self) -> None:
        with self.assertRaises(ConfigInvalide) as capture:
            charger(
                Mode.REJEU,
                env={"AVO_THINK": "true", "AVO_NUM_PREDICT": "64"},
                racine=Path("/inexistant"),
            )
        message = str(capture.exception)
        self.assertIn("AVO_NUM_PREDICT", message)
        self.assertIn(str(NUM_PREDICT_MIN_AVEC_THINK), message)

    def test_think_actif_avec_budget_suffisant_accepte(self) -> None:
        config = charger(
            Mode.REJEU,
            env={"AVO_THINK": "true", "AVO_NUM_PREDICT": str(NUM_PREDICT_MIN_AVEC_THINK)},
            racine=Path("/inexistant"),
        )
        self.assertTrue(config.think)
        self.assertEqual(config.num_predict, NUM_PREDICT_MIN_AVEC_THINK)

    def test_le_plancher_ne_s_applique_pas_sans_raisonnement(self) -> None:
        config = charger(Mode.REJEU, env={"AVO_NUM_PREDICT": "64"}, racine=Path("/inexistant"))
        self.assertFalse(config.think)
        self.assertEqual(config.num_predict, 64)


class TestBudget(unittest.TestCase):
    """§H3.2 : le budget tient compte de la marge que le proxy applique."""

    def test_valeur_exacte_du_budget(self) -> None:
        config = charger(
            Mode.REJEU,
            env={"OLLAMA_CONTEXT_LENGTH": "229376", "AVO_NUM_PREDICT": "4096"},
            racine=Path("/inexistant"),
        )
        attendu = math.floor(229376 / MARGE_PROXY) - 4096
        self.assertEqual(config.budget_prompt, attendu)
        # Valeur en clair, pour que le contrat soit lisible sans recalcul :
        # floor(229376 / 1,15) = 199457, moins 4096 réservés à la sortie.
        self.assertEqual(config.budget_prompt, 195361)

    def test_budget_negatif_est_une_erreur_explicite(self) -> None:
        with self.assertRaises(ConfigInvalide) as capture:
            charger(
                Mode.REJEU,
                env={"OLLAMA_CONTEXT_LENGTH": "1000", "AVO_NUM_PREDICT": "4096"},
                racine=Path("/inexistant"),
            )
        self.assertIn("AVO_NUM_PREDICT", str(capture.exception))

    def test_plafond_appris_abaisse_le_budget(self) -> None:
        config = charger(
            Mode.REJEU, env={"OLLAMA_CONTEXT_LENGTH": "500000"}, racine=Path("/inexistant")
        )
        appris = config.avec_plafond_appris(229376)
        self.assertEqual(appris.contexte_demande, 229376)
        self.assertLess(appris.budget_prompt, config.budget_prompt)

    def test_un_plafond_plus_large_n_elargit_pas_la_fenetre(self) -> None:
        """Un 413 ne peut pas relever silencieusement une fenêtre plus étroite."""
        config = charger(
            Mode.REJEU, env={"OLLAMA_CONTEXT_LENGTH": "100000"}, racine=Path("/inexistant")
        )
        self.assertIs(config.avec_plafond_appris(229376), config)

    def test_plafond_appris_absurde_refuse(self) -> None:
        config = charger(Mode.REJEU, env={}, racine=Path("/inexistant"))
        with self.assertRaises(ConfigInvalide):
            config.avec_plafond_appris(0)


class TestAucunSecretJournalise(unittest.TestCase):
    """§H4.6 : un objet Config peut atterrir dans un journal sans fuite."""

    def test_le_resume_masque_les_cles(self) -> None:
        config = charger(Mode.LIVE, env=_LIVE_MINIMAL, racine=Path("/inexistant"))
        resume = config.resume()
        self.assertEqual(resume["ollama_api_key"], "<masquée>")
        self.assertEqual(resume["arc_api_key"], "<masquée>")
        self.assertNotIn("sk-secret-de-test", str(resume))

    def test_la_representation_ne_contient_aucun_secret(self) -> None:
        config = charger(Mode.LIVE, env=_LIVE_MINIMAL, racine=Path("/inexistant"))
        texte = repr(config)
        self.assertNotIn("sk-secret-de-test", texte)
        self.assertNotIn(_LIVE_MINIMAL["ARC_API_KEY"], texte)
        self.assertIn("<masquée>", texte)

    def test_le_resume_reste_utile_pour_le_diagnostic(self) -> None:
        config = charger(Mode.LIVE, env=_LIVE_MINIMAL, racine=Path("/inexistant"))
        resume = config.resume()
        self.assertEqual(resume["mode"], "live")
        self.assertEqual(resume["contexte_demande"], 224000)
        self.assertEqual(resume["budget_prompt"], config.budget_prompt)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
