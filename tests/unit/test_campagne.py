"""Preuves du runner de campagne : refus, plafonds, état persisté, reprise.

@verifies docs/BACKLOG.md U23 — Runner de campagne et rapport
@verifies docs/SPEC_ARCAGI3.md §A7.1 (plafonds obligatoires en live), §A7.2 (garde
          d'accord de publication), §A7.4 (structures, état de campagne, refus)
@verifies docs/SPEC_HARNAIS.md §H13.2 (reprise de run)
@verifies docs/BACKLOG.md U24 — réconciliation compteurs locale/API sur le résumé
          de scorecard (§A5.3 : champ présent qui diffère = divergence, champ
          absent = rien ; §A1.4 : forme du résumé mesurée)
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from avo.arc.campagne import (
    ETAT,
    CampagneInvalide,
    EtatCampagne,
    Plafonds,
    ResultatJeu,
    fabrique_partagee,
    reconcilier,
    valider,
)
from avo.arc.rhae import NiveauJoue, rhae_jeu
from avo.config import Mode, charger
from avo.memory.workspace import Workspace

CIBLE = (39, 19, 18)


def _plafonds(**surcharges: object) -> Plafonds:
    defauts: dict[str, object] = {
        "actions_niveau": 200,
        "actions_jeu": 800,
        "tours_max": 800,
        "secondes_jeu": 600.0,
        "tokens_jeu": 500_000,
    }
    defauts.update(surcharges)
    return Plafonds(**defauts)  # type: ignore[arg-type]


def _resultat(game_id: str = "cible") -> ResultatJeu:
    niveaux = (
        NiveauJoue(niveau=1, baseline=39, actions=39, complete=True),
        NiveauJoue(niveau=2, baseline=19, actions=4, complete=False),
        NiveauJoue(niveau=3, baseline=18, actions=0, complete=False),
    )
    return ResultatJeu(
        game_id=game_id,
        guid="g-1",
        niveaux=niveaux,
        rhae=rhae_jeu(niveaux),
        tours=43,
        arret="tours_epuises",
        actions=43,
        niveaux_completes=1,
        game_overs=0,
        tokens_prompt=1000,
        tokens_generes=200,
        secondes=12.5,
        continuations=1,
        depassements=0,
        interventions=2,
        versions_committees=1,
    )


class TestGardeDePublication(unittest.TestCase):
    """§A7.2 : jouer en live publie ; l'accord est explicite ou il n'y a pas de campagne."""

    def _config(self, mode: Mode):  # type: ignore[no-untyped-def]
        env = {
            "OLLAMA_HOST": "https://exemple.invalide",
            "OLLAMA_API_KEY": "sk-test",
            "OLLAMA_CONTEXT_LENGTH": "229376",
            "ARC_API_KEY": "cle-arc",
        }
        return charger(mode, env=env, racine=Path("/inexistant"))

    def test_le_mode_rejeu_ne_demande_aucun_accord(self) -> None:
        valider(self._config(Mode.REJEU), None, autorise_publication=False)

    def test_le_mode_live_sans_accord_est_refuse(self) -> None:
        with self.assertRaises(CampagneInvalide) as capture:
            valider(self._config(Mode.LIVE), _plafonds(), autorise_publication=False)
        message = str(capture.exception)
        self.assertIn("scorecard", message)
        self.assertIn("--j-autorise-la-publication", message)

    def test_le_mode_live_sans_budget_de_temps_est_refuse(self) -> None:
        with self.assertRaises(CampagneInvalide) as capture:
            valider(
                self._config(Mode.LIVE),
                _plafonds(secondes_jeu=None),
                autorise_publication=True,
            )
        self.assertIn("--budget-secondes-jeu", str(capture.exception))

    def test_le_mode_live_sans_budget_de_tokens_est_refuse(self) -> None:
        with self.assertRaises(CampagneInvalide) as capture:
            valider(self._config(Mode.LIVE), _plafonds(tokens_jeu=None), autorise_publication=True)
        self.assertIn("--budget-tokens-jeu", str(capture.exception))

    def test_le_mode_live_complet_passe(self) -> None:
        valider(self._config(Mode.LIVE), _plafonds(), autorise_publication=True)


class TestSerialisation(unittest.TestCase):
    """§A7.4 : l'état de campagne est l'unité de reprise ; il doit survivre au disque."""

    def test_les_plafonds_font_un_aller_retour_exact(self) -> None:
        plafonds = _plafonds()
        self.assertEqual(Plafonds.depuis_json(plafonds.en_json()), plafonds)

    def test_un_resultat_de_jeu_fait_un_aller_retour_exact(self) -> None:
        resultat = _resultat()
        relu = ResultatJeu.depuis_json(json.loads(json.dumps(resultat.en_json())))
        self.assertEqual(relu, resultat)

    def test_retries_patch_par_defaut_a_zero_et_fait_un_aller_retour(self) -> None:
        """§H15.4/§H15.8 : absent en mode `transcript`, réel en mode `state` (U27)."""
        self.assertEqual(_resultat().retries_patch, 0)
        avec_retries = ResultatJeu(**{**_resultat().__dict__, "retries_patch": 3})
        relu = ResultatJeu.depuis_json(json.loads(json.dumps(avec_retries.en_json())))
        self.assertEqual(relu.retries_patch, 3)

    def test_le_rhae_relu_est_RECALCULÉ_depuis_les_niveaux(self) -> None:
        """La valeur stockée est redondante : c'est le détail qui fait foi."""
        donnees = _resultat().en_json()
        donnees["rhae"] = 999.0
        self.assertEqual(ResultatJeu.depuis_json(donnees).rhae.valeur, _resultat().rhae.valeur)

    def test_les_tokens_se_totalisent(self) -> None:
        self.assertEqual(_resultat().tokens, 1200)


