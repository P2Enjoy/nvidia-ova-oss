"""Preuves du budget et de la continuation en contexte frais.

@verifies docs/BACKLOG.md U10 — Budget et continuation en contexte frais
@verifies docs/SPEC_HARNAIS.md §H5.3 (seuil, composition du segment frais),
          §H5.4 (`413` nominal, double dépassement fatal), §H3.2 (plafond appris)
"""

from __future__ import annotations

import unittest
from pathlib import Path

from avo.config import Config, Mode, charger
from avo.context.contexte import (
    DEPASSEMENTS_AVANT_ABANDON,
    INVITATION_CONTINUATION,
    BudgetIncoherent,
    Contexte,
    appels_en_api,
)
from avo.llm.client import ChatResult, ContextOverflow, ToolCall


def _config(**env: str) -> Config:
    return charger(Mode.REJEU, env=env, racine=Path("/inexistant"))


def _contexte(**env: str) -> Contexte:
    return Contexte(config=_config(**env), systeme="tu es un agent")


def _reponse(contenu: str = "ok", prompt: int = 100, sortie: int = 10) -> ChatResult:
    return ChatResult(content=contenu, prompt_eval_count=prompt, eval_count=sortie)


class TestBudgetEtSeuil(unittest.TestCase):
    """§H3.2 et §H5.3 : le seuil dérive du budget, lui-même dérivé de la marge."""

    def test_le_budget_vient_de_la_configuration(self) -> None:
        contexte = _contexte(OLLAMA_CONTEXT_LENGTH="229376", AVO_NUM_PREDICT="4096")
        self.assertEqual(contexte.budget_prompt, contexte.config.budget_prompt)
        self.assertEqual(contexte.budget_prompt, 195361)

    def test_le_seuil_est_la_fraction_configuree_du_budget(self) -> None:
        contexte = _contexte(
            OLLAMA_CONTEXT_LENGTH="229376", AVO_NUM_PREDICT="4096", AVO_CONTEXT_SOFT_RATIO="0.5"
        )
        self.assertEqual(contexte.seuil, contexte.budget_prompt // 2)

    def test_un_historique_court_ne_declenche_rien(self) -> None:
        contexte = _contexte()
        self.assertFalse(contexte.seuil_atteint())

    def test_un_historique_long_franchit_le_seuil(self) -> None:
        contexte = _contexte(OLLAMA_CONTEXT_LENGTH="6000", AVO_NUM_PREDICT="1000")
        self.assertFalse(contexte.seuil_atteint())
        contexte.ajouter_observation("x" * 60000)
        self.assertTrue(contexte.seuil_atteint())

    def test_le_seuil_suit_la_calibration_de_l_estimation(self) -> None:
        """Si le serveur compte plus que prévu, le seuil se franchit plus tôt."""
        contexte = _contexte(OLLAMA_CONTEXT_LENGTH="6000", AVO_NUM_PREDICT="1000")
        contexte.ajouter_observation("x" * 12000)
        avant = contexte.estimation()
        contexte.registre.enregistrer(avant, avant * 3)
        self.assertGreater(contexte.estimation(), avant)


class TestCompositionDuSegmentFrais(unittest.TestCase):
    """§H5.3 : système + continuation + notes + observation, dans cet ordre."""

    def setUp(self) -> None:
        self.contexte = _contexte()
        self.contexte.ajouter_observation("observation initiale")
        self.contexte.enregistrer_reponse(_reponse())

    def test_le_segment_frais_contient_exactement_les_quatre_elements(self) -> None:
        self.contexte.continuer("état repris", "mes notes", "observation courante")
        messages = list(self.contexte.transcript)
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[0].role, "system")
        self.assertEqual(messages[0].content, "tu es un agent")
        self.assertEqual(
            [message.content for message in messages[1:]],
            ["état repris", "mes notes", "observation courante"],
        )

    def test_l_ancien_segment_est_archive_et_non_efface(self) -> None:
        avant = self.contexte.transcript
        self.contexte.continuer("état", "notes", "observation")
        self.assertEqual(len(self.contexte.segments_archives), 1)
        self.assertEqual(self.contexte.segments_archives[0].empreinte(), avant.empreinte())

    def test_le_numero_de_segment_progresse(self) -> None:
        self.assertEqual(self.contexte.segment, 1)
        self.contexte.continuer("a", "b", "c")
        self.assertEqual(self.contexte.segment, 2)
        self.contexte.continuer("d", "e", "f")
        self.assertEqual(self.contexte.segment, 3)

    def test_le_segment_frais_repart_d_une_estimation_basse(self) -> None:
        self.contexte.ajouter_observation("y" * 50000)
        avant = self.contexte.estimation()
        self.contexte.continuer("état bref", "notes brèves", "observation brève")
        self.assertLess(self.contexte.estimation(), avant)

    def test_l_invitation_est_breve(self) -> None:
        """Elle consomme le budget qu'elle cherche à préserver (§H5.3)."""
        self.assertLess(len(INVITATION_CONTINUATION), 400)
        self.assertIn("état de continuation", INVITATION_CONTINUATION)


