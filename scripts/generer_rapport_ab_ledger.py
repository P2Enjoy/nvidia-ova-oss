"""Rejoue l'A/B « harnais enrichi contre harnais nu » et écrit le rapport (U37).

@spec docs/BACKLOG.md U37 — A/B en rejeu sur cassettes générées : harnais enrichi
      (mécanismes H18 actifs) contre harnais nu, même mode `state` (patron U27)
@spec docs/SPEC_HARNAIS.md §H18.4 (interrupteurs : `false` = comportement d'avant
      H18), §H18.5 (`ideations` au bilan et au rapport), §H18.6 (preuve exigée)
@spec docs/MASTER_PLAN.md §5 (vérification dans la peau de l'utilisateur : la CLI
      documentée, réellement invoquée en sous-processus — jamais un raccourci interne)

Rejoue deux mini-campagnes `python -m avo run-arc --mode replay` sur le jeu
`cible-synthetique`, TOUTES DEUX en mode `state` — seule la position des
interrupteurs H18 diffère (§H18.4) — puis écrit le rapport comparatif sous
`docs/rapports/`. Le rejeu mesure le COMPORTEMENT du harnais (appels, prompts,
événements), jamais la qualité des choix du modèle : les réponses sont celles des
cassettes générées, scriptées sur le même chemin parfait des deux côtés.
Aucun secret requis : mode rejeu, contre la pile locale (`make up` préalable).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.e2e.scenarios import ENV_EPINGLE

from avo.arc.campagne import EtatCampagne, ResultatJeu
from avo.memory.workspace import Workspace

#: Jeu et plafonds identiques à ceux des cassettes E2E scénarisées (§A8.5).
JEU = "cible-synthetique"
PLAFONDS_CLI = ("--tours-max", "120", "--actions-max-niveau", "100", "--actions-max-jeu", "200")

RAPPORT = Path("docs/rapports/ab_ledger_state.md")

#: Endpoints de la pile locale de rejeu (§H2.4), épinglés en dur pour neutraliser
#: tout `.env` local (même garde-fou mesuré que `scripts/generer_rapport_ab.py`).
HOTE_LLM_REJEU = "http://127.0.0.1:11435"
BASE_ARC_REJEU = "http://127.0.0.1:8765"
JETON_REJEU = "sk-jeton-de-rejeu-ab-ledger"

#: Les deux bras de l'A/B (§H18.4) : seule la position des interrupteurs change.
BRAS: dict[str, dict[str, str]] = {
    "nu": {"AVO_PLAN_LEDGER": "false", "AVO_IDEATION_OUVERTURE": "false"},
    "enrichi": {"AVO_PLAN_LEDGER": "true", "AVO_IDEATION_OUVERTURE": "true"},
}


def jouer(bras: str, runs_dir: Path) -> ResultatJeu:
    """Lance une mini-campagne par la CLI réelle, en sous-processus (MASTER_PLAN §5)."""
    run_id = f"ab-ledger-{bras}"
    environnement = {
        **os.environ,
        **ENV_EPINGLE,
        "AVO_CONTEXT_MODE": "state",
        **BRAS[bras],
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
        raise RuntimeError(f"campagne « {bras} » : code {execution.returncode}\n{execution.stderr}")
    etat = EtatCampagne.lire(Workspace(runs_dir, run_id))
    (jeu,) = etat.resultats
    return jeu


def _ligne(intitule: str, nu: object, enrichi: object) -> str:
    return f"| {intitule} | {nu} | {enrichi} |"


def rapport(nu: ResultatJeu, enrichi: ResultatJeu) -> str:
    """Rapport markdown comparatif, committé sous `docs/rapports/` (§H18.6)."""
    return (
        "\n\n".join(
            [
                "# A/B du patron ledger, sur rejeu (U37)",
                (
                    "Comparaison du harnais NU (mécanismes H18 inactifs, le comportement "
                    "d'avant U37) et du harnais ENRICHI (`AVO_PLAN_LEDGER` et "
                    "`AVO_IDEATION_OUVERTURE` actifs, §H18.4) sur le jeu synthétique local "
                    "`cible-synthetique`, mêmes plafonds, même mode `state`, mêmes réponses "
                    "scriptées sur le même chemin parfait (cassettes générées, §A8.5). Le "
                    "rejeu prouve le COMPORTEMENT du harnais — le pas d'idéation est joué, "
                    "gratuit au score, le ledger voyage dans Σ — jamais la qualité des choix "
                    "du modèle : celle-ci se mesure en conditions réelles (U38)."
                ),
                "\n".join(
                    [
                        "| Mesure | harnais nu | harnais enrichi |",
                        "|---|---|---|",
                        _ligne("actions jouées", nu.actions, enrichi.actions),
                        _ligne(
                            "niveaux complétés", nu.niveaux_completes, enrichi.niveaux_completes
                        ),
                        _ligne("RHAE", f"{nu.rhae.valeur:.3f}", f"{enrichi.rhae.valeur:.3f}"),
                        _ligne("tours (appels de pas)", nu.tours, enrichi.tours),
                        _ligne("pas d'idéation (§H18.2)", nu.ideations, enrichi.ideations),
                        _ligne("curations (§H18.3)", nu.curations, enrichi.curations),
                        _ligne("tokens de prompt", nu.tokens_prompt, enrichi.tokens_prompt),
                        _ligne("tokens générés", nu.tokens_generes, enrichi.tokens_generes),
                    ]
                ),
                (
                    "Lecture : à chemin parfait identique, le harnais enrichi joue le même "
                    "nombre d'actions et complète les mêmes niveaux — l'idéation coûte un "
                    "tour d'appel sans coûter d'action au score, et le protocole du ledger "
                    "grossit chaque prompt (le préremplissage domine le coût, §H1.3.1). Le "
                    "gain attendu du patron — moins d'ancrage, un plan curé — ne peut pas "
                    "apparaître sur des réponses scriptées : c'est l'objet de l'A/B réel "
                    "(U38), qui départage à budget constant."
                ),
            ]
        )
        + "\n"
    )


def generer(runs_dir: Path) -> str:
    """Rejoue les deux bras et rend le rapport comparatif."""
    return rapport(jouer("nu", runs_dir), jouer("enrichi", runs_dir))


def main() -> int:
    with tempfile.TemporaryDirectory() as dossier:
        contenu = generer(Path(dossier))
    RAPPORT.parent.mkdir(parents=True, exist_ok=True)
    RAPPORT.write_text(contenu, encoding="utf-8")
    print(f"rapport comparatif A/B ledger écrit : {RAPPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
