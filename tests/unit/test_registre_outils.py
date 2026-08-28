"""Preuves du registre d'outils : exposition, routage, erreurs, garde.

@verifies docs/BACKLOG.md U12 — Registre d'outils et dispatch
@verifies docs/SPEC_HARNAIS.md §H7.1 (registre, filtrage par état), §H7.2 (exécution
          séquentielle, messages `role: tool`, garde par tour), §H7.4 (erreurs rendues
          au modèle), §H5.1 (transcript append-only)
"""

from __future__ import annotations

import unittest
from typing import Any

from avo.context.transcript import Transcript
from avo.llm.client import ToolCall
from avo.tools.registre import (
    PREFIXE_ERREUR,
    Outil,
    RegistreOutils,
    outil_depuis_schema,
)

_SCHEMA_ECHO: dict[str, Any] = {
    "type": "object",
    "properties": {"texte": {"type": "string"}, "fois": {"type": "integer"}},
    "required": ["texte"],
}


def _echo(texte: str, fois: int = 1) -> str:
    return " ".join([texte] * fois)


def _outil_echo(**surcharges: Any) -> Outil:
    defauts: dict[str, Any] = {
        "nom": "echo",
        "description": "Répète un texte",
        "parametres": _SCHEMA_ECHO,
        "fonction": _echo,
    }
    return Outil(**{**defauts, **surcharges})


def _appel(nom: str = "echo", **arguments: Any) -> ToolCall:
    return ToolCall(nom=nom, arguments=arguments)


class TestDeclaration(unittest.TestCase):
    def test_un_outil_produit_le_schema_attendu_par_l_api(self) -> None:
        schema = _outil_echo().schema()
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "echo")
        self.assertEqual(schema["function"]["parameters"], _SCHEMA_ECHO)

    def test_un_nom_deja_enregistre_est_refuse(self) -> None:
        registre = RegistreOutils([_outil_echo()])
        with self.assertRaises(ValueError):
            registre.enregistrer(_outil_echo())

    def test_le_registre_expose_ses_noms_tries(self) -> None:
        registre = RegistreOutils([_outil_echo(nom="zeta"), _outil_echo(nom="alpha")])
        self.assertEqual(registre.noms, ("alpha", "zeta"))
        self.assertIn("alpha", registre)
        self.assertEqual(len(registre), 2)

    def test_construction_depuis_un_schema_existant(self) -> None:
        from avo.memory.notes import SCHEMA_NOTE_READ

        outil = outil_depuis_schema(SCHEMA_NOTE_READ, lambda name: name, ["notes"])
        self.assertEqual(outil.nom, "note_read")
        self.assertIn("notes", outil.etiquettes)
        self.assertIn("GUIDE", outil.parametres["properties"]["name"]["enum"])


class TestFiltrageParEtat(unittest.TestCase):
    """§H7.1 : les outils d'action ne sont offerts qu'à l'état où agir est permis."""

    def setUp(self) -> None:
        self.registre = RegistreOutils(
            [
                _outil_echo(nom="action1", etiquettes=frozenset({"action"})),
                _outil_echo(nom="note_read", etiquettes=frozenset({"notes"})),
                _outil_echo(nom="inspect", etiquettes=frozenset({"inspection"})),
            ]
        )

    def test_sans_filtre_tous_les_outils_sont_exposes(self) -> None:
        self.assertEqual(len(self.registre.schemas()), 3)

    def test_le_filtre_ne_retient_que_les_etiquettes_demandees(self) -> None:
        noms = [s["function"]["name"] for s in self.registre.schemas(["notes", "inspection"])]
        self.assertEqual(noms, ["inspect", "note_read"])
        self.assertNotIn("action1", noms)

    def test_une_etiquette_inconnue_n_expose_rien(self) -> None:
        self.assertEqual(self.registre.schemas(["inexistante"]), [])


class TestRoutage(unittest.TestCase):
    def setUp(self) -> None:
        self.registre = RegistreOutils([_outil_echo()])

    def test_un_appel_valide_rend_le_resultat_de_la_fonction(self) -> None:
        self.assertEqual(self.registre.router(_appel(texte="ha", fois=3)), "ha ha ha")

    def test_les_defauts_de_la_fonction_s_appliquent(self) -> None:
        self.assertEqual(self.registre.router(_appel(texte="seul")), "seul")


