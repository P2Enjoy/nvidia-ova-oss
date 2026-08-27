# knowledge/ — Sources de référence du projet

Ce dossier contient l'export local, fidèle et hors-ligne des sources qui définissent l'objet de ce dépôt : implémenter en open source le harnais d'agent **AVO** (Agentic Variation Operators, NVIDIA) d'après la spécification publiée, puis l'évaluer sur des benchmarks au travers d'un endpoint d'inférence compatible OpenAI.

Chaque export est un fichier Markdown autoporteur, avec ses images sous `images/<source>/` et, pour les papiers, le PDF d'origine sous `pdf/`. L'en-tête de chaque fichier documente l'URL source, les auteurs, la date de publication et la date de récupération (2026-08-27).

## Sources exportées

| Fichier | Source | Contenu |
|---|---|---|
| [`nvidia-avo-arc-agi-3-blog.md`](nvidia-avo-arc-agi-3-blog.md) | [NVIDIA Technical Blog, 2026-08-21](https://developer.nvidia.com/blog/nvidia-avo-reaches-100-on-arc-agi-3-demonstrating-a-frontier-level-general-purpose-architecture-for-long-horizon-autonomous-agents/) | Annonce : AVO atteint 100.00 RHAE sur l'ensemble public ARC-AGI-3 (25 jeux, 183 niveaux, 6 624 actions) avec Claude Opus 5. Décrit l'architecture (boucle agent + mémoire persistante + superviseur) et la configuration ARC-AGI-3 (observations texte 64×64, principes « direct-interaction » repris de VISTA). |
| [`arxiv-2603.24517-avo-agentic-variation-operators.md`](arxiv-2603.24517-avo-agentic-variation-operators.md) | [arXiv:2603.24517](https://arxiv.org/abs/2603.24517) (NVIDIA, 25 mars 2026) | **Le papier AVO — la spécification de référence du harnais à implémenter.** Formalisation Vary(Pₜ) = Agent(Pₜ, K, f) ; anatomie d'un pas de variation (Planning → Implementation → Evaluation → Bug-Fixing) ; évolution continue single-lineage avec commits git ; superviseur anti-stagnation. Démonstration : optimisation de kernels d'attention sur B200 (bat cuDNN et FlashAttention-4). |
| [`vista-research-project-page.md`](vista-research-project-page.md) | [vista-research.github.io](https://vista-research.github.io/) (MIT, 5 août 2026) | **VISTA, le harnais « direct-interaction » dont AVO reprend l'interface de tâche ARC-AGI-3.** Perception visuelle (PNG 512×512, variantes grille texte et 3D), raisonnement en langage libre, mémoire visuelle sans perte (`inspect`, `read_pixels`), notes `GUIDE.md`/`WORKING.md`, prompt agent complet, résultats par jeu et par niveau (Opus 5.0 : 100.00 RHAE en 7 542 actions ; GPT-5.6 Sol : 98.27). |
| [`arxiv-2607.28287-tycho-programmatic-world-models.md`](arxiv-2607.28287-tycho-programmatic-world-models.md) | [arXiv:2607.28287](https://arxiv.org/abs/2607.28287) (NIMI Research Group, 30 juillet 2026) | **Tycho, l'approche alternative par modèles du monde programmatiques** (que AVO n'a volontairement pas retenue). Formalisation d'ARC-AGI-3 en machines de Moore déterministes rendues ; quatre politiques d'orchestration (no-model / single / orchestrator / trigger) ; définition de la métrique RHAE ; surface d'outils et prompts acteur/constructeur ; 100.00 RHAE avec GPT-5.6 Sol (7 766 actions) et Opus 5 (6 641 actions). |

## Ce que ces sources établissent pour le dépôt

1. **Le harnais compte autant que le modèle.** Le même modèle passe de 1,5–30 RHAE (interface minimale officielle) à 100 RHAE selon le système d'agent qui l'entoure. Ce dépôt implémente le système, le modèle étant fourni par un endpoint compatible OpenAI.
2. **L'architecture AVO à reproduire** (papier §3, figure 2) : un agent de codage généraliste auto-dirigé qui reçoit la lignée complète des solutions $P_t$, une base de connaissances $K$ et une fonction de score $f$ ; boucle interne Planning → Implementation → Evaluation → Bug-Fixing ; persistance de chaque version validée en commit git ; **superviseur** qui surveille la stagnation et intervient conditionnellement ; mémoire persistante portant les résultats, sorties de profils et raisonnements accumulés.
3. **La configuration ARC-AGI-3 d'AVO** (blog) : interface de tâche réimplémentée indépendamment selon les principes direct-interaction de VISTA ; observations **texte uniquement, grilles 64×64 exactes** (pas d'images) ; actions disponibles fournies sans description des règles ni du but ; métrique RHAE officielle (définie précisément dans l'export Tycho, §3.1).
4. **Les points de comparaison** : AVO 100.00 RHAE / 6 624 actions ; VISTA (Opus 5.0) 100.00 / 7 542 ; Tycho (Opus 5) 100.00 / 6 641 ; Tycho (GPT-5.6 Sol) 100.00 / 7 766 ; plus le tableau système complet (Schema, Retrodict, ewma_sv, PRO-LONG, etc.) dans les exports VISTA et Tycho.

## Contenu annexe

- `pdf/` — les deux PDF arXiv d'origine (référence faisant foi en cas de doute sur l'export).
- `images/` — figures extraites des PDF (recadrées depuis les pages) et images miroirs des pages web. Les vidéos `.mp4` de la page VISTA ne sont pas mises en miroir ; l'export pointe vers le site d'origine.

Ces exports sont des instantanés en lecture seule : ne pas les « corriger » ; toute divergence constatée avec la source se traite en re-générant l'export et en le documentant dans `docs/JOURNAL.md`.
