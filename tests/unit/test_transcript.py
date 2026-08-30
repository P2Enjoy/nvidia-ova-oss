"""Preuves du transcript append-only : l'invariant qui protège le cache de préfixe.

@verifies docs/BACKLOG.md U9 — Transcript append-only
@verifies docs/SPEC_HARNAIS.md §H5.1 (immuable en tête, empreinte de préfixe),
          §H5.2 (comptabilité), §H1.3.1 (le préremplissage domine le coût)
"""

from __future__ import annotations

import dataclasses
import unittest

from avo.context.tokens import TokenLedger
from avo.context.transcript import (
    MUTATIONS_INTERDITES,
    Message,
    PrefixeRompu,
    Transcript,
)


class TestConstruction(unittest.TestCase):
    def test_un_transcript_ouvert_sans_systeme_est_vide(self) -> None:
        self.assertEqual(len(Transcript.ouvrir()), 0)

    def test_le_message_systeme_est_pose_en_tete(self) -> None:
        transcript = Transcript.ouvrir("tu es un agent")
        self.assertEqual(len(transcript), 1)
        self.assertEqual(transcript.messages[0].role, "system")
        self.assertEqual(transcript.messages[0].content, "tu es un agent")

    def test_les_roles_usuels_sont_disponibles(self) -> None:
        transcript = (
            Transcript.ouvrir("sys").utilisateur("bonjour").assistant("salut").outil("f", "42")
        )
        self.assertEqual(
            [message.role for message in transcript], ["system", "user", "assistant", "tool"]
        )
        self.assertEqual(transcript.messages[-1].tool_name, "f")


class TestImmuabilite(unittest.TestCase):
    """§H5.1 : on ne peut qu'ajouter. Rien ne permet de réécrire la tête."""

    def test_ajouter_ne_modifie_pas_l_instance_existante(self) -> None:
        avant = Transcript.ouvrir("sys").utilisateur("un")
        apres = avant.utilisateur("deux")
        self.assertEqual(len(avant), 2)
        self.assertEqual(len(apres), 3)
        self.assertIsNot(avant, apres)

    def test_l_empreinte_de_l_instance_existante_ne_bouge_pas(self) -> None:
        avant = Transcript.ouvrir("sys").utilisateur("un")
        empreinte = avant.empreinte()
        avant.utilisateur("deux")
        self.assertEqual(avant.empreinte(), empreinte)

    def test_les_champs_sont_geles(self) -> None:
        transcript = Transcript.ouvrir("sys")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            transcript.messages = ()  # type: ignore[misc]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            transcript.messages[0].content = "autre"  # type: ignore[misc]

    def test_les_messages_sont_dans_un_tuple(self) -> None:
        self.assertIsInstance(Transcript.ouvrir("sys").messages, tuple)

    def test_aucune_api_de_mutation_n_existe_sur_le_type(self) -> None:
        """Test de SURFACE : la garantie tient à ce que ces méthodes n'existent pas."""
        presentes = {nom for nom in MUTATIONS_INTERDITES if hasattr(Transcript, nom)}
        self.assertEqual(presentes, set(), f"API de mutation exposée : {presentes}")