class TestDepassementDeContexte(unittest.TestCase):
    """§H5.4 : le `413` est un cas nominal ; deux consécutifs sont fatals."""

    def _depassement(self, plafond: int | None = 229376) -> ContextOverflow:
        return ContextOverflow(
            "contexte trop grand", tokens_estimated=248803, max_context_tokens=plafond
        )

    def test_un_premier_depassement_est_absorbe(self) -> None:
        contexte = _contexte()
        contexte.absorber_depassement(self._depassement())
        self.assertEqual(contexte.depassements_consecutifs, 1)

    def test_le_plafond_reel_est_appris(self) -> None:
        contexte = _contexte(OLLAMA_CONTEXT_LENGTH="1000000")
        avant = contexte.budget_prompt
        contexte.absorber_depassement(self._depassement(229376))
        self.assertEqual(contexte.config.contexte_demande, 229376)
        self.assertLess(contexte.budget_prompt, avant)

    def test_un_plafond_absent_n_empeche_pas_l_absorption(self) -> None:
        contexte = _contexte()
        contexte.absorber_depassement(self._depassement(plafond=None))
        self.assertEqual(contexte.depassements_consecutifs, 1)

    def test_deux_depassements_consecutifs_sont_fatals(self) -> None:
        contexte = _contexte()
        contexte.absorber_depassement(self._depassement())
        with self.assertRaises(BudgetIncoherent) as capture:
            contexte.absorber_depassement(self._depassement())
        message = str(capture.exception)
        self.assertIn("consécutifs", message)
        self.assertIn("OLLAMA_CONTEXT_LENGTH", message)

    def test_un_echange_abouti_remet_la_serie_a_zero(self) -> None:
        """Ce sont les dépassements CONSÉCUTIFS qui condamnent (§H5.4)."""
        contexte = _contexte()
        contexte.absorber_depassement(self._depassement())
        contexte.enregistrer_reponse(_reponse())
        self.assertEqual(contexte.depassements_consecutifs, 0)
        contexte.absorber_depassement(self._depassement())
        self.assertEqual(contexte.depassements_consecutifs, 1)

    def test_le_seuil_d_abandon_est_bien_de_deux(self) -> None:
        self.assertEqual(DEPASSEMENTS_AVANT_ABANDON, 2)


class TestHistoriqueFidele(unittest.TestCase):
    """L'historique doit refléter ce que le modèle a réellement demandé."""

    def test_les_appels_d_outils_sont_repris_dans_le_transcript(self) -> None:
        contexte = _contexte()
        resultat = ChatResult(
            content="",
            tool_calls=(ToolCall(nom="run_shell", arguments={"command": "ls"}, identifiant="a1"),),
        )
        contexte.enregistrer_reponse(resultat)
        dernier = contexte.transcript.pour_api()[-1]
        self.assertEqual(dernier["tool_calls"][0]["function"]["name"], "run_shell")
        self.assertEqual(dernier["tool_calls"][0]["id"], "a1")

    def test_la_conversion_omet_l_identifiant_absent(self) -> None:
        resultat = ChatResult(content="", tool_calls=(ToolCall(nom="f", arguments={}),))
        self.assertNotIn("id", appels_en_api(resultat)[0])

    def test_une_reponse_sans_outil_ne_porte_pas_le_champ(self) -> None:
        contexte = _contexte()
        contexte.enregistrer_reponse(_reponse("texte"))
        self.assertNotIn("tool_calls", contexte.transcript.pour_api()[-1])

    def test_l_historique_reste_append_only_a_travers_les_tours(self) -> None:
        contexte = _contexte()
        contexte.ajouter_observation("un")
        avant = contexte.transcript
        contexte.enregistrer_reponse(_reponse())
        self.assertTrue(contexte.transcript.prolonge(avant))


class TestResume(unittest.TestCase):
    def test_le_resume_compte_sans_divulguer(self) -> None:
        contexte = _contexte()
        contexte.ajouter_observation("contenu confidentiel")
        resume = contexte.resume()
        self.assertEqual(resume["segment"], 1)
        self.assertNotIn("contenu confidentiel", str(resume))
        self.assertIn("budget_prompt", resume)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
