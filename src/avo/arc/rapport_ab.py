"""Rapport comparatif A/B des deux modes de contexte, sur rejeu (U27).

@spec docs/BACKLOG.md U27 — A/B sur rejeu : mode `transcript` (H5) vs mode `state` (H15)
@spec docs/SPEC_HARNAIS.md §H15.0 (le départage se fait par la mesure, jamais sur le
      papier), §H15.4/§H15.8 (retries de patch, mode `state` seulement)
@spec docs/SPEC_ARCAGI3.md §A7.3 (contenu d'un rapport de campagne, principe réutilisé)

Fonction **pure**, comme `avo.arc.rapport` : elle ne rejoue rien et ne devine aucun
chiffre. Les deux campagnes comparées sont jouées séparément, par la CLI réelle, sur
le MÊME jeu et les MÊMES plafonds — seul `AVO_CONTEXT_MODE` diffère entre les deux
(`scripts/generer_rapport_ab.py`, ou le test E2E qui rejoue l'A/B et relit ce rapport).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from avo.arc.campagne import ResultatJeu
from avo.arc.rapport import formater


@dataclass(frozen=True)
class MesureMode:
    """Ce qu'une mini-campagne mono-mode apporte à la comparaison A/B."""

    mode_contexte: str
    jeux: Sequence[ResultatJeu]
    metriques: Sequence[Mapping[str, Any]]

    @property
    def rhae_moyen(self) -> float:
        return sum(j.rhae.valeur for j in self.jeux) / len(self.jeux) if self.jeux else 0.0

    @property
    def actions(self) -> int:
        return sum(j.actions for j in self.jeux)

    @property
    def tokens(self) -> int:
        return sum(j.tokens for j in self.jeux)

    @property
    def appels(self) -> int:
        """Nombre d'appels au modèle — même définition que `avo.arc.rapport.couts`."""
        return sum(1 for ligne in self.metriques if ligne.get("type") == "llm")

    @property
    def taille_moyenne_prompt(self) -> float:
        return sum(j.tokens_prompt for j in self.jeux) / self.appels if self.appels else 0.0

    @property
    def retries_patch(self) -> int:
        return sum(j.retries_patch for j in self.jeux)


def table(transcript: MesureMode, etat: MesureMode) -> str:
    """Une ligne par mesure nommée dans le backlog U27 (RHAE, actions, tokens
    cumulés, taille moyenne de prompt, retries)."""
    return "\n".join(
        [
            "| Mesure | `transcript` | `state` |",
            "|---|---|---|",
            f"| RHAE moyen | {formater(transcript.rhae_moyen)} | {formater(etat.rhae_moyen)} |",
            f"| Actions | {transcript.actions} | {etat.actions} |",
            f"| Appels au modèle | {transcript.appels} | {etat.appels} |",
            f"| Tokens cumulés | {transcript.tokens} | {etat.tokens} |",
            "| Taille moyenne de prompt (tokens) "
            f"| {formater(transcript.taille_moyenne_prompt)} "
            f"| {formater(etat.taille_moyenne_prompt)} |",
            f"| Retries de patch | {transcript.retries_patch} | {etat.retries_patch} |",
        ]
    )


def rapport(transcript: MesureMode, etat: MesureMode) -> str:
    """Rapport markdown complet, committé sous `docs/rapports/` (U27)."""
    if transcript.mode_contexte != "transcript" or etat.mode_contexte != "state":
        raise ValueError(
            "rapport() attend (mesure « transcript », mesure « state »), dans cet ordre"
        )
    return "\n\n".join(
        [
            "# A/B des deux modes de contexte, sur rejeu (U27)",
            (
                "Comparaison du mode `transcript` (§H5, historique complet renvoyé à chaque "
                "segment) et du mode `state` (§H15, état structuré Σ recomposé en `O(1)` par "
                "tour) sur le jeu synthétique local `cible-synthetique`, mêmes plafonds, mode "
                "rejeu — aucun secret requis, rien n'est publié."
            ),
            table(transcript, etat),
            (
                "Lecture : un nombre d'appels ou un budget de tokens moindre en `state` "
                "reflète le contrat `O(1)` par tour (§H15.1) plutôt que l'historique cumulé de "
                "`transcript` ; un RHAE et un nombre d'actions comparables signifient que le "
                "changement de mode ne dégrade pas la partie jouée. Des retries de patch non "
                "nuls sont attendus du seul mode `state` (§H15.4) — `transcript` ne décode "
                "aucun patch."
            ),
            (
                "Limite : mesure sur rejeu local uniquement (jeu synthétique, réponses "
                "scriptées) — le départage en conditions réelles (endpoint et cache de "
                "préfixe réels, coût observé) reste le périmètre de U28 (`[LIVE]`, en session "
                "interactive, avec le responsable). En particulier, le rejoueur HTTP répond "
                "verbatim les `prompt_eval_count`/`eval_count` enregistrés une seule fois "
                "(§H4.7) : la « taille moyenne de prompt » ci-dessus est donc identique pour "
                "les deux modes par construction du rejeu, et ne dit rien de la croissance "
                "réelle du prompt en `transcript` face au `O(1)` de `state` (§H15.1) — c'est "
                "le nombre d'appels au modèle qui porte ce signal ici, pas la taille par appel."
            ),
        ]
    )
