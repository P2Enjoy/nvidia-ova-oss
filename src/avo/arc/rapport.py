"""Rapport de campagne : ce que la campagne a fait, et ce qu'elle n'établit pas.

@spec docs/BACKLOG.md U23 — Runner de campagne et rapport
@spec docs/SPEC_ARCAGI3.md §A7.3 (contenu du rapport), §A7.4 (le rapport est une
      fonction pure du résultat et des métriques), §A6 (RHAE)
@spec docs/SPEC_HARNAIS.md §H6.1 (`report.md` dans le workspace), §H11.2 (métriques)

Fonction **pure** : elle ne rejoue rien, n'interroge aucun service et ne devine
aucun chiffre. Tout ce qu'elle écrit vient du résultat de campagne ou des métriques
que le run a réellement produites — ce qui est absent est dit absent.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from avo.arc.campagne import ResultatCampagne, ResultatJeu
from avo.memory.workspace import Workspace

#: Références publiées, pour situer un résultat (§A7.3). Score RHAE, puis actions
#: cumulées sur l'ensemble public ARC-AGI-3.
REFERENCES: tuple[tuple[str, float, int], ...] = (
    ("AVO (billet NVIDIA, 2026-08-21)", 100.00, 6624),
    ("VISTA (page projet)", 100.00, 7542),
    ("Tycho, Opus 5", 100.00, 6641),
)


def formater(valeur: float) -> str:
    """Deux décimales : la mise en forme appartient au rapport, pas au calcul (§A6.4)."""
    return f"{valeur:.2f}"


def table_par_jeu(jeux: Sequence[ResultatJeu]) -> str:
    """Un jeu par ligne : niveaux, actions, baseline, RHAE (§A7.3)."""
    if not jeux:
        return "_Aucun jeu joué._"
    lignes = [
        "| Jeu | Niveaux complétés | Actions | Baseline | RHAE | Arrêt |",
        "|---|---|---|---|---|---|",
    ]
    for jeu in jeux:
        baseline = sum(niveau.baseline for niveau in jeu.niveaux)
        lignes.append(
            f"| `{jeu.game_id}` | {jeu.niveaux_completes} / {len(jeu.niveaux)} "
            f"| {jeu.actions} | {baseline} | {formater(jeu.rhae.valeur)} | {jeu.arret} |"
        )
    return "\n".join(lignes)


def table_par_niveau(jeux: Sequence[ResultatJeu]) -> str:
    """Le détail qui rend le RHAE vérifiable à la main (§A6.1)."""
    lignes = [
        "| Jeu | Niveau | Baseline hₗ | Actions aₗ | Complété | Poids wₗ |",
        "|---|---|---|---|---|---|",
    ]
    for jeu in jeux:
        for niveau in jeu.niveaux:
            lignes.append(
                f"| `{jeu.game_id}` | {niveau.niveau} | {niveau.baseline} | {niveau.actions} "
                f"| {'oui' if niveau.complete else 'non'} | {niveau.poids} |"
            )
    return "\n".join(lignes) if len(lignes) > 2 else "_Aucun niveau._"


def couts(jeux: Sequence[ResultatJeu], metriques: Sequence[Mapping[str, Any]]) -> str:
    """Tokens, durées, actions — et le nombre d'appels, qui vient des métriques."""
    appels = sum(1 for ligne in metriques if ligne.get("type") == "llm")
    tronquees = sum(
        1 for ligne in metriques if ligne.get("type") == "llm" and ligne.get("tronquee")
    )
    return "\n".join(
        [
            f"- appels au modèle : **{appels}**"
            + (f", dont {tronquees} tronqué(s) par la limite de sortie" if tronquees else ""),
            f"- tokens de prompt : **{sum(jeu.tokens_prompt for jeu in jeux)}**",
            f"- tokens générés : **{sum(jeu.tokens_generes for jeu in jeux)}**",
            f"- actions dépensées : **{sum(jeu.actions for jeu in jeux)}**",
            f"- tours joués : **{sum(jeu.tours for jeu in jeux)}**",
            f"- durée cumulée : **{formater(sum(jeu.secondes for jeu in jeux))} s**",
        ]
    )


