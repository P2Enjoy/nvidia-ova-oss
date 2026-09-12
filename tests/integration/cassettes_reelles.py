"""Épinglage des rejeux sur cassettes ENREGISTRÉES contre l'endpoint réel.

@spec docs/BACKLOG.md U36 — socle de mesure sous le modèle de travail (§H4.7)
@spec docs/SPEC_HARNAIS.md §H4.7 (rejeu des échanges réels, appariement par hachage)

Une cassette enregistrée est un artefact de SON environnement d'enregistrement :
le corps rejoué doit hacher à l'identique, indépendamment des défauts courants du
harnais (§H3.1). Tout test qui rejoue une cassette enregistrée étale donc ce
dictionnaire dans son environnement de configuration — il épingle explicitement
l'environnement sous lequel `make record-llm` a produit les cassettes courantes
(re-enregistrées sous le modèle de travail et les défauts §H3.1, backlog U36),
et se met à jour dans le même changement que tout re-enregistrement futur.
"""

from __future__ import annotations

ENV_CASSETTES_REELLES: dict[str, str] = {
    "AVO_MODEL": "qwen3.8:27b",
    "AVO_TOP_P": "0.8",
    "AVO_PRESENCE_PENALTY": "1.5",
    "AVO_TOP_K": "aucun",
    "AVO_MIN_P": "aucun",
    "AVO_REPEAT_PENALTY": "aucun",
}
