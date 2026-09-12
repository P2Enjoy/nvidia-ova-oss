# Campagne ARC-AGI-3 — live

Run : `u36-arc-base`

## Résultat

- mode : **live**
- score global (moyenne des RHAE de jeu) : **0.00**
- jeux joués : **3**
- plafonds : 80 actions/niveau, 300 actions/jeu, 400 tours max, temps/jeu 1200.0, tokens/jeu 1500000

## Par jeu

| Jeu | Niveaux complétés | Actions | Baseline | RHAE | Arrêt |
|---|---|---|---|---|---|
| `tu93-0768757b` | 0 / 9 | 7 | 462 | 0.00 | budget de temps du jeu épuisé (1200.0 s) |
| `tn36-ef4dde99` | 0 / 7 | 8 | 317 | 0.00 | budget de temps du jeu épuisé (1200.0 s) |
| `su15-1944f8ab` | 0 / 9 | 9 | 361 | 0.00 | budget de temps du jeu épuisé (1200.0 s) |

## Détail par niveau

| Jeu | Niveau | Baseline hₗ | Actions aₗ | Complété | Poids wₗ |
|---|---|---|---|---|---|
| `tu93-0768757b` | 1 | 19 | 7 | non | 1 |
| `tu93-0768757b` | 2 | 16 | 0 | non | 2 |
| `tu93-0768757b` | 3 | 34 | 0 | non | 3 |
| `tu93-0768757b` | 4 | 42 | 0 | non | 4 |
| `tu93-0768757b` | 5 | 123 | 0 | non | 5 |
| `tu93-0768757b` | 6 | 80 | 0 | non | 6 |
| `tu93-0768757b` | 7 | 14 | 0 | non | 7 |
| `tu93-0768757b` | 8 | 23 | 0 | non | 8 |
| `tu93-0768757b` | 9 | 111 | 0 | non | 9 |
| `tn36-ef4dde99` | 1 | 32 | 8 | non | 1 |
| `tn36-ef4dde99` | 2 | 72 | 0 | non | 2 |
| `tn36-ef4dde99` | 3 | 26 | 0 | non | 3 |
| `tn36-ef4dde99` | 4 | 40 | 0 | non | 4 |
| `tn36-ef4dde99` | 5 | 30 | 0 | non | 5 |
| `tn36-ef4dde99` | 6 | 55 | 0 | non | 6 |
| `tn36-ef4dde99` | 7 | 62 | 0 | non | 7 |
| `su15-1944f8ab` | 1 | 22 | 9 | non | 1 |
| `su15-1944f8ab` | 2 | 42 | 0 | non | 2 |
| `su15-1944f8ab` | 3 | 26 | 0 | non | 3 |
| `su15-1944f8ab` | 4 | 115 | 0 | non | 4 |
| `su15-1944f8ab` | 5 | 36 | 0 | non | 5 |
| `su15-1944f8ab` | 6 | 31 | 0 | non | 6 |
| `su15-1944f8ab` | 7 | 8 | 0 | non | 7 |
| `su15-1944f8ab` | 8 | 40 | 0 | non | 8 |
| `su15-1944f8ab` | 9 | 41 | 0 | non | 9 |

## Coûts

- appels au modèle : **34**
- tokens de prompt : **313863**
- tokens générés : **9908**
- durée d'inférence cumulée : **1384.80 s**
- actions dépensées : **24**
- tours joués : **33**
- durée cumulée de jeu : **3745.50 s**

## Événements

- continuations en contexte frais : **0**
- refus de contexte (HTTP 413) absorbés : **0**
- interventions du superviseur : **0**
- versions committées à la lignée : **0**
- parties perdues (game over) : **0**

## Comparaison aux références publiées

| Source | RHAE | Actions |
|---|---|---|
| **cette campagne** | **0.00** | **24** |
| AVO (billet NVIDIA, 2026-08-21) | 100.00 | 6624 |
| VISTA (page projet) | 100.00 | 7542 |
| Tycho, Opus 5 | 100.00 | 6641 |

## Limites et écarts

- Scorecard de la campagne : `3194350d-9d56-4033-ab8d-c1cd0d08f9be`.
- Au moins un jeu s'est arrêté sur : budget de temps du jeu épuisé (1200.0 s).
- Jeux non terminés : `tu93-0768757b`, `tn36-ef4dde99`, `su15-1944f8ab`. Leur RHAE est plafonné par la complétion (§A6.1).
