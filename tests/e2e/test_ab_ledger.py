"""E2E : l'A/B du patron ledger est rejouable (U37).

@verifies docs/BACKLOG.md U37 — A/B en rejeu : harnais enrichi contre harnais nu,
          même mode `state` (patron U27)
@verifies docs/SPEC_HARNAIS.md §H18.2 (le pas d'idéation est joué et gratuit au
          score), §H18.4 (interrupteurs : `false` = comportement d'avant H18),
          §H18.6 (preuve exigée)
@verifies docs/SPEC_ARCAGI3.md §A8.5 (contrat d'implémentation E2E, préconditions
          nommées)

Même patron que `test_ab_mode_contexte.py` (U27) : rejoue les deux mini-campagnes
par la CLI réelle, pile compose debout, servant la cassette du harnais nu et celle
du harnais enrichi, puis reconstruit le rapport comparatif et le compare AU FICHIER
COMMITTÉ sous `docs/rapports/` — la preuve n'est pas que le script tourne, mais que
le rapport committé est fidèlement rejouable, à l'octet près (§A8.5).
"""

from __future__ import annotations

import tempfile
import unittest
import urllib.request
from pathlib import Path

from scripts.generer_rapport_ab_ledger import RAPPORT, generer, jouer

from tests.e2e.generer_cassette_etat import CASSETTE_NOM as CASSETTE_NU
from tests.e2e.generer_cassette_ledger import CASSETTE_NOM as CASSETTE_ENRICHI
from tests.e2e.generer_cassette_ledger import DOSSIER_CASSETTES

HOTE_LLM = "http://127.0.0.1:11435"
BASE_ARC = "http://127.0.0.1:8765"


def setUpModule() -> None:  # noqa: N802 — contrat unittest
    """La pile et les deux cassettes sont des préconditions NOMMÉES (§A8.5)."""
    for nom in (CASSETTE_NU, CASSETTE_ENRICHI):
        if not (DOSSIER_CASSETTES / nom).exists():
            raise RuntimeError(
                f"cassette {DOSSIER_CASSETTES / nom} absente — lancez « make seed-e2e » "
                "puis « make down && make up » (§A8.5)"
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


class TestABLedger(unittest.TestCase):
    """Le rapport comparatif committé est rejouable, à l'octet près (§A8.5)."""

    def test_le_rapport_committe_est_rejouable_a_l_octet_pres(self) -> None:
        if not RAPPORT.exists():
            self.skipTest(
                "docs/rapports/ab_ledger_state.md absent — lancez « make rapport-ab-ledger »"
            )
        with tempfile.TemporaryDirectory() as dossier:
            rejoue = generer(Path(dossier))
        self.assertEqual(
            rejoue,
            RAPPORT.read_text(encoding="utf-8"),
            "le rapport committé diverge du rejeu — relancez « make rapport-ab-ledger » "
            "et committez le rapport avec le changement qui l'explique",
        )

    def test_l_ideation_est_jouee_et_gratuite_au_score(self) -> None:
        """§H18.2 : le bras enrichi joue un pas de plus, aucune action de plus."""
        with tempfile.TemporaryDirectory() as dossier:
            nu = jouer("nu", Path(dossier))
            enrichi = jouer("enrichi", Path(dossier))
        self.assertEqual(nu.ideations, 0)
        self.assertEqual(enrichi.ideations, 1)
        self.assertEqual(enrichi.tours, nu.tours + 1, "un tour d'appel de plus")
        self.assertEqual(enrichi.actions, nu.actions, "aucune action de plus au score")
        self.assertEqual(enrichi.niveaux_completes, nu.niveaux_completes)


if __name__ == "__main__":
    unittest.main()
