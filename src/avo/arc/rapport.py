"""Rapport de campagne : ce que la campagne a fait, et ce qu'elle n'établit pas.

@spec docs/BACKLOG.md U23 — Runner de campagne et rapport
@spec docs/SPEC_ARCAGI3.md §A7.3 (contenu du rapport), §A7.4 (le rapport est une
      fonction pure du résultat et des métriques), §A6 (RHAE)
@spec docs/SPEC_HARNAIS.md §H6.1 (`report.md` dans le workspace), §H11.2 (métriques)
@spec docs/BACKLOG.md U34 — ligne des résumés de coupure dans les événements (§H17.5)
@spec docs/BACKLOG.md U37 — lignes des idéations et curations dans les événements (§H18.5)
@spec docs/BACKLOG.md U31 — section « Inférence par appel et cache de préfixe » calculée
      depuis les métriques `llm`, `prefixe_pas` et `garde` (§A7.3, §H11.2) ; répartition
      des verdicts de la garde d'évaluation (§A7.3, §H16.5)

Fonction **pure** : elle ne rejoue rien, n'interroge aucun service et ne devine
aucun chiffre. Tout ce qu'elle écrit vient du résultat de campagne ou des métriques
que le run a réellement produites — ce qui est absent est dit absent.
"""

from __future__ import annotations

import statistics
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


def couts(
    jeux: Sequence[ResultatJeu],
    metriques: Sequence[Mapping[str, Any]],
    jeux_refuses: int = 0,
) -> str:
    """Tokens, durées, actions — les lignes d'inférence viennent des métriques (§A7.3).

    Les métriques du run couvrent TOUS les jeux, ceux clos en échec nommé compris
    (§A7.4) : un jeu refusé en cours de partie a réellement dépensé ses tokens, et
    les compter à zéro mentirait. Les lignes de partie (actions, tours, durée de
    jeu) restent celles des jeux menés à leur terme, et l'écart est nommé.
    """
    lignes_llm = [ligne for ligne in metriques if ligne.get("type") == "llm"]
    appels = len(lignes_llm)
    tronquees = sum(1 for ligne in lignes_llm if ligne.get("tronquee"))
    tokens_prompt = sum(int(ligne.get("tokens_prompt", 0)) for ligne in lignes_llm)
    tokens_generes = sum(int(ligne.get("tokens_generes", 0)) for ligne in lignes_llm)
    duree_inference = sum(float(ligne.get("duree_ms", 0)) for ligne in lignes_llm) / 1000.0
    lignes = [
        f"- appels au modèle : **{appels}**"
        + (f", dont {tronquees} tronqué(s) par la limite de sortie" if tronquees else ""),
        f"- tokens de prompt : **{tokens_prompt}**",
        f"- tokens générés : **{tokens_generes}**",
        f"- durée d'inférence cumulée : **{formater(duree_inference)} s**",
        f"- actions dépensées : **{sum(jeu.actions for jeu in jeux)}**",
        f"- tours joués : **{sum(jeu.tours for jeu in jeux)}**",
        f"- durée cumulée de jeu : **{formater(sum(jeu.secondes for jeu in jeux))} s**",
    ]
    if jeux_refuses:
        lignes.append(
            "- les lignes d'inférence couvrent tous les jeux, refusés compris ; "
            f"actions, tours et durée de jeu ne comptent que les {len(jeux)} jeu(x) "
            "mené(s) à terme (§A7.3)"
        )
    return "\n".join(lignes)


ORDRE_DIVERGENCES = ("tete", "notes", "observation", "etat", "protocole", "aucune", "premier")


