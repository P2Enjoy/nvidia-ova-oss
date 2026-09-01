# Campagne pilote U24, run `pilote-u24d` — 2026-09-01

Copie committée du `report.md` du run (`runs/` est ignoré par git). Scorecard
officiel : `3b34284d-73b7-464a-8349-7de7bbf4065a`. **Premier pilote U24 mené à
son terme** : jeu joué jusqu'au plafond de temps, arrêt propre, scorecard fermé,
réconciliation compteurs locale/API EXACTE (6 actions = 6, aucune divergence).

Faits mesurés (métriques du run) :

- fenêtre demandée 98 304 (recette du journal) : 2 continuations en contexte
  frais déclenchées, prompt maximal observé 73 180 tokens — la zone de casse de
  l'endpoint (~120 k mesurée le 2026-08-31) n'est jamais approchée ;
- retries patients (§H4.5 amendé cette session, six requêtes) : tous les `500`
  transitoires absorbés, aucun fatal — là où les pilotes b et c mouraient ;
- débits réels `qwen3.6:35b` à travers le pont : 28 appels, 1 105 505 tokens de
  prompt, 7 874 générés, 554,6 s d'inférence pour 6 actions en 1 321 s
  (~3,7 min par action, dominée par le préremplissage et les gardes) ;
- comportement de jeu : 6 actions en 20 min, 0/6 niveaux — le modèle explore
  lentement ; le RHAE de 0.00 est le plafond de la complétion (§A6.1), pas une
  mesure d'efficacité d'actions.

---

# Campagne ARC-AGI-3 — live

Run : `pilote-u24d`

## Résultat

- mode : **live**
- score global (moyenne des RHAE de jeu) : **0.00**
- jeux joués : **1**
- plafonds : 80 actions/niveau, 300 actions/jeu, 400 tours max, temps/jeu 1200.0, tokens/jeu 1500000

## Par jeu

| Jeu | Niveaux complétés | Actions | Baseline | RHAE | Arrêt |
|---|---|---|---|---|---|
| `cd82-fb555c5d` | 0 / 6 | 6 | 171 | 0.00 | budget de temps du jeu épuisé (1200.0 s) |

## Détail par niveau

| Jeu | Niveau | Baseline hₗ | Actions aₗ | Complété | Poids wₗ |
|---|---|---|---|---|---|
| `cd82-fb555c5d` | 1 | 55 | 6 | non | 1 |
| `cd82-fb555c5d` | 2 | 8 | 0 | non | 2 |
| `cd82-fb555c5d` | 3 | 41 | 0 | non | 3 |
| `cd82-fb555c5d` | 4 | 21 | 0 | non | 4 |
| `cd82-fb555c5d` | 5 | 23 | 0 | non | 5 |
| `cd82-fb555c5d` | 6 | 23 | 0 | non | 6 |

## Coûts

- appels au modèle : **28**
- tokens de prompt : **1105505**
- tokens générés : **7874**
- durée d'inférence cumulée : **554.62 s**
- actions dépensées : **6**
- tours joués : **6**
- durée cumulée de jeu : **1321.26 s**

## Événements

- continuations en contexte frais : **2**
- refus de contexte (HTTP 413) absorbés : **0**
- interventions du superviseur : **0**
- versions committées à la lignée : **0**
- parties perdues (game over) : **0**

## Comparaison aux références publiées

| Source | RHAE | Actions |
|---|---|---|
| **cette campagne** | **0.00** | **6** |
| AVO (billet NVIDIA, 2026-08-21) | 100.00 | 6624 |
| VISTA (page projet) | 100.00 | 7542 |
| Tycho, Opus 5 | 100.00 | 6641 |

## Limites et écarts

- Scorecard de la campagne : `3b34284d-73b7-464a-8349-7de7bbf4065a`.
- Au moins un jeu s'est arrêté sur : budget de temps du jeu épuisé (1200.0 s).
- Jeux non terminés : `cd82-fb555c5d`. Leur RHAE est plafonné par la complétion (§A6.1).
