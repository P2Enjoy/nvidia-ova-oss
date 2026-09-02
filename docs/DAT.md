# Dossier d'architecture technique (DAT)

> Le détail normatif vit dans `docs/SPEC_HARNAIS.md` (H1–H16),
> `docs/SPEC_ARCAGI3.md` (A1–A8) et `docs/SPEC_BANCS.md` (S1+) ; ce dossier est
> la vue d'ensemble. L'implémentation suit `docs/MASTER_PLAN.md`.

## Objet du système

Harnais d'agent AVO (arXiv:2603.24517) : agent LLM autonome longue-durée — boucle
Planning → Implementation → Evaluation → Bug-Fixing, mémoire persistante, lignée de
solutions scorées, superviseur anti-stagnation — évalué sur ARC-AGI-3 (ensemble
public) en direct-interaction texte (grilles 64×64 exactes, actions sans description).

## Composants

| Composant | Spéc. | Rôle |
|---|---|---|
| `avo.config` | H3 | configuration (env puis `.env`), validation nommée, modes rejeu/live, budget dérivé du plafond par clé |
| `avo.llm` | H4 | client d'inférence (Ollama natif `/api/chat`), erreurs typées, retries bornés, transport injectable |
| `avo.context` | H5, H15 | transcript append-only, comptabilité calibrée, budget et continuation en contexte frais ; état d'exécution structuré Σ (mode `state`, U26) — patch validé par le runtime, sérialisation ; schéma de Σ DÉCLARÉ PAR LE DOMAINE et validé par le noyau (H15.9, U31 : genres génériques, champ commun `hypotheses`, dictionnaire fusionné clé par clé, `arc-v1` par défaut, protocole engendré depuis le schéma) |
| `avo.memory` | H6 | workspace de run (manifeste, métriques, transcripts, frames, rapport) et notes persistantes GUIDE/WORKING |
| `avo.tools` | H7 | registre d'outils, exposition filtrée par état, groupe synchronisable sur l'environnement, routage, garde par tour |
| `avo.loop` | H8, H12 | machine d'états P→I→E→B close, prompts de phase versionnés, contrat `Environnement`, bornes d'actions, et les branchements H8.4 : continuation, supervision, métriques, lignée |
| `avo.lineage` | H9 | lignée git jetable et isolée par run, politique correct ∧ ≥ meilleur, `Scorer` branchable |
| `avo.supervisor` | H10 | détecteurs mesurés, intervention par appel LLM séparé, cooldown ; n'agit jamais |
| `avo.transport` | H4.5, A2.1 | politique de retry partagée par les deux clients |
| `avo.runlog` | H11 | logs JSON corrélés, filtre de masquage des secrets |
| `avo.arc` | A2, A4–A7 | client API ARC, rendu texte canonique, mémoire de frames sans perte, interface de tâche direct-interaction (`Environnement` de la boucle), calcul du RHAE, runner de campagne et rapport |
| `avo.bancs` | S1–S7 | bancs d'affinage du harnais : environnements de mesure déterministes (banc a : Entrepôt livré, générateur seedé, score continu) branchés comme adaptateurs minces sur le contrat `Environnement` ; adaptateur de boucle livré (`skillexec/adaptateur.py` : outils `action`, contexte de tâche en message système, relevé `banc.json`) et sous-commande CLI `banc` (`--bruit`, `--derive` : conditions 1 et 3 de la source, mesure de récupération §S5.5) — le dispatch et les mots du banc vivent sous `avo.bancs`, la CLI du noyau reste générique |
| `mocks/llm_replay` | H4.7 | rejeu d'échanges enregistrés sur le vrai endpoint, injection de fautes |
| `mocks/arc_replay` | A3 | contrat ARC local (port 8765), jeu `cible` en forme fermée, rejeu d'épisodes |

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
- Deux modes de contexte exclusifs par run (`AVO_CONTEXT_MODE`, H15.7) : état
  structuré Σ (SKILL.state, H15 — **défaut** depuis la décision du 2026-09-01) et
  historique append-only + continuation en contexte frais à la VISTA (H5),
  activable explicitement. Départage fait par mesure, pas par principe : A/B sur
  rejeu (U27, `docs/rapports/ab_mode_contexte.md`) puis A/B en conditions réelles
  (U28, `docs/rapports/ab-u28-state.md`).
- Gardes de méthode dans les phases (H16, U30) : la structure impose ce que le
  prompt conseille — artefact documentaire (`WORKING.md`, ou `hypotheses` de Σ)
  avant de déverrouiller l'action, prédiction requise par le schéma des outils
  d'action et acheminée vers `reasoning` du fil officiel, verdict
  confirmé/contredit exigé à l'évaluation, écriture de `GUIDE.md` exigée aux
  complétions, game over et interventions. Jamais fatales, bornées
  (`AVO_GARDE_RETRIES`), débrayables (`AVO_GARDES`), valables dans les deux modes
  de contexte ; A/B sur `cible` : aucune action ni aucun appel de plus sur
  politique conforme. En mode `state`, un refus de garde est un pas blanc
  ATOMIQUE — le patch du pas refusé est annulé avec l'action (Σ ne ment jamais
  sur une action non jouée), et le champ commun `hypotheses` ne se vide pas en
  cours de run (vidage = `EtatInvalide`, retry immédiat) — H16.1, mesures au
  journal (suite 21).
- Lignée = git jetable par run, jamais le dépôt projet (H9.3).
- Instanciation ARC du couple (xᵢ, f) : connaissance validée / (niveaux, −actions)
  — décision documentée H9.2, les sources ne publiant pas ce détail.

## Compromis connus

- Le contrat de fil ARC est MESURÉ (sonde U22, 2026-08-31, capture committée) et
  implémenté à l'identique côté client et côté rejeu (A1.4). La réconciliation des
  compteurs officiels par niveau passe par le résumé de scorecard à la fermeture
  (A5.3) — preuve portée par la campagne pilote U24.
- Une campagne complète 25 jeux est hors budget temps d'une session : périmètre
  toujours explicite (A7.1), exécution par tranches reprenables.
- Le RHAE officiel dépend des baselines servies par l'API ; en rejeu local il repose
  sur les baselines synthétiques du jeu `cible` (valeur de test, pas de référence).
