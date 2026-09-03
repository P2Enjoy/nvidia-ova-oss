"""Bancs d'affinage du harnais : terrains de mesure déterministes, hors noyau §H.

@spec docs/BACKLOG.md U29 — Benchmarks interactifs complémentaires ; U29a2 —
      adaptateur harnais + CLI `banc` ; U29a4 — branchement du Dépôt logiciel ;
      U29b2 — branchement du banc CTF au dispatch
@spec docs/SPEC_BANCS.md §S1 (cadre commun : adaptateurs minces, noyau agnostique),
      §S6.3 (CLI : la sous-commande `banc` monte la boucle complète et écrit le
      relevé §S5.3), §S12.4 (dispatch `ctf` : `--env` porte la famille,
      `--bruit`/`--derive` hors défaut refusés par une erreur nommée,
      `--executeur` paramètre d'infrastructure), §S10.3 (`processus` refusé en
      mode `live`)

Le point d'entrée `executer_banc` est la seule surface que la CLI du noyau
connaît : elle ne nomme aucun banc ni environnement — le dispatch vit ici, sous
`src/avo/bancs/`, avec les mots du banc (balayage « zéro indice » du noyau).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from avo.bancs.ctf.score import ReleveCtf
from avo.bancs.skillexec.score import Releve


class BancInconnu(ValueError):
    """Banc ou environnement absent du dispatch : l'erreur nomme les disponibles."""


class ParametreBancInvalide(ValueError):
    """Paramètre refusé par le banc demandé : l'erreur nomme le refus (§S12.4)."""


@dataclass(frozen=True)
class SortieBanc:
    """Ce que l'exécution d'un épisode rend à la CLI (§S6.3)."""

    run_id: str
    releve: Releve | ReleveCtf
    chemin_releve: Path


def _valider_skillexec(environnement: str, executeur: str | None) -> None:
    """Refus nommés du banc a : environnement connu, aucun exécuteur (§S10.3)."""
    if environnement not in ("entrepot", "depot"):
        raise BancInconnu(
            f"environnement inconnu : « {environnement} ». Disponibles : entrepot, depot."
        )
    if executeur is not None:
        raise ParametreBancInvalide(
            "« --executeur » est sans objet pour le banc skillexec : ses "
            "environnements sont simulés, aucune commande n'y est exécutée (§S10.3)."
        )


def _valider_ctf(environnement: str, bruit: int, derive: bool, executeur: str, mode: str) -> None:
    """Refus nommés du banc b (§S8.3, §S10.3, §S12.4)."""
    from avo.bancs.ctf.adaptateur import EXECUTEUR_PROCESSUS, EXECUTEURS
    from avo.bancs.ctf.defis import ALEATOIRE, FAMILLES

    if environnement not in (*FAMILLES, ALEATOIRE):
        raise BancInconnu(
            f"environnement inconnu : « {environnement} ». Disponibles : "
            f"{', '.join(FAMILLES)}, {ALEATOIRE}."
        )
    if bruit != 0:
        raise ParametreBancInvalide(
            "« --bruit » ne s'applique pas au banc ctf (§S8.3) : le défi n'a "
            "pas de télémétrie de fond."
        )
    if derive:
        raise ParametreBancInvalide(
            "« --derive » ne s'applique pas au banc ctf (§S8.3) : le défi n'a pas de dérive d'état."
        )
    if executeur not in EXECUTEURS:
        raise ParametreBancInvalide(
            f"exécuteur inconnu : « {executeur} ». Disponibles : {', '.join(EXECUTEURS)}."
        )
    if mode == "live" and executeur == EXECUTEUR_PROCESSUS:
        raise ParametreBancInvalide(
            "l'exécuteur « processus » est refusé en mode live (§S10.3) : les "
            "commandes viennent du modèle et ne s'exécutent jamais directement "
            "sur l'hôte — utiliser « conteneur »."
        )


def executer_banc(
    nom: str,
    environnement: str,
    seed: int,
    horizon: int,
    bruit: int = 0,
    mode: str = "replay",
    run_id: str | None = None,
    tours_max: int | None = None,
    derive: bool = False,
    executeur: str | None = None,
) -> SortieBanc:
    """Monte et joue un épisode de banc, puis rend le relevé (§S6.3, §S12.4).

    En mode `replay`, la configuration pointe la pile locale comme le reste du
    produit (§H3.4) ; en mode `live`, l'endpoint réel est exigé par la
    configuration elle-même (§H3.3). Les paramètres sont validés AVANT de
    monter quoi que ce soit : un refus nommé ne laisse aucun workspace derrière.
    """
    from avo.config import charger
    from avo.memory.workspace import Workspace
    from avo.runlog import configurer_journalisation, nouveau_run_id

    if nom not in ("skillexec", "ctf"):
        raise BancInconnu(f"banc inconnu : « {nom} ». Disponibles : skillexec, ctf.")
    if nom == "skillexec":
        _valider_skillexec(environnement, executeur)
    else:
        from avo.bancs.ctf.adaptateur import EXECUTEUR_CONTENEUR

        executeur = executeur or EXECUTEUR_CONTENEUR
        _valider_ctf(environnement, bruit, derive, executeur, mode)

    config = charger(mode)
    identifiant = run_id or nouveau_run_id(suffixe="banc")
    configurer_journalisation(identifiant)
    espace = Workspace.ouvrir(config, identifiant)
    releve: Releve | ReleveCtf
    if nom == "skillexec":
        from avo.bancs.skillexec.adaptateur import jouer_episode

        releve = jouer_episode(
            config,
            espace,
            seed=seed,
            horizon=horizon,
            bruit=bruit,
            tours_max=tours_max,
            environnement=environnement,
            derive=derive,
        )
    else:
        from avo.bancs.ctf.adaptateur import jouer_episode_ctf

        assert executeur is not None  # posé au défaut ci-dessus
        releve = jouer_episode_ctf(
            config,
            espace,
            seed=seed,
            horizon=horizon,
            famille=environnement,
            executeur=executeur,
            tours_max=tours_max,
        )
    return SortieBanc(run_id=identifiant, releve=releve, chemin_releve=espace.chemin / "banc.json")
