# Campagne ARC-AGI-3 — live

Run : `u31-obs3-tu93`

## Résultat

- mode : **live**
- score global (moyenne des RHAE de jeu) : **0.00**
- jeux joués : **1**
- plafonds : 80 actions/niveau, 300 actions/jeu, 400 tours max, temps/jeu 1200.0, tokens/jeu 1500000

## Par jeu

| Jeu | Niveaux complétés | Actions | Baseline | RHAE | Arrêt |
|---|---|---|---|---|---|
| `tu93-0768757b` | 0 / 9 | 41 | 462 | 0.00 | budget de temps du jeu épuisé (1200.0 s) |

## Détail par niveau

| Jeu | Niveau | Baseline hₗ | Actions aₗ | Complété | Poids wₗ |
|---|---|---|---|---|---|
| `tu93-0768757b` | 1 | 19 | 41 | non | 1 |
| `tu93-0768757b` | 2 | 16 | 0 | non | 2 |
| `tu93-0768757b` | 3 | 34 | 0 | non | 3 |
| `tu93-0768757b` | 4 | 42 | 0 | non | 4 |
| `tu93-0768757b` | 5 | 123 | 0 | non | 5 |
| `tu93-0768757b` | 6 | 80 | 0 | non | 6 |
| `tu93-0768757b` | 7 | 14 | 0 | non | 7 |
| `tu93-0768757b` | 8 | 23 | 0 | non | 8 |
| `tu93-0768757b` | 9 | 111 | 0 | non | 9 |

## Coûts

- appels au modèle : **46**
- tokens de prompt : **420772**
- tokens générés : **20405**
- durée d'inférence cumulée : **1176.32 s**
- actions dépensées : **41**
- tours joués : **46**
- durée cumulée de jeu : **1205.74 s**

## Événements

- continuations en contexte frais : **0**
- refus de contexte (HTTP 413) absorbés : **0**
- interventions du superviseur : **0**
- versions committées à la lignée : **0**
- parties perdues (game over) : **0**

## Comparaison aux références publiées

| Source | RHAE | Actions |
|---|---|---|
| **cette campagne** | **0.00** | **41** |
| AVO (billet NVIDIA, 2026-08-21) | 100.00 | 6624 |
| VISTA (page projet) | 100.00 | 7542 |
| Tycho, Opus 5 | 100.00 | 6641 |

## Limites et écarts

- Scorecard de la campagne : `cc8af56e-8c34-4c88-bb66-4d798be03854`.
- Au moins un jeu s'est arrêté sur : budget de temps du jeu épuisé (1200.0 s).
- Jeux non terminés : `tu93-0768757b`. Leur RHAE est plafonné par la complétion (§A6.1).
