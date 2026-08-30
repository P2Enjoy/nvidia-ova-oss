"""Preuves des notes persistantes : deux noms, lecture, écriture, refus.

@verifies docs/BACKLOG.md U11 — Notes persistantes
@verifies docs/SPEC_HARNAIS.md §H6.2 (rôles GUIDE/WORKING), §H7.3 (outils, noms
          limités), §H7.4 (erreur d'outil rendue au modèle), §H5.3 (bloc injecté)
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from avo.memory.notes import (
    GUIDE,
    NOMS_AUTORISES,
    WORKING,
    NomDeNoteInvalide,
    Notes,
    note_read,
    note_write,
)


class TestNotes(unittest.TestCase):
    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.notes = Notes(Path(self._dossier.name) / "notes")

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def test_le_dossier_est_cree(self) -> None:
        self.assertTrue(self.notes.dossier.is_dir())

    def test_une_note_jamais_ecrite_est_vide_et_non_absente(self) -> None:
        self.assertEqual(self.notes.lire(GUIDE), "")

    def test_ecrire_puis_lire_restitue_le_contenu(self) -> None:
        self.notes.ecrire(GUIDE, "les verts sautent par-dessus les rouges")
        self.assertEqual(self.notes.lire(GUIDE), "les verts sautent par-dessus les rouges")

    def test_une_note_se_reecrit_entierement(self) -> None:
        """À la différence du transcript, une note est révisable (§H6.2)."""
        self.notes.ecrire(WORKING, "première hypothèse")
        self.notes.ecrire(WORKING, "hypothèse corrigée")
        self.assertEqual(self.notes.lire(WORKING), "hypothèse corrigée")

    def test_les_deux_notes_sont_independantes(self) -> None:
        self.notes.ecrire(GUIDE, "durable")
        self.notes.ecrire(WORKING, "brouillon")
        self.assertEqual(self.notes.toutes(), {GUIDE: "durable", WORKING: "brouillon"})

    def test_vider_efface_sans_supprimer(self) -> None:
        self.notes.ecrire(WORKING, "niveau précédent")
        self.notes.vider(WORKING)
        self.assertEqual(self.notes.lire(WORKING), "")
        self.assertTrue(self.notes.chemin(WORKING).exists())

    def test_les_notes_sont_ecrites_sur_disque_en_markdown(self) -> None:
        self.notes.ecrire(GUIDE, "contenu")
        self.assertEqual(self.notes.chemin(GUIDE).name, "GUIDE.md")
        self.assertEqual(self.notes.chemin(GUIDE).read_text(encoding="utf-8"), "contenu")


class TestNomsLimites(unittest.TestCase):
    """§H7.3 : deux noms, pas trois. La contrainte est délibérée."""

    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.notes = Notes(Path(self._dossier.name) / "notes")

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def test_seuls_deux_noms_existent(self) -> None:
        self.assertEqual(NOMS_AUTORISES, ("GUIDE", "WORKING"))

    def test_un_autre_nom_est_refuse_en_lecture(self) -> None:
        with self.assertRaises(NomDeNoteInvalide) as capture:
            self.notes.lire("SCRATCH")
        message = str(capture.exception)
        self.assertIn("SCRATCH", message)
        self.assertIn("GUIDE", message)

    def test_un_autre_nom_est_refuse_en_ecriture(self) -> None:
        with self.assertRaises(NomDeNoteInvalide):
            self.notes.ecrire("notes/../../etc/passwd", "malveillant")

    def test_la_casse_et_l_extension_sont_tolerees(self) -> None:
        self.notes.ecrire("guide.md", "contenu")
        self.assertEqual(self.notes.lire("GUIDE"), "contenu")
        self.assertEqual(self.notes.lire(" Working "), "")

    def test_aucun_chemin_n_echappe_au_dossier(self) -> None:
        for tentative in ("../evasion", "/etc/passwd", "GUIDE/../../x"):
            with self.subTest(tentative=tentative), self.assertRaises(NomDeNoteInvalide):
                self.notes.chemin(tentative)


class TestBlocInjecte(unittest.TestCase):
    """§H5.3 : les notes réapparaissent en tête de segment frais."""

    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.notes = Notes(Path(self._dossier.name) / "notes")

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def test_le_bloc_porte_les_deux_notes_et_leurs_roles(self) -> None:
        self.notes.ecrire(GUIDE, "règle durable")
        self.notes.ecrire(WORKING, "essai en cours")
        bloc = self.notes.pour_segment_frais()
        self.assertIn("règle durable", bloc)
        self.assertIn("essai en cours", bloc)
        self.assertIn("GUIDE.md", bloc)
        self.assertIn("WORKING.md", bloc)
        self.assertIn("transverse aux niveaux", bloc)

    def test_une_note_vide_est_annoncee_et_non_omise(self) -> None:
        """Son absence est une information : l'agent saura qu'il n'a rien consigné."""
        self.notes.ecrire(GUIDE, "seulement le guide")
        bloc = self.notes.pour_segment_frais()
        self.assertIn("(vide)", bloc)
        self.assertIn("WORKING.md", bloc)

    def test_le_resume_compte_sans_divulguer(self) -> None:
        self.notes.ecrire(GUIDE, "contenu confidentiel")
        resume = self.notes.resume()
        self.assertEqual(resume["guide_caracteres"], len("contenu confidentiel"))
        self.assertNotIn("confidentiel", str(resume))


class TestSurfaceOutil(unittest.TestCase):
    """§H7.4 : une erreur d'outil est rendue au modèle, pas levée."""

    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.notes = Notes(Path(self._dossier.name) / "notes")

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def test_ecriture_puis_lecture_par_les_outils(self) -> None:
        confirmation = note_write(self.notes, "GUIDE", "ma compréhension")
        self.assertIn("GUIDE.md", confirmation)
        self.assertEqual(note_read(self.notes, "GUIDE"), "ma compréhension")

    def test_une_note_vide_le_dit_au_modele(self) -> None:
        self.assertEqual(note_read(self.notes, "WORKING"), "(note vide)")

    def test_un_nom_invalide_rend_un_texte_d_erreur_sans_lever(self) -> None:
        resultat = note_read(self.notes, "AUTRE")
        self.assertTrue(resultat.startswith("error:"))
        self.assertIn("GUIDE", resultat)

    def test_une_ecriture_invalide_rend_un_texte_d_erreur_sans_lever(self) -> None:
        resultat = note_write(self.notes, "AUTRE", "contenu")
        self.assertTrue(resultat.startswith("error:"))
        self.assertEqual(list(self.notes.dossier.glob("*.md")), [])

    def test_les_schemas_declarent_les_noms_acceptes(self) -> None:
        from avo.memory.notes import SCHEMA_NOTE_READ, SCHEMA_NOTE_WRITE

        for schema in (SCHEMA_NOTE_READ, SCHEMA_NOTE_WRITE):
            enum = schema["function"]["parameters"]["properties"]["name"]["enum"]
            self.assertEqual(enum, list(NOMS_AUTORISES))
        self.assertEqual(
            SCHEMA_NOTE_WRITE["function"]["parameters"]["required"], ["name", "content"]
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
