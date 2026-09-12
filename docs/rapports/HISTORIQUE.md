# Historique consolidé des lignes de base — bancs et ARC

Tableau consolidé banc × version du harnais × modèle × score, accepté par le
responsable (journal 2026-09-12, suite 3). Les relevés détaillés vivent dans
`docs/JOURNAL.md` (suites citées) et, pour ARC, dans `docs/rapports/`.
Protocoles : banc a `skillexec` h25 bruit 0 seeds 1–3 (moyenne des scores) ;
banc b `ctf` aléatoire h30 seeds 1–10, exécuteur `conteneur` (pass@1) ;
banc c `tau` détail h20 seeds 1–10, utilisateur `llm` (pass) ; ARC : plafonds
§A7.1 constants (80 actions/niveau, 300 actions/jeu, 1 200 s/jeu,
1 500 000 tokens/jeu, 400 tours), mode `state`, gardes actives.

## Banc a — SkillExecBench, environnement dépôt

| Harnais | Modèle | Score moyen (s1/s2/s3) | Relevé |
|---|---|---|---|
| v1.9 pré-§H15.8 | `qwen3.6:35b` | 0,76 (0,80/0,68/0,80) | journal, suite 22 |
| v1.9 | `qwen3.6:35b` | 0,827 (0,88/0,80/0,80) | journal, suite 27 |
| v1.10 | `qwen3.6:35b` | 0,947 (0,96/0,96/0,92) | journal, suite 46 add. 2 |
| v1.10 + éch. §H3.1 (U33) | `qwen3.8:27b` | **0,987** (0,96/1,00/1,00) | journal, 2026-09-12 (U36) |

## Banc a — SkillExecBench, environnement entrepôt

| Harnais | Modèle | Score moyen (s1/s2/s3) | Relevé |
|---|---|---|---|
| v1.9 | `qwen3.6:35b` | 0,77 (0,96/0,92/0,44) | journal, suite 23 |
| v1.9 (réplication) | `qwen3.6:35b` | 0,653 (0,48/0,96/0,52) | journal, suite 24 |
| v1.10 | `qwen3.6:35b` | **0,707** (0,96/0,44/0,72) | journal, suite 46 add. 3 |

Bande de variance inter-réplications de cet environnement : [0,653 ; 0,77] —
l'entrepôt est dominé par la variance de runs, pas par les refus de forme.

## Banc b — InterCode CTF (patron), environnement aléatoire

| Harnais | Modèle | pass@1 | Relevé |
|---|---|---|---|
| v1.9 | `qwen3.6:35b` | 8/10 | journal, suite 37 |
| v1.9 (réplication) | `qwen3.6:35b` | 6/10 | journal, suite 39 |
| v1.10 | `qwen3.6:35b` | **8/10** (échecs s1, s8 — famille `encodage`) | journal, suite 46 add. 4 |

Variance inter-séries mesurée : 6/10 à 8/10.

## Banc c — τ-Bench (patron), environnement détail

| Harnais | Modèle | pass | Relevé |
|---|---|---|---|
| v1.9 | `qwen3.6:35b` | 8/10 | journal, suite 40 |
| v1.9 (réplication) | `qwen3.6:35b` | 9/10 | journal, suite 42 |
| v1.10 | `qwen3.6:35b` | **9/10** (échec s10) | journal, suite 46 add. 5 |

Variance inter-séries mesurée : 8/10 à 9/10.

## ARC-AGI-3 — surfaces de validation historiques

Trois jeux de validation (les seuls dont l'historique porte des mesures
fines) ; RHAE 0,00 partout à ce jour — la comparaison porte sur les actions
valides, les niveaux et l'exploitation des interventions.

| Harnais | Modèle | Jeu | Actions valides | Niveaux | Arrêt | Relevé |
|---|---|---|---|---|---|---|
| v1.10 | `qwen3.6:35b` | `tu93-0768757b` | 40 | 0/9 | temps (1 200 s) | `u31-v110-tu93.md` |
| v1.10 | `qwen3.6:35b` | `tn36-ef4dde99` | 30 | 0/7 | temps (1 200 s) | `u31-v110-tn36.md` |
| v1.10 | `qwen3.6:35b` | `su15-1944f8ab` | 29 | 0/9 | temps (1 200 s) | `u31-v110-su15.md` |