class TestEtatDeCampagne(unittest.TestCase):
    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        config = charger(Mode.REJEU, env={}, racine=Path("/inexistant"))
        self.espace = Workspace.ouvrir(config, "run-test", racine=self.racine)

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def _etat(self, **surcharges: object) -> EtatCampagne:
        defauts: dict[str, object] = {
            "run_id": "run-test",
            "mode": "replay",
            "plafonds": _plafonds(),
            "jeux_demandes": ["a", "b", "c"],
        }
        defauts.update(surcharges)
        return EtatCampagne(**defauts)  # type: ignore[arg-type]

    def test_les_jeux_restants_excluent_les_termines(self) -> None:
        etat = self._etat(resultats=[_resultat("b")])
        self.assertEqual(etat.restants(), ["a", "c"])
        self.assertEqual(etat.termines, {"b"})

    def test_l_ordre_demande_est_conserve(self) -> None:
        """La reprise doit rejouer dans le même ordre, sinon le rapport diverge."""
        self.assertEqual(self._etat().restants(), ["a", "b", "c"])

    def test_l_etat_fait_un_aller_retour_par_le_disque(self) -> None:
        etat = self._etat(resultats=[_resultat("a")], card_id="carte-1")
        etat.ecrire(self.espace)
        relu = EtatCampagne.lire(self.espace)
        self.assertEqual(relu.jeux_demandes, etat.jeux_demandes)
        self.assertEqual(relu.card_id, "carte-1")
        self.assertEqual(relu.plafonds, etat.plafonds)
        self.assertEqual(relu.resultats, etat.resultats)

    def test_l_accord_de_publication_est_persiste(self) -> None:
        """§A7.2 : l'accord appartient à la campagne, pas à l'invocation."""
        self._etat(autorise_publication=True).ecrire(self.espace)
        self.assertTrue(EtatCampagne.lire(self.espace).autorise_publication)

    def test_une_campagne_jamais_autorisee_le_reste_apres_relecture(self) -> None:
        self._etat().ecrire(self.espace)
        self.assertFalse(EtatCampagne.lire(self.espace).autorise_publication)

    def test_reprendre_sans_etat_est_refuse(self) -> None:
        with self.assertRaises(CampagneInvalide) as capture:
            EtatCampagne.lire(self.espace)
        self.assertIn(ETAT, str(capture.exception))

    def test_l_etat_est_ecrit_dans_le_workspace_du_run(self) -> None:
        self._etat().ecrire(self.espace)
        self.assertTrue((self.espace.chemin / ETAT).exists())