class TestErreursRenduesAuModele(unittest.TestCase):
    """§H7.4 : rien de ce que fait un outil n'interrompt le run."""

    def setUp(self) -> None:
        def qui_leve() -> str:
            raise RuntimeError("panne interne de l'outil")

        self.registre = RegistreOutils(
            [
                _outil_echo(),
                _outil_echo(
                    nom="casse", parametres={"type": "object", "properties": {}}, fonction=qui_leve
                ),
            ]
        )

    def test_un_outil_inconnu_liste_les_outils_disponibles(self) -> None:
        sortie = self.registre.router(_appel(nom="inexistant", texte="x"))
        self.assertTrue(sortie.startswith(f"{PREFIXE_ERREUR}: outil_inconnu"))
        self.assertIn("echo", sortie)

    def test_un_argument_obligatoire_absent_est_nomme(self) -> None:
        sortie = self.registre.router(_appel(fois=2))
        self.assertIn("texte", sortie)
        self.assertTrue(sortie.startswith(f"{PREFIXE_ERREUR}: arguments"))

    def test_un_type_incorrect_est_diagnostique(self) -> None:
        sortie = self.registre.router(_appel(texte="x", fois="beaucoup"))
        self.assertIn("integer", sortie)
        self.assertIn("str", sortie)

    def test_un_argument_inconnu_est_signale(self) -> None:
        sortie = self.registre.router(_appel(texte="x", inattendu=1))
        self.assertIn("inattendu", sortie)

    def test_une_enumeration_non_respectee_est_signalee(self) -> None:
        registre = RegistreOutils(
            [
                _outil_echo(
                    nom="choix",
                    parametres={
                        "type": "object",
                        "properties": {"mode": {"type": "string", "enum": ["a", "b"]}},
                        "required": ["mode"],
                    },
                    fonction=lambda mode: mode,
                )
            ]
        )
        sortie = registre.router(ToolCall(nom="choix", arguments={"mode": "c"}))
        self.assertIn("['a', 'b']", sortie)

    def test_des_arguments_json_invalides_sont_rendus_tels_quels(self) -> None:
        appel = ToolCall(nom="echo", erreur_arguments="arguments JSON invalides : ligne 1")
        sortie = self.registre.router(appel)
        self.assertTrue(sortie.startswith(f"{PREFIXE_ERREUR}: arguments"))
        self.assertIn("JSON invalides", sortie)

    def test_une_fonction_qui_leve_rend_un_texte_et_ne_propage_pas(self) -> None:
        sortie = self.registre.router(ToolCall(nom="casse", arguments={}))
        self.assertTrue(sortie.startswith(f"{PREFIXE_ERREUR}: RuntimeError"))
        self.assertIn("panne interne", sortie)


class TestExecutionEtGarde(unittest.TestCase):
    """§H7.2 : exécution séquentielle, messages `role: tool`, garde par tour."""

    def setUp(self) -> None:
        self.registre = RegistreOutils([_outil_echo()])
        self.transcript = Transcript.ouvrir("sys")

    def test_chaque_appel_ajoute_un_message_role_tool(self) -> None:
        appels = [_appel(texte="un"), _appel(texte="deux")]
        resultat = self.registre.executer(appels, self.transcript, tool_steps_max=40)
        messages = resultat.transcript.pour_api()[1:]
        self.assertEqual([m["role"] for m in messages], ["tool", "tool"])
        self.assertEqual([m["content"] for m in messages], ["un", "deux"])
        self.assertEqual([m["name"] for m in messages], ["echo", "echo"])

    def test_l_ordre_des_messages_suit_l_ordre_des_appels(self) -> None:
        appels = [_appel(texte=str(n)) for n in range(5)]
        resultat = self.registre.executer(appels, self.transcript, tool_steps_max=40)
        contenus = [m["content"] for m in resultat.transcript.pour_api()[1:]]
        self.assertEqual(contenus, ["0", "1", "2", "3", "4"])

    def test_l_historique_reste_append_only(self) -> None:
        resultat = self.registre.executer([_appel(texte="x")], self.transcript, 40)
        self.assertTrue(resultat.transcript.prolonge(self.transcript))

    def test_une_erreur_d_outil_est_aussi_un_message_tool(self) -> None:
        resultat = self.registre.executer([_appel(nom="inconnu")], self.transcript, 40)
        message = resultat.transcript.pour_api()[-1]
        self.assertEqual(message["role"], "tool")
        self.assertTrue(message["content"].startswith(PREFIXE_ERREUR))

    def test_la_garde_clot_le_tour_par_un_message_explicite(self) -> None:
        appels = [_appel(texte=str(n)) for n in range(10)]
        resultat = self.registre.executer(appels, self.transcript, tool_steps_max=3)
        self.assertTrue(resultat.garde_franchie)
        self.assertEqual(resultat.executes, 3)
        dernier = resultat.transcript.pour_api()[-1]
        self.assertEqual(dernier["role"], "user")
        self.assertIn("AVO_TOOL_STEPS_MAX", dernier["content"])

    def test_le_compteur_est_cumulable_entre_deux_lots(self) -> None:
        """La garde vaut pour le TOUR, pas pour un seul lot d'appels."""
        premier = self.registre.executer([_appel(texte="a")] * 2, self.transcript, 3)
        second = self.registre.executer(
            [_appel(texte="b")] * 2, premier.transcript, 3, deja_executes=premier.executes
        )
        self.assertTrue(second.garde_franchie)
        self.assertEqual(second.executes, 3)

    def test_sans_depassement_la_garde_reste_close(self) -> None:
        resultat = self.registre.executer([_appel(texte="x")], self.transcript, 40)
        self.assertFalse(resultat.garde_franchie)
        self.assertEqual(resultat.executes, 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
