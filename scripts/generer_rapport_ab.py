"""Rejoue l'A/B des deux modes de contexte et écrit le rapport comparatif (U27).

@spec docs/BACKLOG.md U27 — A/B sur rejeu, mode `transcript` vs mode `state`
@spec docs/SPEC_HARNAIS.md §H15.0 (le départage se fait par la mesure), §H15.7
      (mode exclusif par segment, `AVO_CONTEXT_MODE`)
@spec docs/SPEC_ARCAGI3.md §A7.1 (surface de `run-arc`), §A8.5 (jeu `cible-synthetique`)
@spec docs/MASTER_PLAN.md §5 (vérification dans la peau de l'utilisateur : la CLI
      documentée, réellement invoquée en sous-processus — jamais un raccourci interne)

Rejoue deux mini-campagnes `python -m avo run-arc --mode replay` sur le jeu
`cible-synthetique`, une par mode de contexte (§H15.7) — mêmes plafonds sinon — puis
construit et écrit le rapport comparatif sous `docs/rapports/` (`avo.arc.rapport_ab`).
Aucun secret requis : mode rejeu, contre la pile locale (`make up` préalable).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from avo.arc.campagne import EtatCampagne
from avo.arc.rapport_ab import MesureMode, rapport
from avo.memory.workspace import Workspace
from tests.e2e.scenarios import ENV_EPINGLE

#: Jeu et plafonds identiques à ceux des cassettes E2E scénarisées (§A8.5).
JEU = "cible-synthetique"
PLAFONDS_CLI = ("--tours-max", "120", "--actions-max-niveau", "100", "--actions-max-jeu", "200")

RAPPORT = Path("docs/rapports/ab_mode_contexte.md")

#: Endpoints de la pile locale de rejeu (§H2.4). Épinglés en dur dans
#: l'environnement du sous-processus pour neutraliser tout `.env` local qui
#: porterait un `OLLAMA_HOST` réel — sans quoi le rejeu appellerait le VRAI
#: endpoint (§A8.5, même principe que `tests/e2e/scenarios.ENV_EPINGLE`). Un
#: incident réel a confirmé le risque : sans ce garde-fou, une première tentative
#: de cette cible a réellement interrogé `qwen3.6:35b` en direct (docs/JOURNAL.md).
HOTE_LLM_REJEU = "http://127.0.0.1:11435"
BASE_ARC_REJEU = "http://127.0.0.1:8765"
JETON_REJEU = "sk-jeton-de-rejeu-ab"


def jouer(mode_contexte: str, runs_dir: Path) -> MesureMode:
    """Lance une mini-campagne par la CLI réelle, en sous-processus (MASTER_PLAN §5)."""
    run_id = f"ab-{mode_contexte}"
    environnement = {
        **os.environ,
        # Même épinglage complet que les scénarios E2E : un `.env` local qui porte
        # un `OLLAMA_CONTEXT_LENGTH` différent de celui des cassettes changerait
        # `options.num_ctx` et ferait rendre 599 au rejoueur (mesuré 2026-09-01,
        # `.env` à 98 304 contre cassettes à 229 376 — deux refus, rapport à zéro).
        **ENV_EPINGLE,
        "AVO_CONTEXT_MODE": mode_contexte,
        "AVO_RUNS_DIR": str(runs_dir),
        "OLLAMA_HOST": HOTE_LLM_REJEU,
        "OLLAMA_API_KEY": JETON_REJEU,
        "ARC_BASE_URL": BASE_ARC_REJEU,
    }
    execution = subprocess.run(
        [
            sys.executable,
            "-m",
            "avo",
            "run-arc",
            "--mode",
            "replay",
            "--games",
            JEU,
            "--run-id",
            run_id,
            *PLAFONDS_CLI,
        ],
        env=environnement,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if execution.returncode != 0:
        raise RuntimeError(
            f"campagne « {mode_contexte} » : code {execution.returncode}\n{execution.stderr}"
        )
    espace = Workspace(runs_dir, run_id)
    etat = EtatCampagne.lire(espace)
    return MesureMode(
        mode_contexte=mode_contexte,
        jeux=tuple(etat.resultats),
        metriques=tuple(espace.lire_metriques()),
    )


def generer(runs_dir: Path) -> str:
    """Rejoue les deux mini-campagnes et rend le rapport comparatif (contrat de la
    fonction pure `avo.arc.rapport_ab.rapport`)."""
    transcript = jouer("transcript", runs_dir)
    etat = jouer("state", runs_dir)
    return rapport(transcript, etat)


def main() -> int:
    with tempfile.TemporaryDirectory() as dossier:
        contenu = generer(Path(dossier))
    RAPPORT.parent.mkdir(parents=True, exist_ok=True)
    RAPPORT.write_text(contenu, encoding="utf-8")
    print(f"rapport comparatif A/B écrit : {RAPPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
