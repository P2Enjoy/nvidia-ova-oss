# Campagne ARC-AGI-3 — live

Run : `u31-obs2-tn36`

## Résultat

- mode : **live**
- score global (moyenne des RHAE de jeu) : **0.00**
- jeux joués : **1**
- plafonds : 80 actions/niveau, 300 actions/jeu, 400 tours max, temps/jeu 1200.0, tokens/jeu 1500000

## Par jeu

| Jeu | Niveaux complétés | Actions | Baseline | RHAE | Arrêt |
|---|---|---|---|---|---|
| `tn36-ef4dde99` | 0 / 7 | 26 | 317 | 0.00 | budget de temps du jeu épuisé (1200.0 s) |

## Détail par niveau

| Jeu | Niveau | Baseline hₗ | Actions aₗ | Complété | Poids wₗ |
|---|---|---|---|---|---|
| `tn36-ef4dde99` | 1 | 32 | 26 | non | 1 |
| `tn36-ef4dde99` | 2 | 72 | 0 | non | 2 |
| `tn36-ef4dde99` | 3 | 26 | 0 | non | 3 |
| `tn36-ef4dde99` | 4 | 40 | 0 | non | 4 |
| `tn36-ef4dde99` | 5 | 30 | 0 | non | 5 |
| `tn36-ef4dde99` | 6 | 55 | 0 | non | 6 |
| `tn36-ef4dde99` | 7 | 62 | 0 | non | 7 |

## Coûts

- appels au modèle : **38**
- tokens de prompt : **351849**
- tokens générés : **24197**
- durée d'inférence cumulée : **1200.19 s**
- actions dépensées : **26**
- tours joués : **34**
- durée cumulée de jeu : **1223.73 s**

## Événements

- continuations en contexte frais : **0**
- refus de contexte (HTTP 413) absorbés : **0**
- interventions du superviseur : **0**
- versions committées à la lignée : **0**
- parties perdues (game over) : **0**

## Comparaison aux références publiées

| Source | RHAE | Actions |
|---|---|---|
| **cette campagne** | **0.00** | **26** |
| AVO (billet NVIDIA, 2026-08-21) | 100.00 | 6624 |
| VISTA (page projet) | 100.00 | 7542 |
| Tycho, Opus 5 | 100.00 | 6641 |

## Limites et écarts

- Scorecard de la campagne : `2a3d6edb-1e6b-47de-83d0-5b1ad361fe0c`.
- Au moins un jeu s'est arrêté sur : budget de temps du jeu épuisé (1200.0 s).
- Jeux non terminés : `tn36-ef4dde99`. Leur RHAE est plafonné par la complétion (§A6.1).
