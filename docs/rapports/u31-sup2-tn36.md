# Campagne ARC-AGI-3 — live

Run : `u31-sup2-tn36`

## Résultat

- mode : **live**
- score global (moyenne des RHAE de jeu) : **0.00**
- jeux joués : **1**
- plafonds : 80 actions/niveau, 300 actions/jeu, 400 tours max, temps/jeu 1200.0, tokens/jeu 1500000

## Par jeu

| Jeu | Niveaux complétés | Actions | Baseline | RHAE | Arrêt |
|---|---|---|---|---|---|
| `tn36-ef4dde99` | 0 / 7 | 28 | 317 | 0.00 | budget de temps du jeu épuisé (1200.0 s) |

## Détail par niveau

| Jeu | Niveau | Baseline hₗ | Actions aₗ | Complété | Poids wₗ |
|---|---|---|---|---|---|
| `tn36-ef4dde99` | 1 | 32 | 28 | non | 1 |
| `tn36-ef4dde99` | 2 | 72 | 0 | non | 2 |
| `tn36-ef4dde99` | 3 | 26 | 0 | non | 3 |
| `tn36-ef4dde99` | 4 | 40 | 0 | non | 4 |
| `tn36-ef4dde99` | 5 | 30 | 0 | non | 5 |
| `tn36-ef4dde99` | 6 | 55 | 0 | non | 6 |
| `tn36-ef4dde99` | 7 | 62 | 0 | non | 7 |

## Coûts

- appels au modèle : **38**
- tokens de prompt : **347703**
- tokens générés : **23016**
- durée d'inférence cumulée : **1155.30 s**
- actions dépensées : **28**
- tours joués : **37**
- durée cumulée de jeu : **1233.89 s**

## Événements

- continuations en contexte frais : **0**
- refus de contexte (HTTP 413) absorbés : **0**
- interventions du superviseur : **1**
- versions committées à la lignée : **0**
- parties perdues (game over) : **0**

## Comparaison aux références publiées

| Source | RHAE | Actions |
|---|---|---|
| **cette campagne** | **0.00** | **28** |
| AVO (billet NVIDIA, 2026-08-21) | 100.00 | 6624 |
| VISTA (page projet) | 100.00 | 7542 |
| Tycho, Opus 5 | 100.00 | 6641 |

## Limites et écarts

- Scorecard de la campagne : `06d3b740-10a5-4945-afc5-d89aad3ae0a4`.
- Au moins un jeu s'est arrêté sur : budget de temps du jeu épuisé (1200.0 s).
- Jeux non terminés : `tn36-ef4dde99`. Leur RHAE est plafonné par la complétion (§A6.1).
