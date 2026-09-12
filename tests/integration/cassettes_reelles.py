"""Épinglage des rejeux sur cassettes ENREGISTRÉES contre l'endpoint réel.

@spec docs/BACKLOG.md U33 — bascule du modèle de travail et échantillonnage (§H3.1)
@spec docs/SPEC_HARNAIS.md §H4.7 (rejeu des échanges réels, appariement par hachage)

Ces cassettes sont des artefacts historiques du modèle `qwen3.6:35b`, enregistrées
sans paramètre d'échantillonnage dans `options` : le corps rejoué doit hacher à
l'identique, indépendamment des défauts courants du harnais (§H3.1). Tout test qui
rejoue une cassette enregistrée étale ce dictionnaire dans son environnement de
configuration. Levée prévue au re-enregistrement sous le modèle de travail
(backlog U36).
"""

from __future__ import annotations

ENV_CASSETTES_REELLES: dict[str, str] = {
    "AVO_MODEL": "qwen3.6:35b",
    "AVO_TOP_P": "aucun",
    "AVO_PRESENCE_PENALTY": "aucun",
}
