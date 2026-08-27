# Dossier d'architecture technique (DAT)

> État : embryonnaire. Aucun code applicatif n'existe encore ; ce document sera complété par l'unité U2 (`docs/BACKLOG.md`) — la spécification du harnais — avant toute implémentation.

## Objet du système

Harnais d'agent AVO (Agentic Variation Operators) : implémentation open source de l'architecture décrite dans `knowledge/arxiv-2603.24517-avo-agentic-variation-operators.md`, pilotant un LLM servi par un endpoint compatible OpenAI, évaluée sur des benchmarks (ARC-AGI-3 en premier lieu).

## Composants prévus (à spécifier en U2)

- **Agent principal** : boucle Planning → Implementation → Evaluation → Bug-Fixing ; outils (édition, exécution, consultation de la base de connaissances) ; mémoire persistante.
- **Lignée de solutions** `Pₜ` : paires (solution, score) persistées en git, une version committée seulement si correcte et au moins égale au meilleur score.
- **Base de connaissances** `K` : documents de référence propres à la tâche.
- **Fonction de score** `f` : vecteur par configuration de test ; zéro si la correction échoue.
- **Superviseur** : détection de stagnation, intervention conditionnelle.
- **Client d'inférence** : API compatible OpenAI (URL, clé, modèle par variables d'environnement) avec timeout, retry contrôlé, journalisation sans secret.
- **Interface de benchmark** : ARC-AGI-3 direct-interaction en grilles texte 64×64 (principes VISTA, cf. `knowledge/`), calcul RHAE.

## Décisions déjà actées

- Aucune ligne de code avant la spécification committée (CLAUDE.md §5).
- Stack pressentie : Python (préférence du socle pour l'IA/ML) — à confirmer en U2.
- Les secrets (clé API) ne sont jamais committés ; configuration par variables d'environnement documentées.

## Flux, modèles de données, déploiement, reprise

À définir en U2.