class TestInvariantDePrefixe(unittest.TestCase):
    """§H5.1 : le préfixe déjà envoyé rend toujours la même empreinte."""

    def test_apres_n_tours_chaque_prefixe_reste_stable(self) -> None:
        transcript = Transcript.ouvrir("sys")
        empreintes: list[str] = [transcript.empreinte()]
        for tour in range(10):
            transcript = transcript.utilisateur(f"observation {tour}").assistant(f"action {tour}")
            empreintes.append(transcript.empreinte())
        # Le préfixe envoyé au tour k doit rendre exactement l'empreinte du tour k.
        for tour, empreinte in enumerate(empreintes):
            longueur = 1 + tour * 2
            self.assertEqual(transcript.empreinte_prefixe(longueur), empreinte, f"tour {tour}")

    def test_prolonge_reconnait_une_suite_legitime(self) -> None:
        avant = Transcript.ouvrir("sys").utilisateur("un")
        apres = avant.assistant("deux")
        self.assertTrue(apres.prolonge(avant))
        apres.verifier_prolonge(avant)

    def test_une_tete_reecrite_est_detectee(self) -> None:
        avant = Transcript.ouvrir("sys").utilisateur("un")
        falsifie = Transcript.ouvrir("sys").utilisateur("un MODIFIÉ").assistant("deux")
        self.assertFalse(falsifie.prolonge(avant))
        with self.assertRaises(PrefixeRompu) as capture:
            falsifie.verifier_prolonge(avant)
        self.assertIn("append-only", str(capture.exception))

    def test_un_message_insere_au_milieu_est_detecte(self) -> None:
        avant = Transcript.ouvrir("sys").utilisateur("un").assistant("deux")
        insere = Transcript.ouvrir("sys").utilisateur("un").utilisateur("intrus").assistant("deux")
        self.assertFalse(insere.prolonge(avant))

    def test_un_transcript_plus_court_ne_prolonge_pas(self) -> None:
        long = Transcript.ouvrir("sys").utilisateur("un").assistant("deux")
        court = Transcript.ouvrir("sys").utilisateur("un")
        self.assertFalse(court.prolonge(long))

    def test_un_systeme_different_rompt_le_prefixe(self) -> None:
        """Le message système est figé à l'ouverture du segment (§H5.1)."""
        avant = Transcript.ouvrir("sys").utilisateur("un")
        autre = Transcript.ouvrir("AUTRE").utilisateur("un").assistant("deux")
        self.assertFalse(autre.prolonge(avant))

    def test_prefixe_hors_bornes_est_une_erreur_explicite(self) -> None:
        transcript = Transcript.ouvrir("sys")
        with self.assertRaises(ValueError):
            transcript.empreinte_prefixe(5)
        with self.assertRaises(ValueError):
            transcript.empreinte_prefixe(-1)


class TestSerialisation(unittest.TestCase):
    def test_la_forme_api_ne_porte_pas_les_champs_vides(self) -> None:
        charge = Transcript.ouvrir("sys").utilisateur("bonjour").pour_api()
        self.assertEqual(
            charge,
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "bonjour"},
            ],
        )

    def test_les_appels_d_outils_sont_emis(self) -> None:
        transcript = Transcript.ouvrir().assistant("", [{"function": {"name": "f"}}])
        self.assertIn("tool_calls", transcript.pour_api()[0])

    def test_le_message_d_outil_porte_son_nom(self) -> None:
        charge = Transcript.ouvrir().outil("run_shell", "sortie").pour_api()[0]
        self.assertEqual(charge["name"], "run_shell")
        self.assertEqual(charge["role"], "tool")

    def test_l_empreinte_ne_depend_pas_de_l_ordre_des_cles(self) -> None:
        """La canonisation trie les clés : deux mêmes historiques s'apparient."""
        a = Transcript((Message(role="user", content="x"),))
        b = Transcript((Message(content="x", role="user"),))
        self.assertEqual(a.empreinte(), b.empreinte())


class TestComptabilite(unittest.TestCase):
    """§H5.2 : l'estimation porte sur le texte réellement envoyé."""

    def test_le_texte_integral_couvre_tous_les_messages(self) -> None:
        transcript = Transcript.ouvrir("sys").utilisateur("bonjour").assistant("salut")
        texte = transcript.texte_integral()
        for attendu in ("sys", "bonjour", "salut"):
            self.assertIn(attendu, texte)

    def test_l_estimation_croit_avec_l_historique(self) -> None:
        registre = TokenLedger()
        court = Transcript.ouvrir("sys")
        long = court.utilisateur("x" * 1000)
        self.assertGreater(
            registre.estimer(long.texte_integral()), registre.estimer(court.texte_integral())
        )

    def test_le_resume_compte_sans_divulguer(self) -> None:
        transcript = Transcript.ouvrir("sys").utilisateur("contenu confidentiel")
        resume = transcript.resume()
        self.assertEqual(resume["messages"], 2)
        self.assertEqual(resume["roles"], {"system": 1, "user": 1})
        self.assertNotIn("contenu confidentiel", str(resume))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
