"""Preuves de la journalisation : JSON, corrélation, et surtout aucun secret.

@verifies docs/BACKLOG.md U8 — Comptabilité, journalisation, workspace de run
@verifies docs/SPEC_HARNAIS.md §H11.1 (JSON une ligne, niveaux, run_id),
          §H4.6 (aucun secret journalisé)
"""

from __future__ import annotations

import io
import json
import logging
import unittest
from datetime import UTC, datetime

from avo.runlog import MASQUE, FiltreSecrets, configurer_journalisation, nouveau_run_id

_SECRET = "sk-ollama-secret-qui-ne-doit-jamais-sortir"


class _Journal:
    """Capture les lignes JSON émises par le harnais."""

    def __init__(self, *secrets: str, run_id: str = "run-test") -> None:
        self.flux = io.StringIO()
        configurer_journalisation(run_id=run_id, secrets=secrets, flux=self.flux)
        self.logger = logging.getLogger("avo.test")

    def lignes(self) -> list[dict[str, object]]:
        return [json.loads(ligne) for ligne in self.flux.getvalue().splitlines() if ligne.strip()]

    def texte(self) -> str:
        return self.flux.getvalue()


class TestFormatJSON(unittest.TestCase):
    def tearDown(self) -> None:
        configurer_journalisation(flux=io.StringIO())

    def test_chaque_ligne_est_un_objet_json(self) -> None:
        journal = _Journal()
        journal.logger.info("un message")
        journal.logger.warning("un autre")
        lignes = journal.lignes()
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[0]["message"], "un message")
        self.assertEqual(lignes[1]["niveau"], "WARNING")

    def test_le_run_id_correle_toutes_les_lignes(self) -> None:
        journal = _Journal(run_id="run-42")
        journal.logger.info("a")
        journal.logger.info("b")
        self.assertTrue(all(ligne["run_id"] == "run-42" for ligne in journal.lignes()))

    def test_les_champs_supplementaires_sont_portes(self) -> None:
        journal = _Journal()
        journal.logger.info("appel", extra={"tokens": 42, "duree_s": 1.5})
        ligne = journal.lignes()[0]
        self.assertEqual(ligne["tokens"], 42)
        self.assertEqual(ligne["duree_s"], 1.5)

    def test_l_exception_est_serialisee(self) -> None:
        journal = _Journal()
        try:
            raise ValueError("cassé")
        except ValueError:
            journal.logger.exception("échec")
        self.assertIn("ValueError", str(journal.lignes()[0]["exception"]))


class TestAucunSecret(unittest.TestCase):
    """§H4.6 : la garantie ne repose pas sur la discipline des appelants."""

    def tearDown(self) -> None:
        configurer_journalisation(flux=io.StringIO())

    def test_un_secret_journalise_par_erreur_est_masque(self) -> None:
        journal = _Journal(_SECRET)
        journal.logger.info("appel avec %s", _SECRET)
        self.assertNotIn(_SECRET, journal.texte())
        self.assertIn(MASQUE, journal.texte())

    def test_un_secret_dans_un_champ_supplementaire_est_masque(self) -> None:
        journal = _Journal(_SECRET)
        journal.logger.info("appel", extra={"entete": f"Bearer {_SECRET}"})
        self.assertNotIn(_SECRET, journal.texte())

    def test_un_secret_imbrique_dans_une_structure_est_masque(self) -> None:
        journal = _Journal(_SECRET)
        journal.logger.info("appel", extra={"detail": {"liste": [{"cle": _SECRET}]}})
        self.assertNotIn(_SECRET, journal.texte())

    def test_une_valeur_trop_courte_n_est_pas_traitee_comme_un_secret(self) -> None:
        """Masquer « ok » rendrait les journaux illisibles sans rien protéger."""
        filtre = FiltreSecrets(["ok", _SECRET])
        self.assertEqual(filtre.secrets, (_SECRET,))

    def test_sans_secret_declare_le_message_passe_intact(self) -> None:
        journal = _Journal()
        journal.logger.info("message ordinaire")
        self.assertIn("message ordinaire", journal.texte())


class TestIdentifiantDeRun(unittest.TestCase):
    def test_format_lisible_et_triable(self) -> None:
        instant = datetime(2026, 8, 28, 3, 24, 34, tzinfo=UTC)
        self.assertEqual(nouveau_run_id(instant), "20260828-032434")
        self.assertEqual(nouveau_run_id(instant, "arc"), "20260828-032434-arc")

    def test_deux_instants_ordonnes_donnent_des_identifiants_ordonnes(self) -> None:
        tot = nouveau_run_id(datetime(2026, 8, 28, 1, 0, 0, tzinfo=UTC))
        tard = nouveau_run_id(datetime(2026, 8, 28, 2, 0, 0, tzinfo=UTC))
        self.assertLess(tot, tard)


class TestReconfiguration(unittest.TestCase):
    def tearDown(self) -> None:
        configurer_journalisation(flux=io.StringIO())

    def test_reconfigurer_ne_laisse_pas_deux_sorties(self) -> None:
        premier = io.StringIO()
        configurer_journalisation(run_id="a", flux=premier)
        second = io.StringIO()
        configurer_journalisation(run_id="b", flux=second)
        logging.getLogger("avo.test").info("après reconfiguration")
        self.assertEqual(premier.getvalue(), "")
        self.assertIn("après reconfiguration", second.getvalue())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
