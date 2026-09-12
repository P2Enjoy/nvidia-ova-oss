# GVS5H — dépôt compagnon du papier « Zero-Shot Self-Orchestration with Ledger-Based Control » (code, prompts, données de runs)

> **Source** : <https://github.com/slee-persis/GVS5H> — commit `e46c574763e881e5343d3cca6fe1bbaab755f44e` (2026-09-11T16:19:46-04:00, auteur `slee-persis`)
> **Récupéré le** : 2026-09-12 (clone superficiel du dépôt public)
> **Licences** : code (`codebase/`, `paper_plot_script/`) MIT ; papier, figures et données de runs (`paper/`, `assets/`, `runs/`) CC BY 4.0 ; le fork LiveCodeBench et les énoncés de problèmes conservent leurs licences propres (voir « Licences » ci-dessous).
> **Pertinence pour ce dépôt** : implémentation de référence, complète et minuscule (~500 lignes), du scaffold manager–workers du papier arXiv:2608.26480 (export `arxiv-2608.26480-gvs5h-zero-shot-self-orchestration.md`) — boucle, prompts verbatim, gardes, workspace « ledger » sur fichiers — plus les workspaces et transcripts complets de tous les runs du papier. Même famille d'ingrédients que le harnais AVO : workspace persistant hors contexte, notes réécrites et bornées, décomposition en appels courts en contexte frais, garde de non-progrès, verdict d'exécution traité comme vérité terrain.

---

## Objet du dépôt

Dépôt compagnon (« GVS5H: Five Qwen3.8-27B Models Match Claude Fable 5 on LiveCodeBench Hard ») publiant, pour le papier arXiv:2608.26480 :

- `codebase/v2-current/` — le scaffold v2 (résultats §2.1 du papier) : ~500 lignes de Python autour d'un client OpenAI-compatible ;
- `codebase/v1-be9dfa2/` — le scaffold original (résultats §2.4) ;
- `codebase/livecodebench/` — fork de LiveCodeBench portant la correction d'évaluateur du §3.3 du papier (mock stdin binaire : `readline()` sans avancement de position) ;
- `paper/` — les sources LaTeX et le PDF de la conférence (`iclr2027_conference.pdf`) ;
- `assets/` — les deux figures principales en PNG (mises en miroir sous `images/github-gvs5h/`) ;
- `runs/` — les résultats et les WORKSPACES COMPLETS des runs du papier (~316 Mo) : par condition (`128k-clean`, `16k-reasoning-off-5pass`, `fable5-128k-reasoning-on-5pass`, etc.), chaque problème avec son `task.md`, `plan.md`, `notes.md`, `tasks.json`, `solution.py` et `transcript.jsonl` (chaque appel modèle avec rôle, requête, réponse, raisonnement, `finish_reason`, comptes de tokens) ;
- `paper_plot_script/` — les scripts de figures.

## README du dépôt (texte original)

> **Abstract.** Frontier coding performance is typically bought with larger proprietary models at high cost. We introduce ledger-based zero-shot self-orchestration, a training-free method in which fresh instances of one model decompose problems and coordinate through a shared filesystem holding a plan, notes and current solution. Across nine open and closed-weight models on the 100 latest *hard* LiveCodeBench problems, the method yields gains of up to 23.2 percentage points on pinned backends and offers two routes to frontier-level accuracy. Orchestrated GPT-5.6-Terra reaches 88.0% pass@1 against Fable 5's 90.4% at 19% of the cost, and locally served, open-weight Qwen3.8-27B rises from 69.2% to 92.4%, slightly exceeding Fable 5. Gains are not universal: some models are unchanged or worse. Transcript analysis attributes the gain to decomposition and persistent context. Inference-time organization can approach frontier coding accuracy at a fraction of the cost, or slightly exceed it on self-hostable weights.

