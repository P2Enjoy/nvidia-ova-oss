# CLAUDE_PROJECT.md — Règles locales du dépôt nvidia-ova-oss

Complément local de `CLAUDE.md` (qui reste global et prime pour les exigences de qualité).

## Objet du dépôt

Implémentation open source du harnais d'agent **AVO** (papier arXiv:2603.24517) et son évaluation sur des benchmarks via un endpoint d'inférence **compatible OpenAI**. L'endpoint (URL), la clé API et le nom du modèle sont fournis par le responsable hors dépôt ; ils ne sont **jamais** committés.

## Sources de référence

- `knowledge/` contient les exports fidèles des quatre sources (papier AVO, blog NVIDIA, page VISTA, papier Tycho) avec images et PDF. **Lire `knowledge/README.md` avant tout travail sur le harnais.**
- Ces exports sont des instantanés en lecture seule : ne pas les modifier à la main ; en cas de divergence avec la source, re-générer l'export et le consigner dans `docs/JOURNAL.md`.
- En cas de doute d'interprétation, le PDF sous `knowledge/pdf/` fait foi.

## Configuration de l'endpoint d'inférence

- Trois variables, fournies par le responsable hors dépôt : `OLLAMA_HOST`, `OLLAMA_API_KEY`, `OLLAMA_CONTEXT_LENGTH` (rôles et formats documentés dans `README.md`). En session, elles vivent dans un `.env` local à la racine, couvert par `.gitignore` — vérifier `git check-ignore .env` avant tout commit.
- Le serveur est un Ollama derrière un reverse-proxy qui porte l'authentification et les quotas : surface compatible OpenAI sous `$OLLAMA_HOST/v1` (`/v1/models`, `/v1/chat/completions`), API native sous `/api` (`/api/tags`, `/api/show`, `/api/version`, `/api/ps`, `/api/chat`). Authentification `Authorization: Bearer $OLLAMA_API_KEY`, appliquée réellement côté serveur (`401` sans clé et avec clé invalide, vérifié).
- Ni l'URL réelle, ni la clé, ni les adresses d'infrastructure du responsable ne sont écrites dans les fichiers committés (docs comprises) : les documents parlent de « l'endpoint fourni » et des noms de variables. Le nom du modèle, lui, n'est pas un secret et peut être cité.
- **Modèle de travail : `qwen3.6:35b`** — seul modèle de complétion servi (l'autre, `all-minilm:latest`, ne fait que des embeddings). Capacités `completion`, `tools`, `thinking`, `vision`.
- Trois contraintes mesurées, contraignantes pour toute conception du harnais (mesures et chiffres : `docs/JOURNAL.md`, entrée du 2026-08-27 (suite 2)) :
  1. le **préremplissage domine le coût** — l'historique envoyé au modèle doit rester strictement append-only pour bénéficier du cache de préfixe ; toute réécriture en tête de contexte est un défaut de performance ;
  2. le **plafond de contexte est par clé API**, publié par le proxy dans le corps de son `HTTP 413` (`max_context_tokens`), et comparé à une estimation **majorée de 15 %** — budgéter sur `max_context_tokens / 1,15` et traiter le `413` comme un cas nominal, son corps renvoyant `tokens_estimated` ;
  3. le modèle **raisonne avant de répondre**, et le raisonnement consomme le budget `max_tokens` — un budget trop court rend `content` vide avec `finish_reason: length`. Le raisonnement est exposé dans `message.reasoning` et désactivable par `think: false` sur l'API native.
- État de joignabilité et procédure de re-test : dernière entrée de `docs/JOURNAL.md`. L'endpoint a été testé et validé de bout en bout le 2026-08-27 ; un échec de joignabilité constaté depuis un autre environnement d'exécution ne remet pas en cause le serveur (voir l'entrée précédente du journal, marquée résolue).

## Accès ARC-AGI-3 (ARC Prize)

- Variable `ARC_API_KEY`, fournie hors dépôt comme les autres, envoyée en en-tête `X-API-Key` sur l'API ARC-AGI-3. Vérifiée le 2026-08-27 en lecture seule : 25 jeux, 183 niveaux, `baseline_actions` humaines par niveau, qui **font foi** pour le calcul du RHAE.
- **Évaluer, c'est publier.** Toute partie jouée via l'API officielle s'enregistre dans un scorecard rattaché au compte du responsable ; il n'existe pas de mode officiel sans dépôt de résultat. Les tests et les exécutions d'essai passent donc obligatoirement par l'environnement local de rejeu déterministe et **n'appellent jamais l'API**. La première campagne officielle requiert l'accord explicite du responsable.

## Spécifications et plan

- La spécification du harnais est **écrite et committée** : `docs/SPEC_HARNAIS.md` (§H) et `docs/SPEC_ARCAGI3.md` (§A) ; l'ordre d'exécution et la DoD commune sont dans `docs/MASTER_PLAN.md`. Les commentaires `@spec`/`@verifies` citent l'unité de backlog et ces chapitres (`Hn.m`/`An.m`).
- Toutes les unités du backlog ont leur spécification : une session prend une unité et **code directement** (cas « spécification existante » du contrat worker). Les unités **[LIVE]** exigent le `.env` local et ne sont jamais prises par le worker planifié (`docs/MASTER_PLAN.md` §3).
- Produit CLI sans interface graphique : la vérification « dans la peau de l'utilisateur » est l'exécution réelle des commandes documentées et la lecture des artefacts (`docs/MASTER_PLAN.md` §5) ; CLAUDE.md §16 s'appliquera en entier si une UI apparaît.

## Conventions locales

- Documentation projet en français ; les exports de `knowledge/` conservent le texte original anglais sous un en-tête de provenance français.
- L'état réel du travail vit dans `docs/BACKLOG.md` (unités U1–U6) et `docs/JOURNAL.md` (dernière entrée = point de reprise). Les relire en début de session.
- La spécification du harnais (ex-unité U2) est écrite et committée ; toute nouvelle ligne de code doit être couverte par un chapitre de `docs/SPEC_HARNAIS.md` ou `docs/SPEC_ARCAGI3.md` cité en `@spec` — un comportement non spécifié se spécifie d'abord, dans le même chunk.
- `docs/.routine` et `docs/CloudWorker.md` sont le contrat de la tâche planifiée (worker horaire sur `main`) hérité de la base factory ; une session interactive travaille sur la branche que le responsable lui désigne.

## Terminologie

- **AVO** : Agentic Variation Operators — l'architecture à implémenter.
- **VISTA** : harnais visuel MIT dont AVO reprend les principes « direct-interaction » pour ARC-AGI-3.
- **Tycho** : approche par modèles du monde programmatiques ; source de la formalisation ARC-AGI-3 et de la définition RHAE.
- **RHAE** : Relative Human Action Efficiency, métrique officielle ARC-AGI-3 (définition exacte dans l'export Tycho, §3.1).
