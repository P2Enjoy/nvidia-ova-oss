# Journal du projet

Trace chronologique des décisions et investigations significatives. La dernière entrée dit toujours où reprendre.

---

## 2026-08-27 — Étude des sources, import dans `knowledge/`, préparation du travail sur le harnais AVO

**Contexte.** Session interactive demandée par le responsable, sur la branche désignée `claude/avo-harness-implementation-ufsb43`. Mission énoncée : (1) lire et exporter dans `knowledge/` (markdown + images) les quatre sources qui définissent l'objet du dépôt ; (2) se préparer à implémenter le harnais AVO d'après la spécification du papier et à l'évaluer sur des benchmarks via un endpoint compatible OpenAI dont l'URL et la clé API seront fournies ultérieurement. Aucun code à écrire à ce stade.

**Problème.** Le dépôt était la base « software factory » vierge (un seul commit) : aucun contenu projet, la finalité n'existait que dans l'énoncé de mission. Une décision non persistée étant une décision perdue, tout ce qui a été appris et décidé ici est écrit dans le dépôt.

**Observations (étude des sources).**

- **AVO** (arXiv:2603.24517, NVIDIA) est la spécification à implémenter : un opérateur de variation agentique pour la recherche évolutionnaire, `Vary(Pₜ) = Agent(Pₜ, K, f)`. Boucle interne Planning → Implementation → Evaluation → Bug-Fixing ; agent de codage généraliste avec outils (édition de code, shell, navigation fichiers, consultation de documentation), mémoire persistante par historique de conversation ; lignée single-lineage où chaque version validée (correcte ET au moins aussi bonne que le meilleur score committé) devient un commit git avec son score ; **superviseur** séparé qui détecte stagnation/cycles improductifs et redirige la recherche (intervention conditionnelle). Le papier démontre AVO sur l'optimisation de kernels d'attention B200 ; l'architecture est explicitement indépendante du domaine.
- **Blog NVIDIA (2026-08-21)** : la même architecture appliquée à ARC-AGI-3 fait 100.00 RHAE (25 jeux publics, 183 niveaux, 6 624 actions, Claude Opus 5). Configuration décisive pour nous : interface de tâche réimplémentée **selon les principes direct-interaction de VISTA**, mais en **texte seul** — chaque observation est la grille 64×64 exacte, aucune image envoyée au modèle ; actions disponibles fournies sans description des règles ni du but. AVO est annoncé multi-modèles (démonstrations Opus 5 et GPT-5.6 Sol).
- **VISTA** (MIT) : harnais minimaliste sans synthèse de programme — perception (PNG 512×512 ou grille texte), raisonnement en langage libre, mémoire visuelle sans perte (`inspect`, `read_pixels`), notes `GUIDE.md`/`WORKING.md`, continuation en contexte frais à l'approche de la limite de contexte. Le prompt agent complet est dans l'export. Résultats par jeu et par niveau exportés (Opus 5.0 : 100.00 RHAE, 7 542 actions).
- **Tycho** (NIMI) : l'approche concurrente par modèles du monde programmatiques (que NVIDIA n'a pas retenue). Précieux pour nous : formalisation propre d'ARC-AGI-3 (machines de Moore rendues, protocole de score, **définition exacte de RHAE** : eₗ = min(115, 100·(hₗ/aₗ)²) si complété, pondération wₗ = ℓ, plafonnement par la complétion), comparaison de quatre politiques d'orchestration, surface d'outils et extraits de prompts, diagnostics et coûts d'inférence.

**Décisions.**

1. `knowledge/` est le dossier de référence : quatre exports markdown autoporteurs, images sous `knowledge/images/<source>/`, PDF d'origine sous `knowledge/pdf/`, index `knowledge/README.md` avec provenance et synthèse. Les exports sont des instantanés en lecture seule.
2. Figures des PDF extraites par recadrage ancré sur les légendes (script reproductible en session) ; les valeurs numériques des graphiques à barres du papier AVO ont été reconstruites en tableaux sous les figures, vérifiées contre les pourcentages annoncés dans le texte.
3. Les vidéos `.mp4` de la page VISTA ne sont pas mises en miroir (la demande porte sur markdown + images) ; l'export garde des liens absolus vers le site.
4. Documentation projet initialisée (README réécrit, CHANGELOG, BACKLOG, DAT embryonnaire, CLAUDE_PROJECT.md) ; le plan de travail vit dans `docs/BACKLOG.md`, pas dans la mémoire de session.
5. Aucune ligne de code du harnais avant la spécification écrite et committée (unité U2), conformément à `CLAUDE.md` §5.

**Vérifications réalisées.** Les 4 URL ont répondu 200 et les contenus téléchargés correspondent (titres, auteurs, chiffres croisés entre sources : les actions AVO/VISTA/Tycho citées par le blog concordent avec les exports). Tous les liens d'images relatifs des markdown de `knowledge/` résolvent vers un fichier existant (vérification scriptée). Les recadrages de figures ont été inspectés visuellement (fig. 1–2 AVO, fig. 1 et 12 Tycho lisibles et complets).

**En attente du responsable (bloquant pour la suite).**

- URL de l'endpoint compatible OpenAI, clé API, **nom du modèle** à utiliser.
- Confirmation du périmètre « common benchmarks » : ARC-AGI-3 est le benchmark central des sources (nécessite l'API ARC Prize pour un scorecard officiel) ; préciser s'il faut d'autres benchmarks (par ex. SWE-bench-like, optimisation de code) et lesquels sont accessibles depuis cet environnement.

**Où reprendre.** Unité U2 du backlog : rédiger la spécification complète du harnais (architecture, contrat de configuration par variables d'environnement, interface de tâche, protocole d'évaluation, plan de tests) dans `docs/`, la committer, PUIS seulement commencer le code (U3+), une fois l'endpoint fourni.
