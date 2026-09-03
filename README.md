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

**Implémentation avancée — lots A à D livrés en entier, lot E livré jusqu'au RHAE, runner de campagne livré.**

- Fait : import des cinq sources de référence dans `knowledge/` (markdown + images + PDF) — papier AVO, billet NVIDIA, page VISTA, papier Tycho, papier SKILL.state (arXiv:2608.26263, ajouté le 2026-08-30).
- Fait : endpoint d'inférence fourni par le responsable, **testé et validé de bout en bout** le 2026-08-27 (authentification, tool calling, contexte long réellement exploité) ; le modèle de travail est `qwen3.6:35b`, seul modèle de complétion servi par cet endpoint. Mesures et contraintes qui en découlent : `docs/JOURNAL.md`, entrée du 2026-08-27 (suite 2).
- Décidé : le benchmark de référence est **ARC-AGI-3, ensemble public** (décision prise par défaut le 2026-08-27 au titre de `CLAUDE.md` §1, « Autonomie de décision » ; motif et options écartées dans `docs/JOURNAL.md`). Aucun autre benchmark n'entre dans le périmètre initial ; les benchmarks interactifs du papier SKILL.state sont consignés comme extension possible, en attente d'arbitrage (`docs/BACKLOG.md`, U29).
- Fait : **spécification complète écrite et committée** — `docs/SPEC_HARNAIS.md` (noyau agent, H1–H14), `docs/SPEC_ARCAGI3.md` (interface et évaluation, A1–A8), `docs/SPEC_BANCS.md` (bancs d'affinage, S1+), `docs/MASTER_PLAN.md` (ordre d'exécution, DoD commune), backlog en unités d'une session, chacune portant ses références de spécification et ses preuves.
- Fait : **unités U3 à U21 et U23 à U27 livrées et vérifiées** (socle conteneurisé, client d'inférence sur cassettes réelles, contexte et notes, outils et boucle P→I→E→B, lignée et superviseur, rejeu ARC local et jeu `cible`, client API ARC, rendu et mémoire de frames, interface direct-interaction, RHAE, runner de campagne `run-arc`/`resume` avec rapport, E2E de partie complète sur rejeu, mode d'exécution `state` de la boucle H15 et son A/B contre `transcript` — `docs/rapports/ab_mode_contexte.md`). Campagne de preuves : 599 tests verts (467 unitaires, 132 d'intégration, 4 E2E), lint, format, mypy strict.
- Fait : **U22 (sonde de contrat API officielle) livrée le 2026-08-31.** Le format de fil réel de l'API ARC-AGI-3 est mesuré (scorecard de sonde étiqueté `probe`, capture expurgée committée sous `tests/fixtures/arc/episodes/`), la spécification A1.4 est passée de « supposée » à « mesurée », et le client comme le rejeu local sont corrigés dans le même changement (coordonnées x/y, cookies de session, `game_id` par action, `frame` au singulier, `available_actions` en entiers). L'épisode réel se rejoue vert par `make test-int`.
- Prochaine étape : le préalable consigné au registre (arrêt de la boucle sur état terminal), puis U24 (campagne pilote), puis U25/U28. Le responsable a autorisé la routine planifiée à jouer ARC Prize via l'API officielle et à collecter les résultats (2026-08-30, `CLAUDE_PROJECT.md`) ; les sessions interactives restent possibles pour les mêmes unités.

## Stack

- **Python ≥ 3.11, zéro dépendance d'exécution** (bibliothèque standard uniquement) ; outillage de développement : pytest, ruff, mypy (`docs/SPEC_HARNAIS.md` §H2, motifs inclus).
- Pile locale conteneurisée (Docker Compose) : **`llm-replay`** sur le port `11435` (rejeu d'échanges **enregistrés sur le vrai endpoint** — aucun faux serveur) et `arc-replay` sur `8765` (contrat ARC-AGI-3 + jeu synthétique `cible`, car chaque appel réel publie un scorecard). Les tests tournent hors ligne sans jamais inventer un contrat.
- Deux images depuis un `Dockerfile` multi-étages : **`avo`** (production, 176 Mo, le paquet seul sans dépendance) et **`avo-dev`** (320 Mo, y ajoute make, pytest, ruff, mypy). L'outillage ne vit que dans l'image de développement.

## Prérequis

**Rien n'est installé sur votre machine : tout s'exécute dans Docker.** Il vous faut donc uniquement :

- `git` et `docker` avec un démon joignable par votre utilisateur — **le mode rootless convient et est le mode vérifié** ;
- `make` est facultatif sur l'hôte : il est installé dans l'image, et la campagne complète s'exécute avec Docker seul (commande ci-dessous) ;
- si `docker info` répond « permission denied » en mode classique, l'ajout au groupe `docker` est nécessaire, une seule fois : `sudo usermod -aG docker $USER` puis rouvrir la session ;
- Python n'est requis sur l'hôte que pour le mode dégradé décrit plus bas ;
- pour les exécutions live uniquement : l'endpoint d'inférence et la clé ARC Prize (variables ci-dessous, jamais committées).

## Commandes

Contrat : `docs/SPEC_HARNAIS.md` §H2.3. Chaque cible lance un **conteneur jetable** sur le dépôt monté en volume ; l'outillage (pytest, ruff, mypy) vit dans l'image, jamais sur l'hôte. Une cible dont l'objet n'est pas encore livré échoue en nommant l'unité de backlog qui le livrera.

| Commande | Rôle |
|---|---|
| `make image` (`make install`) | construit l'image de développement `avo-dev` |
| `make lint` / `make typecheck` | ruff / mypy, dans le conteneur |
| `make test-unit` / `make test-int` / `make test-e2e` | preuves par classe |
| `make check` | **campagne complète**, hors ligne et sans secret |
| `make build` | image de **production** `avo` (le paquet seul, sans outillage) |
| `make up` / `make down` / `make ps` / `make logs` | pile de services locale (cibles d'hôte) |
| `make smoke-pile` | fumée de la pile par le port publié (cible d'hôte) |
| `make seed` | contrôle des fixtures (n'en fabrique aucune) |
| `make record-llm` / `make test-int-live` | **[LIVE]** enregistrement et détection de dérive (exigent `.env`) |
| `make smoke-live` | fumée manuelle contre l'endpoint réel (exige `.env`, hors campagne) |
| `make run-arc` | campagne ARC (replay par défaut ; live sous garde d'accord explicite) |
| `make resume RUN_ID=<id>` | reprend un run sans rejouer les jeux déjà terminés |
| `make rapport-ab` | A/B des deux modes de contexte sur rejeu (U27) — écrit `docs/rapports/ab_mode_contexte.md` |

**Lancer une campagne** (la pile doit être debout) :

```sh
make up
make run-arc ARGS="--games cible-synthetique --tours-max 40"
make resume RUN_ID=<identifiant affiché par la commande précédente>
```

La commande écrit tout dans `runs/<run_id>/` : `report.md` (score, coûts, événements,
comparaison aux références publiées et **limites**), `campagne.json` (état de reprise),
`metrics.jsonl`, les transcripts par segment, les frames typées et un dépôt de lignée
par jeu. En `--mode live`, quatre plafonds sont obligatoires et l'accord de publication
doit être donné explicitement par `--j-autorise-la-publication` : jouer via l'API
officielle enregistre un scorecard sur le compte du responsable.

**Jouer un épisode de banc d'affinage** (`docs/SPEC_BANCS.md` §S6, §S12) :

```sh
python -m avo banc skillexec --env entrepot --seed 42 --horizon 50 [--bruit N] [--derive] [--mode live]
python -m avo banc ctf --env aleatoire --seed 42 --horizon 30 [--executeur conteneur|processus] [--mode live]
```

En `--mode replay` (défaut), l'épisode se rejoue contre la pile locale par cassette ;
en `--mode live`, le harnais joue réellement contre l'endpoint d'inférence (`.env`
requis). Banc `skillexec` : `--derive` active la condition 3 (§S3.8, §S4.7) — une
dérive d'état externe signalée par une alerte non structurée, mesurée en pas de
récupération (§S5.5). Banc `ctf` : `--env` porte la famille de défi (`aleatoire`
la tire au seed) ; les commandes de l'agent s'exécutent dans un conteneur jetable
sans réseau (`--executeur conteneur`, défaut, requis en live — un démon Docker
joignable est alors nécessaire ; `processus` est réservé aux preuves et au
rejeu, §S10.3). Le relevé (score continu §S5.3, ou pass@1 §S11.2) s'écrit dans
`runs/<run_id>/banc.json`, à côté des artefacts habituels du run.

**Lancer la pile locale** (aucun secret requis) :

```sh
make up            # construit et démarre llm-replay, puis affiche son état
make smoke-pile    # vérifie le rejeu par le port 11435 : /_health, 401 sans clé, 200 avec
make down          # arrête la pile
```

Sans `OLLAMA_API_KEY` dans l'environnement, le rejoueur accepte n'importe quel jeton porteur comme authentification valide et ne distingue que l'absence d'en-tête : la pile démontre donc le refus sans clé et le succès avec clé sans qu'aucun secret n'y entre.

**Sans `make` sur l'hôte** — campagne complète avec Docker pour seul prérequis :

```sh
docker build -t avo-dev .
docker run --rm -v "$PWD":/app -w /app -e HOME=/tmp \
  -e RUFF_CACHE_DIR=/tmp/.ruff_cache -e MYPY_CACHE_DIR=/tmp/.mypy_cache \
  avo-dev make check          # hors rootless, ajouter --user $(id -u):$(id -g)
```

**Mode dégradé, sans Docker et sans rien installer** : `AVO_NO_DOCKER=1 make test-unit` exécute les tests sur l'hôte avec la seule bibliothèque standard. Le lint y est réduit à une compilation et le typecheck n'est **pas** exécuté ; les commandes le signalent, et le bilan de `make check` le répète. Ce repli ne vaut pas preuve de style ni de typage.

## Variables d'environnement

Le harnais consommera l'endpoint d'inférence via ces variables, fournies hors dépôt (fichier `.env` local ignoré par git, ou environnement du shell). Aucune valeur réelle ni aucun secret n'est jamais committé. **Le modèle complet et commenté est [`.env.example`](.env.example)** (toutes les variables, valeurs d'exemple non sensibles, défauts) : `cp .env.example .env` puis renseigner les valeurs réelles.

| Variable | Rôle | Format attendu | Obligatoire | Exemple non sensible |
|---|---|---|---|---|
| `OLLAMA_HOST` | URL de base du serveur Ollama (surface compatible OpenAI sous `/v1`, API native sous `/api`) | URL `https://hôte[:port]` sans slash final | oui | `https://inference.example.com` |
| `OLLAMA_API_KEY` | Clé d'authentification, envoyée en `Authorization: Bearer …` | chaîne opaque | oui | `sk-ollama-xxxxxxxx` |
| `OLLAMA_CONTEXT_LENGTH` | Fenêtre de contexte demandée au serveur, en tokens (transmise en `options.num_ctx`) ; borne les budgets de contexte du harnais | entier | oui | `131072` |
| `AVO_MODEL` | Nom du modèle servi par l'endpoint | chaîne | non (défaut `qwen3.6:35b`) | `qwen3.6:35b` |
| `AVO_THINK` | Raisonnement natif du modèle (`think` sur `/api/chat`, politique H12) | booléen | non (défaut `false`) | `false` |
| `AVO_NUM_PREDICT` | Budget de sortie par appel (`options.num_predict`) | entier | non (défaut `4096`) | `4096` |
| `AVO_TEMPERATURE` | Température d'échantillonnage | réel borné | non (défaut `0.7`) | `0.7` |
| `AVO_TIMEOUT_S` | Timeout d'un appel LLM, en secondes | entier | non (défaut `900`) | `900` |
| `AVO_CONTEXT_SOFT_RATIO` | Seuil de continuation en contexte frais, en fraction du budget de prompt (H5.3) | réel dans ]0,1[ | non (défaut `0.85`) | `0.85` |
| `AVO_TOOL_STEPS_MAX` | Garde : nombre maximal d'appels d'outils par tour d'agent, au-delà duquel le tour est clos avec un message explicite | entier | non (défaut `40`) | `40` |
| `AVO_ACTIONS_MAX_NIVEAU` / `AVO_ACTIONS_MAX_JEU` | Bornes d'actions d'environnement, par niveau et par jeu ; dépassement = arrêt propre avec la borne nommée | entier | non (défauts `1000` / `5000`) | `1000` |
| `AVO_SUP_STALL_ACTIONS` / `AVO_SUP_COOLDOWN` | Superviseur : actions sans progrès avant intervention, et actions minimales entre deux interventions | entier | non (défauts `60` / `30`) | `60` |
| `ARC_API_KEY` | Clé d'accès à l'API ARC Prize (ARC-AGI-3), envoyée en en-tête `X-API-Key` ; donne accès aux environnements officiels et à l'ouverture des scorecards | UUID | oui pour l'évaluation ARC-AGI-3, inutile pour le reste du harnais | `00000000-0000-0000-0000-000000000000` |
| `ARC_BASE_URL` | Base de l'API ARC-AGI-3. En mode rejeu, elle pointe la pile locale et le client **refuse** tout autre hôte : les tests ne peuvent pas publier de scorecard par accident | URL `https://hôte[:port]` | non (défaut selon le mode) | `http://127.0.0.1:8765` |
| `AVO_RUNS_DIR` | Racine des workspaces de run (artefacts) | chemin | non (défaut `runs/`) | `runs/` |
| `AVO_CONTEXT_MODE` | Mode de contexte de la boucle : `state` (état structuré Σ borné en O(1) par tour, H15 ; schéma de Σ déclaré par le domaine de tâche, H15.9) ou `transcript` (historique complet, H5) | `transcript` \| `state` | non (défaut `state`, décision du 2026-09-01 sur l'A/B réel de U28) | `state` |
| `AVO_GARDES` | Gardes de méthode dans les phases (H16) : artefact documentaire avant l'action, prédiction requise, verdict exigé, persistance aux événements | booléen | non (défaut `true`) | `true` |
| `AVO_GARDE_RETRIES` | Redemandes d'une même garde dans un même tour, avant l'issue écrite en H16 (tour clos sans action, ou verdict réputé contredit) | entier | non (défaut `2`) | `2` |
| `AVO_LLM_MAX_CONCURRENT` | Plafond de requêtes LLM simultanées par endpoint (H4.9) : l'excédent patiente au lieu d'échouer ; `0` désactive | entier ≥ 0 | non (défaut `3`, limite du port public) | `3` |
| `AVO_LLM_SLOTS_DIR` | Répertoire des jetons de concurrence (H4.9) ; pointer un chemin réellement partagé pour coordonner plusieurs processus ou sessions | chemin | non (défaut `<AVO_RUNS_DIR>/.llm-slots`) | `runs/.llm-slots` |

Trois variables d'**outillage** sont lues dans l'environnement du shell par `make` et les scripts — pas dans `.env` (`make` ne le lit pas) : `AVO_NO_DOCKER` (mode dégradé sans Docker, stdlib seule), `AVO_PORT_LLM_REPLAY` (défaut `11435`) et `AVO_PORT_ARC_REPLAY` (défaut `8765`), ports publiés de la pile locale.

En **mode rejeu** (le mode par défaut, celui des tests et du worker), aucune de ces variables n'est requise : la configuration pointe la pile locale (`http://127.0.0.1:11435`), emploie un jeton qui n'est pas un secret et une fenêtre de contexte par défaut. En **mode live**, l'absence de `OLLAMA_HOST`, `OLLAMA_API_KEY`, `OLLAMA_CONTEXT_LENGTH` ou `ARC_API_KEY` est une erreur au démarrage qui nomme la variable — jamais une valeur par défaut silencieuse.

Le plafond réellement applicable n'est pas cette variable seule : le proxy d'authentification impose une **limite de contexte par clé API**, qu'il publie dans le corps de sa réponse `HTTP 413` (`max_context_tokens`), et il compare à ce plafond une estimation **majorée de 15 %**. Le budget exploitable par le harnais vaut donc environ `max_context_tokens / 1,15`. Le `413` doit être traité comme un cas nominal (repli par compaction ou continuation en contexte frais), pas comme une erreur fatale ; son corps renvoie `tokens_estimated`, directement exploitable. Valeurs mesurées sur l'endpoint courant : `docs/JOURNAL.md`, entrée du 2026-08-27 (suite 2).

## Structure du dépôt

```text
.
├── CLAUDE.md            # contrat d'ingénierie global P2Enjoy (ne pas localiser)
├── CLAUDE_PROJECT.md    # règles propres à ce dépôt
├── README.md
├── CHANGELOG.md
├── Dockerfile           # multi-étages : avo (production) et avo-dev (outillage)
├── docker-compose.yml   # pile locale de rejeu (llm-replay, port 11435)
├── scripts/             # fumée de la pile (exécutée sur l'hôte)
├── Makefile             # contrat des commandes, tout en conteneur
├── pyproject.toml       # paquet avo, zéro dépendance d'exécution
├── src/avo/             # paquet applicatif (cli, llm, context, memory, tools, loop, arc, bancs)
├── infra/               # llm-proxy : pont HTTPS 443 vers l'endpoint (fonction edge Netlify)
├── mocks/               # serveurs locaux : llm-replay (U4), arc-replay (U16)
├── tests/               # unit, integration, e2e, fixtures
├── docs/
│   ├── .routine         # entrée de la tâche planifiée (worker horaire)
│   ├── CloudWorker.md   # contrat d'exécution du worker planifié
│   ├── MASTER_PLAN.md   # ordre d'exécution des unités, DoD commune
│   ├── SPEC_HARNAIS.md  # spécification du noyau agent (H1–H14)
│   ├── SPEC_ARCAGI3.md  # spécification interface ARC-AGI-3 et évaluation (A1–A8)
│   ├── DAT.md           # dossier d'architecture technique (vue d'ensemble)
│   ├── BACKLOG.md       # unités de travail et statuts (U1–U25)
│   ├── JOURNAL.md       # décisions et investigations
│   └── DESIGN_SYSTEM.md # socle UI global P2Enjoy (pas d'UI dans ce projet à ce stade)
└── knowledge/           # sources de référence exportées (voir knowledge/README.md)
```

## Limites connues

- Le harnais n'est pas encore implémenté : le dépôt contient la connaissance de référence, la spécification complète, et le squelette outillé (U3). Les composants arrivent avec les unités U4+ du backlog.
- Le listing `/api/games` de l'API officielle peut annoncer des jeux que le backend de commandes ne sert pas (`400` « game … not found », mesuré) : une campagne doit s'attendre à ce refus nommé. La lecture `GET /api/scorecard/<id>` s'est révélée non fiable (404 sur carte sans partie et après fermeture) : le résumé rendu par la fermeture fait foi (`docs/SPEC_ARCAGI3.md` §A1.4).
- **Le préremplissage du contexte est le coût dominant de l'endpoint**, très loin devant la génération (débit mesuré le 2026-08-27 : voir `docs/JOURNAL.md`). Un harnais qui réémettrait l'historique complet à chaque tour serait inexploitable en temps sur un benchmark de plusieurs milliers d'actions : l'historique doit rester strictement append-only pour bénéficier du cache de préfixe.
- **Le budget de contexte utile est inférieur au plafond nominal** de la clé, à cause de la marge de 15 % appliquée par le proxy (voir « Variables d'environnement »).
- **Le modèle servi est un modèle à raisonnement** : le raisonnement consomme le budget de sortie avant tout contenu, et une valeur de `max_tokens` trop basse produit une réponse vide avec `finish_reason: length`. Politique à arrêter dans la spécification (budget large, ou raisonnement désactivé).
- **Évaluer, c'est publier** : l'API ARC Prize enregistre chaque partie dans un scorecard rattaché au compte porteur de la clé. Il n'existe pas de mode d'exécution officiel sans dépôt de résultat. Toute campagne engage donc le compte du responsable, et les exécutions d'essai doivent passer par l'environnement local de rejeu plutôt que par l'API.
- **Une campagne complète est hors de portée en une session** : 25 jeux, 183 niveaux, une référence humaine de 17 135 actions cumulées et des agents de référence autour de 7 000 actions, à combiner avec le coût de préremplissage de l'endpoint. Le périmètre d'une campagne (sous-ensemble de jeux, plafonds d'actions, budget de temps) est défini dans la spécification, jamais implicite.

## Origine

Dépôt initialisé depuis la base « P2Enjoy Software Factory » (conventions d'ingénierie, contrat de worker planifié, socle UI). Licence : [MPL-2.0](LICENSE).
