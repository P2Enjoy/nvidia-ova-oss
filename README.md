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
- En attente d'une action humaine : URL de l'endpoint compatible OpenAI, clé API et nom du modèle à utiliser (annoncés par le responsable, non encore fournis), et confirmation de la liste des benchmarks visés.
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
| `OLLAMA_CONTEXT_LENGTH` | Fenêtre de contexte configurée côté serveur, en tokens ; borne les budgets de contexte du harnais | entier | oui | `114688` |

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
- L'endpoint d'inférence fourni le 2026-08-27 est sain (vérifié depuis des points de mesure externes) mais **injoignable depuis l'environnement d'exécution**, dont la sortie réseau n'autorise le TLS que vers le port 443 alors que l'endpoint écoute sur un port non standard. Diagnostic complet et options de déblocage : `docs/JOURNAL.md`, entrée du 2026-08-27 (suite). Nécessite une action humaine.
- Le nom du modèle à utiliser n'est pas encore confirmé par le responsable.
- L'évaluation ARC-AGI-3 officielle suppose un accès à l'API ARC Prize (scorecards) ; cette dépendance sera traitée dans la spécification.

## Origine

Dépôt initialisé depuis la base « P2Enjoy Software Factory » (conventions d'ingénierie, contrat de worker planifié, socle UI). Licence : [MPL-2.0](LICENSE).