class TestReconciliation(unittest.TestCase):
    """§A5.3 : la réconciliation ne juge que ce que le résumé porte, sans rien masquer."""

    def test_resume_officiel_concordant_aucune_divergence(self) -> None:
        resume = {
            "environments": [
                {
                    "id": "cible",
                    "levels_completed": 1,
                    "runs": [
                        {
                            "guid": "g-1",
                            "actions": 43,
                            "levels_completed": 1,
                            "level_actions": [39, 4, 0],
                        }
                    ],
                }
            ]
        }
        self.assertEqual(reconcilier(resume, _resultat()), [])

    def test_chaque_ecart_present_est_nomme(self) -> None:
        resume = {
            "environments": [
                {
                    "id": "cible",
                    "runs": [
                        {
                            "guid": "g-1",
                            "actions": 44,
                            "levels_completed": 2,
                            "level_actions": [39, 5, 0],
                        }
                    ],
                }
            ]
        }
        divergences = reconcilier(resume, _resultat())
        champs = sorted(d["champ"] for d in divergences)
        self.assertEqual(champs, ["actions", "level_actions[1]", "levels_completed"])

    def test_resume_partiel_du_rejeu_local_ne_juge_que_ses_champs(self) -> None:
        resume = {"environments": [{"id": "cible", "levels_completed": 1, "state": "GAME_OVER"}]}
        self.assertEqual(reconcilier(resume, _resultat()), [])

    def test_environnement_absent_est_une_divergence(self) -> None:
        divergences = reconcilier({"environments": []}, _resultat())
        self.assertEqual(divergences[0]["champ"], "environnement")


class TestRefusEtAffinite(unittest.TestCase):
    """§A7.4 (2026-09-01) : refus de jeu persisté hors score, cookies partagés."""

    def test_un_refus_persiste_et_sort_des_restants(self) -> None:
        etat = EtatCampagne(
            run_id="r",
            mode="replay",
            plafonds=_plafonds(),
            jeux_demandes=["a", "b"],
            refus=[{"jeu": "a", "motif": "game a not found"}],
        )
        self.assertEqual(etat.restants(), ["b"], "le refus est l'issue nommée du jeu")
        with tempfile.TemporaryDirectory() as dossier:
            config = charger(Mode.REJEU, env={}, racine=Path("/inexistant"))
            espace = Workspace.ouvrir(config, "r", racine=Path(dossier))
            etat.ecrire(espace)
            relu = EtatCampagne.lire(espace)
        self.assertEqual(relu.refus, [{"jeu": "a", "motif": "game a not found"}])
        self.assertEqual(relu.restants(), ["b"], "la reprise ne rejoue pas un jeu refusé")

    def test_la_fabrique_partagee_donne_le_meme_transport_a_chaque_client(self) -> None:
        """§A1.4 mesuré : l'affinité par cookies couvre le scorecard — sans pot
        commun, la fermeture atteint un backend qui ignore le scorecard."""
        config = charger(Mode.REJEU, env={}, racine=Path("/inexistant"))
        fabriquer = fabrique_partagee(config)
        premier, second = fabriquer(), fabriquer()
        self.assertIsNot(premier, second, "chaque client garde son historique typé")
        self.assertIs(premier._transport, second._transport, "un seul pot de cookies")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
