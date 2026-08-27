# CLAUDE_PROJECT.md — Règles locales du dépôt nvidia-ova-oss

Complément local de `CLAUDE.md` (qui reste global et prime pour les exigences de qualité).

## Objet du dépôt

Implémentation open source du harnais d'agent **AVO** (papier arXiv:2603.24517) et son évaluation sur des benchmarks via un endpoint d'inférence **compatible OpenAI**. L'endpoint (URL), la clé API et le nom du modèle sont fournis par le responsable hors dépôt ; ils ne sont **jamais** committés.

## Sources de référence

- `knowledge/` contient les exports fidèles des quatre sources (papier AVO, blog NVIDIA, page VISTA, papier Tycho) avec images et PDF. **Lire `knowledge/README.md` avant tout travail sur le harnais.**
- Ces exports sont des instantanés en lecture seule : ne pas les modifier à la main ; en cas de divergence avec la source, re-générer l'export et le consigner dans `docs/JOURNAL.md`.
- En cas de doute d'interprétation, le PDF sous `knowledge/pdf/` fait foi.

## Conventions locales

- Documentation projet en français ; les exports de `knowledge/` conservent le texte original anglais sous un en-tête de provenance français.
- L'état réel du travail vit dans `docs/BACKLOG.md` (unités U1–U6) et `docs/JOURNAL.md` (dernière entrée = point de reprise). Les relire en début de session.
- Aucune ligne de code du harnais tant que la spécification (unité U2) n'est pas écrite et committée.
- `docs/.routine` et `docs/CloudWorker.md` sont le contrat de la tâche planifiée (worker horaire sur `main`) hérité de la base factory ; une session interactive travaille sur la branche que le responsable lui désigne.

## Terminologie

- **AVO** : Agentic Variation Operators — l'architecture à implémenter.
- **VISTA** : harnais visuel MIT dont AVO reprend les principes « direct-interaction » pour ARC-AGI-3.
- **Tycho** : approche par modèles du monde programmatiques ; source de la formalisation ARC-AGI-3 et de la définition RHAE.
- **RHAE** : Relative Human Action Efficiency, métrique officielle ARC-AGI-3 (définition exacte dans l'export Tycho, §3.1).