**NOTE DE DIVERGENCE (constatée à l'export, 2026-09-12)** : les chiffres de cet abstract de README (88,0 / 90,4 / 69,2 → 92,4) diffèrent de ceux du PDF arXiv v1 du 27 août (85,0 / 87,4 / 63,0 → 86,4). Le dépôt (commit du 2026-09-11) porte un état PLUS RÉCENT que l'arXiv v1 — le `pdftotext` des deux PDF diffère aussi. L'export du papier suit le PDF arXiv v1, qui fait foi pour la version publiée ; le dépôt fait foi pour le code et les données.

Commande de reproduction documentée par le README (nécessite `uv` et une clé API du modèle testé) :

```bash
cd codebase/v2-current
export OPENAI_API_KEY=...

LCB_RELEASE=release_v6 \
ESCALATION_CLOUD_MAX_TOKENS=128000 \
ESCALATION_CLOUD_TIMEOUT=7200 \
MULTIAGENT_MODEL=openai:gpt-5.6-terra \
uv run --no-project --python 3.12 --with 'datasets<4' --with numpy --with anthropic \
  python escalation/run_bench.py --engine multiagent --only lcb --lcb 100 --parallel 8
```

- `--engine multiagent` runs the manager; `--engine single` is the one-call baseline.
- Other models: `anthropic:<model>`, `dashscope:<model>`, `openrouter:<model>`, each with its own `*_API_KEY`.
- The pass@1 score prints at the end. Results are written to `runs/results.json`, workspaces to `runs/ws/`.

## Le scaffold v2 (`codebase/v2-current/escalation/multiagent.py`, 496 lignes)

### Workspace « ledger » et constantes

Un workspace par problème (`runs/ws/<md5(problème)[:12]>/`), fichiers : `task.md` (énoncé), `plan.md` (plan du manager), `tasks.json` (`[{id, desc, status, result}]`), `notes.md` (notes accumulées), `solution.py` (meilleure solution courante), `transcript.jsonl` (chaque appel : rôle, requête, réponse, `reasoning` — avec drapeau `reasoning_is_summary`, car Anthropic rend un RÉSUMÉ du raisonnement là où vLLM/DashScope rendent la chaîne réelle —, `finish_reason`, comptes de tokens, fournisseur, tentatives).

Constantes (variables d'environnement) : `MULTIAGENT_MAX_ITERS=10` (budget de rondes manager→worker), `MULTIAGENT_MAX_TASKS=12` (plafond de la task list), `MAX_PLAN_CHARS=4000` (plan borné ; notes bornées à 2×), `MULTIAGENT_STRICT_FORMAT` (rappel de format renforcé pour certains modèles). Températures : 0,3 plan, 0,4 brainstorm, 0,2 exécution de tâche, curation et baseline single.

### Gardes

- **Budget de rondes** : 10 cycles manager→worker maximum.
- **Garde de non-progrès** : si le manager redélivre EXACTEMENT la tâche qu'il vient de donner, la boucle s'arrête.
- **Résumeur de coupure** : un worker coupé au plafond de tokens (`finish_reason=length`) voit sa tentative partielle résumée par un appel court séparé ; le résumé — approche poursuivie, acquis, reste — parvient au manager avec la consigne « prefer a simpler or different approach next ». Ses NOTES tronquées ne remplacent PAS le fichier de notes.
- **Invariant « pas de done sans artefact »** : un verdict `done` du manager sans solution sur disque est forcé à `continue`.
- **Verdict d'échantillons = vérité terrain** : si les tests publics échouent, un `done` du manager est OUTREPASSÉ et la boucle continue sur une tâche « fix or switch ».
- **Finaliseur conditionnel** : appelé seulement si la boucle se termine sans sign-off propre ; sauté quand `done` est déclaré avec une solution utilisable déjà sur disque, pour qu'une passe finale redondante ne puisse pas écraser une réponse correcte.

### Prompts verbatim

**Manager — plan** (température 0,3) :

```
You are the PRIMARY orchestrator (manager) of a small team of workers, all
expert at competitive programming. Given a problem, produce a short overarching
plan to solve it, then a task list the workers can pick up. Respond with
EXACTLY these sections:
### PLAN
<3-6 sentence strategy>
### TASKS
<3-6 bullet tasks, each a concrete unit of work>
```

**Premier worker — brainstorm/idéation** (température 0,4 ; reçoit PROBLEM + PLAN) :

```
You are the FIRST WORKER. Do NOT solve the problem and do NOT write any code.
Just think about it: identify the core difficulty, then list SEVERAL DISTINCT
candidate approaches (genuinely different algorithms / data structures / problem
reductions, not variations of one idea), and note pitfalls for each. Describe each
approach in prose only -- absolutely no code blocks; a later worker will implement.
Respond with EXACTLY:
### NOTES
<your analysis>
### NEXT
<bullet list of distinct approaches to try next>
```

**Manager — manage/curation** (température 0,2 ; reçoit PROBLEM, CURRENT SOLUTION, NOTES, CURRENT TASK LIST, LATEST WORKER RESULT, PROPOSED NEW STEPS) :

```
You are the PRIMARY orchestrator and manager. You OWN the task list and decide
when the problem is solved. Review the current progress and the latest worker's
result, then:
- The LATEST WORKER RESULT may include a SAMPLE TESTS verdict from actually running
the code. Treat it as ground truth: only set STATUS 'done' if the solution PASSED the
sample tests; if it FAILED, you MUST set STATUS 'continue' and choose a task that
fixes the failing case or switches to a different approach.
- If the current solution/answer is complete and correct, set STATUS to 'done'.
- Otherwise CURATE the task list: merge duplicates, drop finished or irrelevant
items, mark completed ones [done], and fold in ONLY genuinely new sub-tasks from
the proposals. Then choose the single most valuable next task.
- IMPORTANT: if the current solution keeps failing, or the last worker made no real
progress, do NOT keep refining the same idea. Switch to a DIFFERENT approach
(a different algorithm / data structure / reduction) from the notes, or ask for a
new one. You have many rounds -- use them to try distinct approaches, not to polish
a stuck one.
Respond with EXACTLY these sections:
### STATUS
<done|continue>
### NEXT
<exact text of the ONE task to do next; omit if done>
### TASKS
<curated list, one per line, each '- [done] ...' or '- [todo] ...'>
```

**Worker — exécution de tâche** (température 0,2 ; reçoit PROBLEM, PLAN, NOTES, CURRENT WORK, YOUR TASK ; le `solver_system` est le prompt solveur de la baseline single, enveloppé) :

````
You are a WORKER subagent, {solver_system} You share a workspace with the team.
Build on the current work and notes where useful -- but if your task is to try a
different approach, write a FRESH solution for that approach instead of patching
the stuck one. Respond with EXACTLY these sections:
### CODE
```python
<the FULL updated self-contained program>
```
### NOTES
<the COMPLETE notes file, rewritten. You are shown the current NOTES above: fold
your findings into them, keep what still matters, and DELETE anything superseded,
disproven, or now obvious. This REPLACES the file, so whatever you omit is gone.
Organise it as '- **Topic:** ...' bullets, under ~800 words. Do NOT use markdown
headings (#, ##), bold-only lines, or ALLCAPS: lines anywhere inside this section
-- the reply is split on those, so they would truncate your notes.>
### NEXT
<bullet list of remaining steps, or 'none'>
### STATUS
<solved|continue>
````

**Résumeur de coupure** (température 0,2) :

```
A worker's solution attempt was CUT OFF when it hit the token limit. Summarize its
partial attempt in 3-5 sentences: which approach it was pursuing, what it established
or ruled out, how far it got, and what remained unfinished. Be concrete so another
worker can resume or judge it. Do NOT try to finish the solution yourself.
```

**Retour des tests d'échantillons au manager** (préfixé au résultat du worker) — succès : `[SAMPLE TESTS: PASSED all {n} public samples -- the solution looks correct.]` ; échec : `[SAMPLE TESTS: FAILED -- passed {p}/{t}. The current solution is WRONG. First failing case: input=… expected=… got=…. Fix the bug or, if this approach keeps failing, switch to a DIFFERENT approach.]`. Exécution réelle en sous-processus (`python solution.py`, stdin des tests publics, timeout 10 s).

**Baseline single** : le même modèle, le `solver_system` seul, le problème en un appel, température 0,2 — pas de workspace, pas de boucle.

### Boucle (`multiagent_solve`)

plan → brainstorm → manage → [worker → tests d'échantillons → manage]* jusqu'à `done`, tâche répétée, ou budget de 10 rondes → finaliseur si nécessaire. Chaque rôle est le même modèle en contexte frais ; le workspace fichiers est le seul état partagé.

## Licences (NOTICE.md, résumé)

Copyright (c) 2026 Persis Capital Inc. Deux licences par chemin : code (`codebase/v2-current/`, `codebase/v1-be9dfa2/`, `paper_plot_script/`) MIT ; papier, figures, résultats et workspaces (`paper/`, `assets/`, `runs/`) CC BY 4.0. Exceptions : `codebase/livecodebench/` est un fork MIT de LiveCodeBench (avec composants Apache-2.0/MIT, voir son NOTICE) ; chaque `runs/**/ws/**/task.md` porte l'énoncé d'un problème LiveCodeBench (AtCoder, LeetCode, Codeforces) appartenant à ses éditeurs d'origine ; les fichiers de gabarit LaTeX (`iclr2027_conference.sty`/`.bst`, `natbib.sty`, `fancyhdr.sty`) gardent leurs propres termes (LPPL pour la plupart). Attribution demandée : « Victor Gao, Vida Khosrowshahi, Ali Khosrowshahi, Xihao Sun, Juhyun Lee and Simon (Sang Won) Lee. *Zero-Shot Self-Orchestration with Ledger-Based Control Improves Coding in Language Models*. 2026. »

## Ce que ce dépôt ajoute aux autres sources de `knowledge/`

1. **Un scaffold d'orchestration mesuré, minimal, générique et libre** : ~500 lignes, aucune heuristique de benchmark, prompts génériques — le contraste utile avec AVO (boucle interne P→I→E→B d'un agent unique) et SKILL.state (état structuré mutable) : ici l'état partagé est un ledger de fichiers et la décomposition se fait entre INSTANCES fraîches du même modèle.
2. **Des transcripts complets publiés** (`runs/`) : la matière première des analyses §4.1–4.4 du papier (mécanismes de gain, boucles de rumination, régressions), consultable appel par appel.
3. **Des mesures directement pertinentes pour le modèle de travail de ce dépôt** : `qwen3.6:35b` (le défaut H3.1) est le perdant type du scaffold (−1,2 à 16k off, −9 à 128k off, n.s./négatif) tandis que `qwen3.8:27b` (présent sur l'endpoint, non évalué) en est le grand gagnant (+23,4, niveau frontier auto-hébergé) ; toute conclusion pour ce dépôt passe par la mesure, pas par transposition.