def evenements(jeux: Sequence[ResultatJeu]) -> str:
    """Continuations, dépassements, interventions, versions committées (§A7.3)."""
    return "\n".join(
        [
            f"- continuations en contexte frais : **{sum(j.continuations for j in jeux)}**",
            f"- refus de contexte (HTTP 413) absorbés : **{sum(j.depassements for j in jeux)}**",
            f"- interventions du superviseur : **{sum(j.interventions for j in jeux)}**",
            f"- versions committées à la lignée : **{sum(j.versions_committees for j in jeux)}**",
            f"- parties perdues (game over) : **{sum(j.game_overs for j in jeux)}**",
        ]
    )


def comparaison(resultat: ResultatCampagne) -> str:
    """Situer le score, sans laisser croire à une comparaison qui n'en est pas une."""
    actions = sum(jeu.actions for jeu in resultat.jeux)
    lignes = [
        "| Source | RHAE | Actions |",
        "|---|---|---|",
        f"| **cette campagne** | **{formater(resultat.score_global)}** | **{actions}** |",
    ]
    lignes += [f"| {nom} | {formater(score)} | {total} |" for nom, score, total in REFERENCES]
    return "\n".join(lignes)


def limites(resultat: ResultatCampagne) -> str:
    """Ce que la campagne n'établit PAS. Un rapport muet là-dessus se lit comme un score."""
    points = []
    if resultat.mode != "live":
        points.append(
            "- Cette campagne s'est jouée en **mode rejeu**, sur le jeu synthétique local. "
            "Son score mesure le harnais, pas une performance sur ARC-AGI-3 : il n'est "
            "**pas comparable** aux références ci-dessus, qui portent sur l'ensemble public."
        )
    if resultat.card_id is None:
        points.append("- Aucun scorecard n'a été ouvert : rien n'a été publié.")
    else:
        points.append(f"- Scorecard de la campagne : `{resultat.card_id}`.")
    arrets = {jeu.arret for jeu in resultat.jeux if jeu.arret != "tours_epuises"}
    for arret in sorted(arrets):
        points.append(f"- Au moins un jeu s'est arrêté sur : {arret}.")
    incomplets = [jeu for jeu in resultat.jeux if jeu.niveaux_completes < len(jeu.niveaux)]
    if incomplets:
        noms = ", ".join(f"`{jeu.game_id}`" for jeu in incomplets)
        points.append(
            f"- Jeux non terminés : {noms}. Leur RHAE est plafonné par la complétion (§A6.1)."
        )
    return "\n".join(points) if points else "_Aucune limite particulière relevée._"


def sections(
    resultat: ResultatCampagne, metriques: Sequence[Mapping[str, Any]]
) -> list[tuple[str, str]]:
    """Les sections du rapport, dans l'ordre où elles se lisent (§A7.3)."""
    plafonds = resultat.plafonds
    entete = "\n".join(
        [
            f"- mode : **{resultat.mode}**",
            f"- score global (moyenne des RHAE de jeu) : **{formater(resultat.score_global)}**",
            f"- jeux joués : **{len(resultat.jeux)}**",
            f"- plafonds : {plafonds.actions_niveau} actions/niveau, "
            f"{plafonds.actions_jeu} actions/jeu, {plafonds.tours_max} tours max, "
            f"temps/jeu {plafonds.secondes_jeu or 'aucun'}, "
            f"tokens/jeu {plafonds.tokens_jeu or 'aucun'}",
        ]
    )
    return [
        ("Résultat", entete),
        ("Par jeu", table_par_jeu(resultat.jeux)),
        ("Détail par niveau", table_par_niveau(resultat.jeux)),
        ("Coûts", couts(resultat.jeux, metriques)),
        ("Événements", evenements(resultat.jeux)),
        ("Comparaison aux références publiées", comparaison(resultat)),
        ("Limites et écarts", limites(resultat)),
    ]


def ecrire(workspace: Workspace, resultat: ResultatCampagne) -> None:
    """Écrit `report.md` dans le workspace du run (§H6.1)."""
    workspace.ecrire_rapport(
        f"Campagne ARC-AGI-3 — {resultat.mode}",
        sections(resultat, workspace.lire_metriques()),
    )
