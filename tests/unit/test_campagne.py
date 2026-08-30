"""Preuves du runner de campagne : refus, plafonds, état persisté, reprise.

@verifies docs/BACKLOG.md U23 — Runner de campagne et rapport
@verifies docs/SPEC_ARCAGI3.md §A7.1 (plafonds obligatoires en live), §A7.2 (garde
          d'accord de publication), §A7.4 (structures, état de campagne, refus)
@verifies docs/SPEC_HARNAIS.md §H13.2 (reprise de run)
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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
