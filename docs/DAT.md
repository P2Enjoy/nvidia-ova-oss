# Dossier d'architecture technique (DAT)

> Le détail normatif vit dans `docs/SPEC_HARNAIS.md` (H1–H14) et
> `docs/SPEC_ARCAGI3.md` (A1–A8) ; ce dossier est la vue d'ensemble. Le code
> n'existe pas encore : l'implémentation suit `docs/MASTER_PLAN.md` (U3+).

## Objet du système

Harnais d'agent AVO (arXiv:2603.24517) : agent LLM autonome longue-durée — boucle
Planning → Implementation → Evaluation → Bug-Fixing, mémoire persistante, lignée de
solutions scorées, superviseur anti-stagnation — évalué sur ARC-AGI-3 (ensemble
public) en direct-interaction texte (grilles 64×64 exactes, actions sans description).

## Composants

| Composant | Spéc. | Rôle |
|---|---|---|
| `avo.config` | H3 | configuration par variables d'environnement, budgets dérivés |
| `avo.llm` | H4 | client d'inférence (Ollama natif `/api/chat`), erreurs typées, retries |
| `avo.context` | H5 | transcript append-only, budget de contexte, continuation en contexte frais |
| `avo.memory` | H6 | workspace de run, notes persistantes GUIDE/WORKING |
| `avo.tools` | H7 | registre d'outils, dispatch des tool_calls, garde |
| `avo.loop` | H8, H12 | machine d'états P→I→E→B, prompts de phase, politique de raisonnement |
| `avo.lineage` | H9 | lignée git jetable par run, politique correct ∧ ≥ meilleur, `Scorer` |
| `avo.supervisor` | H10 | détection de stagnation, intervention conditionnelle |
| `avo.runlog` | H11 | logs JSON sans secret, métriques, transcripts |
| `avo.arc` | A2, A4–A7 | client API ARC, rendu texte, interface de tâche, RHAE, campagne |
| `mocks/llm_replay` | H4.7 | rejeu d'échanges enregistrés sur le vrai endpoint, injection de fautes |
| `mocks/arc_replay` | A3 | contrat ARC local, jeu synthétique `cible`, rejeu d'épisodes |

## Flux principaux

1. **Tour de jeu** : observation (grille texte + actions disponibles) → Planning
   (hypothèses + prédiction) → Implementation (une action via outil → `ArcClient`) →
   Evaluation (frames typées, notes, score) → [Bug-Fixing]. Frames archivées sans
   perte ; inspection gratuite au score.
2. **Continuation** : seuil de budget ou `HTTP 413` → état de continuation écrit par
   l'agent → segment frais (système + continuation + notes + observation). Historique
   d'un segment strictement append-only (cache de préfixe).
3. **Lignée** : complétion de niveau → commit (connaissance + score) dans le dépôt
   git jetable du run.
4. **Supervision** : stall/cycles détectés → appel LLM séparé → directive
   `[SUPERVISEUR]` injectée en append.
5. **Campagne** : runner séquentiel multi-jeux, scorecard officiel (live) ou
   arc-replay (replay), RHAE, `report.md`.

## Données

- **Workspace de run** `runs/<id>/` : manifest, transcripts JSONL, notes, frames
  typées, lignée (git dédié), métriques, rapport. Gitignoré ; les rapports de
  campagne officielle sont copiés sous `docs/rapports/`.
- **Fixtures** `tests/fixtures/` : cassettes llm **enregistrées sur le vrai endpoint**
  (`make record-llm`, [LIVE]), paramètres du jeu `cible` et épisodes ARC expurgés (U16).
  `make seed` contrôle leur présence et nomme ce qui manque — il ne fabrique aucun
  contrat (CLAUDE.md §8).

## Interfaces externes

- **Endpoint d'inférence** (fourni, hors dépôt) : Ollama derrière proxy authentifiant,
  surface native `/api/*` ; contraintes mesurées (préremplissage dominant, plafond par
  clé +15 %, modèle à raisonnement) — `docs/JOURNAL.md` 2026-08-27.
- **API ARC Prize** : `X-API-Key` ; **évaluer = publier un scorecard** → tests
  uniquement sur arc-replay (garde anti-publication A2.3), campagnes en session
  interactive avec accord.

## Sécurité et autorisations

Secrets uniquement en `.env` local (gitignoré) ; jamais journalisés (tests dédiés).
Mode `replay` sans réseau externe par construction. Aucune écriture dans le dépôt
projet par le harnais (lignée isolée sous `runs/`).

## Déploiement et exécution

Deux images depuis un `Dockerfile` multi-étages : `avo` (production, le paquet seul,
aucune dépendance d'exécution) et `avo-dev` (y ajoute make, pytest, ruff, mypy — seul
endroit où l'outillage est installé). Pile locale : `make up` (compose : `llm-replay`
sur 11435 avec healthcheck sur `/_health` ; `arc-replay` sur 8765 en U16),
`make smoke-pile`, `make seed`, `make check` (campagne de preuves complète, hors
ligne, en conteneur). Live : `make smoke-live` (manuel),
`python -m avo run-arc --mode live` avec garde d'accord explicite. Pas
d'environnement de production : le « déploiement » est la campagne d'évaluation
(contrat A7).

## Choix techniques actés (motifs dans les spécifications)

- Python ≥ 3.11, **zéro dépendance d'exécution** (stdlib) ; dev : pytest, ruff, mypy (H2.1).
- Surface Ollama **native** plutôt qu'OpenAI `/v1` (contrôle `think`, `num_ctx`,
  compteurs) derrière une interface remplaçable (H4.1).
- `think:false` par défaut, raisonnement en clair dans le contenu (H12).
- Historique append-only + continuation en contexte frais à la VISTA (H5).
- Lignée = git jetable par run, jamais le dépôt projet (H9.3).
- Instanciation ARC du couple (xᵢ, f) : connaissance validée / (niveaux, −actions)
  — décision documentée H9.2, les sources ne publiant pas ce détail.

## Compromis connus

- Le contrat de fil ARC exact reste à confirmer par la sonde U22 (A1.4) — écrit
  d'après l'export Tycho, corrigeable des deux côtés (client + rejeu).
- Une campagne complète 25 jeux est hors budget temps d'une session : périmètre
  toujours explicite (A7.1), exécution par tranches reprenables.
- Le RHAE officiel dépend des baselines servies par l'API ; en rejeu local il repose
  sur les baselines synthétiques du jeu `cible` (valeur de test, pas de référence).
