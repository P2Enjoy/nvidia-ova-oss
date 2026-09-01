"""Bancs d'affinage du harnais : terrains de mesure déterministes, hors noyau §H.

@spec docs/BACKLOG.md U29 — Benchmarks interactifs complémentaires ; U29a2 —
      adaptateur harnais + CLI `banc` ; U29a4 — branchement du Dépôt logiciel
@spec docs/SPEC_BANCS.md §S1 (cadre commun : adaptateurs minces, noyau agnostique),
      §S6.3 (CLI : la sous-commande `banc` monte la boucle complète et écrit le
      relevé §S5.3)

Le point d'entrée `executer_banc` est la seule surface que la CLI du noyau
connaît : elle ne nomme aucun banc ni environnement — le dispatch vit ici, sous
`src/avo/bancs/`, avec les mots du banc (balayage « zéro indice » du noyau).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from avo.bancs.skillexec.score import Releve


class BancInconnu(ValueError):
    """Banc ou environnement absent du dispatch : l'erreur nomme les disponibles."""


@dataclass(frozen=True)
class SortieBanc:
    """Ce que l'exécution d'un épisode rend à la CLI (§S6.3)."""

    run_id: str
    releve: Releve
    chemin_releve: Path


def executer_banc(
    nom: str,
    environnement: str,
    seed: int,
    horizon: int,
    bruit: int = 0,
    mode: str = "replay",
    run_id: str | None = None,
    tours_max: int | None = None,
) -> SortieBanc:
    """Monte et joue un épisode de banc, puis rend le relevé (§S6.3).

    En mode `replay`, la configuration pointe la pile locale comme le reste du
    produit (§H3.4) ; en mode `live`, l'endpoint réel est exigé par la
    configuration elle-même (§H3.3).
    """
    from avo.bancs.skillexec.adaptateur import jouer_episode
    from avo.config import charger
    from avo.memory.workspace import Workspace
    from avo.runlog import configurer_journalisation, nouveau_run_id

    if nom != "skillexec":
        raise BancInconnu(f"banc inconnu : « {nom} ». Disponibles : skillexec.")
    if environnement not in ("entrepot", "depot"):
        raise BancInconnu(
            f"environnement inconnu : « {environnement} ». Disponibles : entrepot, depot."
        )
    config = charger(mode)
    identifiant = run_id or nouveau_run_id(suffixe="banc")
    configurer_journalisation(identifiant)
    espace = Workspace.ouvrir(config, identifiant)
    releve = jouer_episode(
        config,
        espace,
        seed=seed,
        horizon=horizon,
        bruit=bruit,
        tours_max=tours_max,
        environnement=environnement,
    )
    return SortieBanc(run_id=identifiant, releve=releve, chemin_releve=espace.chemin / "banc.json")