def inference_par_appel(metriques: Sequence[Mapping[str, Any]]) -> str:
    """Lectures par appel et cache de préfixe, depuis les métriques du run (§A7.3, §H11.2).

    Des lectures, jamais des décisions. Une famille de métriques absente se dit
    « aucune » plutôt que zéro : un zéro se lirait comme une mesure.
    """
    llm = [ligne for ligne in metriques if ligne.get("type") == "llm"]
    lignes: list[str] = []
    if not llm:
        lignes.append("- appels au modèle : aucune métrique `llm`")
    else:
        generes = [int(ligne.get("tokens_generes", 0)) for ligne in llm]
        durees = [float(ligne.get("duree_ms", 0)) / 1000.0 for ligne in llm]
        prefills = [
            float(ligne["prefill_ms"]) / 1000.0
            for ligne in llm
            if ligne.get("prefill_ms") is not None
        ]
        generation_ms = sum(
            float(ligne.get("generation_ms") or 0)
            for ligne in llm
            if ligne.get("generation_ms") is not None
        )
        lignes.append(
            f"- tokens générés par appel : moyenne **{formater(statistics.mean(generes))}**, "
            f"maximum **{max(generes)}**"
        )
        lignes.append(
            f"- durée serveur par appel : moyenne **{formater(statistics.mean(durees))} s**"
        )
        if prefills:
            moyenne_prefill = formater(statistics.mean(prefills))
            mediane_prefill = formater(statistics.median(prefills))
            lignes.append(
                f"- préremplissage (`prefill_ms`) : moyenne **{moyenne_prefill} s**, "
                f"médiane **{mediane_prefill} s** sur {len(prefills)} appel(s)"
            )
        else:
            lignes.append("- préremplissage (`prefill_ms`) : aucune métrique")
        if generation_ms > 0:
            debit = formater(sum(generes) / (generation_ms / 1000.0))
            lignes.append(f"- débit de génération : **{debit} tokens/s**")
        else:
            lignes.append("- débit de génération : aucune métrique `generation_ms`")
    prefixes = [ligne for ligne in metriques if ligne.get("type") == "prefixe_pas"]
    if not prefixes:
        lignes.append("- messages de pas composés (`prefixe_pas`) : aucune métrique")
    else:
        comptes = {nom: 0 for nom in ORDRE_DIVERGENCES}
        for ligne in prefixes:
            comptes[str(ligne.get("divergence"))] = comptes.get(str(ligne.get("divergence")), 0) + 1
        repartition = ", ".join(f"{nom} {compte}" for nom, compte in comptes.items() if compte)
        parts = [
            100.0 * float(ligne.get("prefixe_commun", 0)) / float(ligne["caracteres"])
            for ligne in prefixes
            if ligne.get("divergence") != "premier" and float(ligne.get("caracteres", 0)) > 0
        ]
        lignes.append(
            f"- messages de pas composés (`prefixe_pas`) : **{len(prefixes)}** — "
            f"divergence : {repartition}"
        )
        if parts:
            lignes.append(
                f"- part médiane du préfixe commun : **{formater(statistics.median(parts))} %**"
            )
    gardes = [ligne for ligne in metriques if ligne.get("type") == "garde"]
    if not gardes:
        lignes.append("- gardes d'évaluation : aucune métrique")
    else:
        compte = {
            issue: sum(1 for ligne in gardes if ligne.get("issue") == issue)
            for issue in ("confirmee", "contredite", "forcee", "caduque", "redemandee")
        }
        # §H16.5 : l'issue prudente est une contradiction réputée — elle compte
        # parmi les contredites et se nomme à part.
        lignes.append(
            f"- gardes : verdicts confirmées **{compte['confirmee']}**, "
            f"contredites **{compte['contredite'] + compte['forcee']}** "
            f"(dont forcées **{compte['forcee']}**), caduques **{compte['caduque']}**, "
            f"redemandes **{compte['redemandee']}**"
        )
    return "\n".join(lignes)


def evenements(jeux: Sequence[ResultatJeu]) -> str:
    """Continuations, dépassements, interventions, versions committées (§A7.3)."""
    return "\n".join(
        [
            f"- continuations en contexte frais : **{sum(j.continuations for j in jeux)}**",
            f"- refus de contexte (HTTP 413) absorbés : **{sum(j.depassements for j in jeux)}**",
            f"- interventions du superviseur : **{sum(j.interventions for j in jeux)}**",
            f"- versions committées à la lignée : **{sum(j.versions_committees for j in jeux)}**",
            f"- résumés de coupure injectés (§H17) : **{sum(j.resumes_coupure for j in jeux)}**",
            f"- pas d'idéation d'ouverture (§H18) : **{sum(j.ideations for j in jeux)}**",
            f"- curations du ledger appliquées (§H18) : **{sum(j.curations for j in jeux)}**",
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
            f"- jeux joués : **{len(resultat.jeux)}**"
            + (
                f" — jeux refusés par le backend : **{len(resultat.refus)}**"
                if resultat.refus
                else ""
            ),
            f"- plafonds : {plafonds.actions_niveau} actions/niveau, "
            f"{plafonds.actions_jeu} actions/jeu, {plafonds.tours_max} tours max, "
            f"temps/jeu {plafonds.secondes_jeu or 'aucun'}, "
            f"tokens/jeu {plafonds.tokens_jeu or 'aucun'}",
        ]
    )
    sections_rapport = [
        ("Résultat", entete),
        ("Par jeu", table_par_jeu(resultat.jeux)),
        ("Détail par niveau", table_par_niveau(resultat.jeux)),
        ("Coûts", couts(resultat.jeux, metriques, jeux_refuses=len(resultat.refus))),
        ("Inférence par appel et cache de préfixe", inference_par_appel(metriques)),
        ("Événements", evenements(resultat.jeux)),
        ("Comparaison aux références publiées", comparaison(resultat)),
        ("Limites et écarts", limites(resultat)),
    ]
    if resultat.refus:
        # Un refus n'est jamais un saut silencieux (§A1.4, §A7.4) : le rapport le
        # remonte avec son motif, hors score.
        lignes_refus = "\n".join(
            f"- `{entree['jeu']}` : {entree['motif']}" for entree in resultat.refus
        )
        sections_rapport.insert(2, ("Jeux refusés par le backend (hors score)", lignes_refus))
    return sections_rapport


def ecrire(workspace: Workspace, resultat: ResultatCampagne) -> None:
    """Écrit `report.md` dans le workspace du run (§H6.1)."""
    workspace.ecrire_rapport(
        f"Campagne ARC-AGI-3 — {resultat.mode}",
        sections(resultat, workspace.lire_metriques()),
    )
