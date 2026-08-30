"""E2E : l'A/B des deux modes de contexte est rejouable (U27).

@verifies docs/BACKLOG.md U27 — A/B sur rejeu : mode `transcript` vs mode `state`
@verifies docs/SPEC_HARNAIS.md §H15.0 (le départage se fait par la mesure), §H15.1
          (contrat `O(1)` par tour), §H15.8 (un pas = un tour)
@verifies docs/SPEC_ARCAGI3.md §A8.5 (contrat d'implémentation E2E, préconditions
          nommées), §A7.3 (contenu d'un rapport, principe réutilisé)

Rejoue les deux mini-campagnes (transcript, state) par la CLI réelle, pile compose
debout, servant les cassettes de victoire des deux modes. Reconstruit le rapport
comparatif et le compare **au fichier committé** sous `docs/rapports/` : la preuve
n'est pas que le script tourne, mais que le rapport committé est fidèlement
rejouable, à l'octet près, plutôt qu'une capture figée qui aurait pu diverger du
code (§A8.5, même exigence qu'`e2e_victoire.jsonl`/`e2e_echec.jsonl`).
"""

from __future__ import annotations

import tempfile
import unittest
import urllib.request
from pathlib import Path

from scripts.generer_rapport_ab import RAPPORT, generer

from tests.e2e.generer_cassette_etat import CASSETTE_NOM as CASSETTE_ETAT
from tests.e2e.generer_cassette_etat import DOSSIER_CASSETTES as DOSSIER_CASSETTES_ETAT
from tests.e2e.scenarios import DOSSIER_CASSETTES, VICTOIRE

HOTE_LLM = "http://127.0.0.1:11435"
BASE_ARC = "http://127.0.0.1:8765"


def setUpModule() -> None:  # noqa: N802 — contrat unittest
    """La pile et les deux cassettes de victoire sont des préconditions NOMMÉES."""
    for chemin in (DOSSIER_CASSETTES / VICTOIRE.cassette, DOSSIER_CASSETTES_ETAT / CASSETTE_ETAT):
        if not chemin.exists():
            raise RuntimeError(
                f"cassette {chemin} absente — lancez « make seed-e2e » puis « make down "
                "&& make up » (§A8.5)"
            )
    for nom, url in (("llm-replay", f"{HOTE_LLM}/_health"), ("arc-replay", f"{BASE_ARC}/_health")):
        try:
            with urllib.request.urlopen(url, timeout=5) as reponse:
                if reponse.status != 200:
                    raise RuntimeError(f"{nom} répond {reponse.status}")
        except Exception as erreur:  # noqa: BLE001 — le message opérateur prime
            raise RuntimeError(
                f"pile compose injoignable ({nom} : {erreur}) — lancez « make up » (§A8.5)"
            ) from erreur


class TestABModeContexte(unittest.TestCase):
    """Le rapport comparatif committé est rejouable, à l'octet près (§A8.5)."""

    def test_le_rapport_committe_est_rejouable_a_l_octet_pres(self) -> None:
        if not RAPPORT.exists():
            self.skipTest("docs/rapports/ab_mode_contexte.md absent — lancez « make rapport-ab »")
        with tempfile.TemporaryDirectory() as dossier:
            rejoue = generer(Path(dossier))
        committe = RAPPORT.read_text(encoding="utf-8")
        self.assertEqual(rejoue, committe)

    def test_le_rapport_nomme_les_mesures_du_backlog_u27(self) -> None:
        """RHAE, actions, tokens cumulés, taille moyenne de prompt, retries (BACKLOG.md U27)."""
        with tempfile.TemporaryDirectory() as dossier:
            contenu = generer(Path(dossier))
        for mesure in (
            "RHAE moyen",
            "Actions",
            "Tokens cumulés",
            "Taille moyenne de prompt",
            "Retries de patch",
        ):
            with self.subTest(mesure=mesure):
                self.assertIn(mesure, contenu)
        # Signal O(1) par tour (§H15.1) : moins d'appels en `state` qu'en `transcript`,
        # à RHAE et nombre d'actions égaux — le mode ne dégrade pas la partie jouée.
        self.assertIn("| Appels au modèle | 316 | 120 |", contenu)
        self.assertIn("| RHAE moyen | 100.00 | 100.00 |", contenu)
        self.assertIn("| Actions | 76 | 76 |", contenu)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
