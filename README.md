# nvidia-ova-oss

Implémentation open source du harnais d'agent **AVO** (*Agentic Variation Operators*, NVIDIA Research) d'après sa spécification publiée, et évaluation de ce harnais sur des benchmarks au travers d'un endpoint d'inférence **compatible OpenAI**.

## Objectif

AVO est une architecture d'agent autonome longue-durée décrite par NVIDIA dans [arXiv:2603.24517](https://arxiv.org/abs/2603.24517) et démontrée à 100.00 RHAE sur l'ensemble public ARC-AGI-3 ([billet NVIDIA du 2026-08-21](https://developer.nvidia.com/blog/nvidia-avo-reaches-100-on-arc-agi-3-demonstrating-a-frontier-level-general-purpose-architecture-for-long-horizon-autonomous-agents/)). NVIDIA n'a pas publié le code du harnais : ce dépôt vise à en produire une implémentation ouverte, fidèle à la spécification, pilotant un LLM servi par une API compatible OpenAI, puis à l'évaluer sur des benchmarks de référence.

Les éléments constitutifs, tirés des sources exportées dans [`knowledge/`](knowledge/README.md) :

- boucle agent auto-dirigée **Planning → Implementation → Evaluation → Bug-Fixing** avec outils, mémoire et raisonnement ;
- entrée `Vary(Pₜ) = Agent(Pₜ, K, f)` : lignée complète des solutions, base de connaissances, fonction de score ;
- **mémoire persistante** (contexte accumulé des éditions, résultats et raisonnements) et lignée versionnée en git ;
- **agent superviseur** : surveillance de la stagnation et intervention conditionnelle ;
- interface de tâche ARC-AGI-3 de type « direct-interaction » (principes VISTA), observations texte 64×64.

## État actuel

**Phase de préparation — aucun code applicatif n'existe encore.**

- Fait : import des quatre sources de référence dans `knowledge/` (markdown + images + PDF), documentation projet initialisée.
- Fait : endpoint d'inférence fourni par le responsable, **testé et validé de bout en bout** le 2026-08-27 (authentification, tool calling, contexte long réellement exploité) ; le modèle de travail est `qwen3.6:35b`, seul modèle de complétion servi par cet endpoint. Mesures et contraintes qui en découlent : `docs/JOURNAL.md`, entrée du 2026-08-27 (suite 2).
- Décidé : le benchmark de référence est **ARC-AGI-3, ensemble public** (décision prise par défaut le 2026-08-27 au titre de `CLAUDE.md` §1, « Autonomie de décision » ; motif et options écartées dans `docs/JOURNAL.md`). Aucun autre benchmark n'entre dans le périmètre initial.
- Prochaine étape : spécification complète du harnais (`docs/`) avant toute ligne de code, conformément à `CLAUDE.md`.

## Stack

- Cible prévue : **Python** (conforme aux préférences du socle P2Enjoy pour l'IA/ML ; à confirmer dans la spécification, `docs/BACKLOG.md` U2).
- Aucune dépendance installée à ce stade.

## Prérequis

- Git.
- Python 3 (pour la phase d'implémentation à venir).
- Un endpoint d'inférence compatible OpenAI (URL + clé API) — fourni séparément, jamais committé.

## Commandes

Aucune commande de build, de test ou de lancement n'existe encore. Elles seront documentées ici dans le même commit que leur introduction.

## Variables d'environnement

Le harnais consommera l'endpoint d'inférence via ces variables, fournies hors dépôt (fichier `.env` local ignoré par git, ou environnement du shell). Aucune valeur réelle ni aucun secret n'est jamais committé.

| Variable | Rôle | Format attendu | Obligatoire | Exemple non sensible |
|---|---|---|---|---|
| `OLLAMA_HOST` | URL de base du serveur Ollama (surface compatible OpenAI sous `/v1`, API native sous `/api`) | URL `https://hôte[:port]` sans slash final | oui | `https://inference.example.com` |
| `OLLAMA_API_KEY` | Clé d'authentification, envoyée en `Authorization: Bearer …` | chaîne opaque | oui | `sk-ollama-xxxxxxxx` |
| `OLLAMA_CONTEXT_LENGTH` | Fenêtre de contexte demandée au serveur, en tokens (transmise en `options.num_ctx`) ; borne les budgets de contexte du harnais | entier | oui | `131072` |
| `ARC_API_KEY` | Clé d'accès à l'API ARC Prize (ARC-AGI-3), envoyée en en-tête `X-API-Key` ; donne accès aux environnements officiels et à l'ouverture des scorecards | UUID | oui pour l'évaluation ARC-AGI-3, inutile pour le reste du harnais | `00000000-0000-0000-0000-000000000000` |

Le plafond réellement applicable n'est pas cette variable seule : le proxy d'authentification impose une **limite de contexte par clé API**, qu'il publie dans le corps de sa réponse `HTTP 413` (`max_context_tokens`), et il compare à ce plafond une estimation **majorée de 15 %**. Le budget exploitable par le harnais vaut donc environ `max_context_tokens / 1,15`. Le `413` doit être traité comme un cas nominal (repli par compaction ou continuation en contexte frais), pas comme une erreur fatale ; son corps renvoie `tokens_estimated`, directement exploitable. Valeurs mesurées sur l'endpoint courant : `docs/JOURNAL.md`, entrée du 2026-08-27 (suite 2).

## Structure du dépôt

```text
.
├── CLAUDE.md            # contrat d'ingénierie global P2Enjoy (ne pas localiser)
├── CLAUDE_PROJECT.md    # règles propres à ce dépôt
├── README.md
├── CHANGELOG.md
├── docs/
│   ├── .routine         # entrée de la tâche planifiée (worker horaire)
│   ├── CloudWorker.md   # contrat d'exécution du worker planifié
│   ├── DAT.md           # dossier d'architecture technique (embryonnaire)
│   ├── BACKLOG.md       # unités de travail et statuts
│   ├── JOURNAL.md       # décisions et investigations
│   └── DESIGN_SYSTEM.md # socle UI global P2Enjoy (pas d'UI dans ce projet à ce stade)
└── knowledge/           # sources de référence exportées (voir knowledge/README.md)
```

## Limites connues

- Le harnais n'est pas implémenté : le dépôt ne contient que la connaissance de référence et la documentation de préparation.
- **Le préremplissage du contexte est le coût dominant de l'endpoint**, très loin devant la génération (débit mesuré le 2026-08-27 : voir `docs/JOURNAL.md`). Un harnais qui réémettrait l'historique complet à chaque tour serait inexploitable en temps sur un benchmark de plusieurs milliers d'actions : l'historique doit rester strictement append-only pour bénéficier du cache de préfixe.
- **Le budget de contexte utile est inférieur au plafond nominal** de la clé, à cause de la marge de 15 % appliquée par le proxy (voir « Variables d'environnement »).
- **Le modèle servi est un modèle à raisonnement** : le raisonnement consomme le budget de sortie avant tout contenu, et une valeur de `max_tokens` trop basse produit une réponse vide avec `finish_reason: length`. Politique à arrêter dans la spécification (budget large, ou raisonnement désactivé).
- **Évaluer, c'est publier** : l'API ARC Prize enregistre chaque partie dans un scorecard rattaché au compte porteur de la clé. Il n'existe pas de mode d'exécution officiel sans dépôt de résultat. Toute campagne engage donc le compte du responsable, et les exécutions d'essai doivent passer par l'environnement local de rejeu plutôt que par l'API.
- **Une campagne complète est hors de portée en une session** : 25 jeux, 183 niveaux, une référence humaine de 17 135 actions cumulées et des agents de référence autour de 7 000 actions, à combiner avec le coût de préremplissage de l'endpoint. Le périmètre d'une campagne (sous-ensemble de jeux, plafonds d'actions, budget de temps) est défini dans la spécification, jamais implicite.

## Origine

Dépôt initialisé depuis la base « P2Enjoy Software Factory » (conventions d'ingénierie, contrat de worker planifié, socle UI). Licence : [MPL-2.0](LICENSE).
