# Campagne ARC-AGI-3 officielle — U25, tranche 2 : rapport final agrégé (A7.3)

Campagne du 2026-09-17 au 2026-09-26, sessions planifiées (U31, cible « campagne
ARC au périmètre U25 », déclencheur constaté le 2026-09-17). Un scorecard par jeu
(une invocation `run-arc` par jeu, machine éphémère) ; les 25 jeux déclarés par
`/api/games` sont tous joués une fois, rapports `docs/rapports/u25-t2-<jeu>.md`.
Agrégats calculés depuis ces 25 rapports le 2026-09-27 ; les compteurs fins
(actions invalides, retries de patch, observations inchangées) viennent des relevés
par jeu du journal — les `runs/` sont éphémères.

## Résultat global

- mode : **live** (API officielle ARC-AGI-3, autorisation du responsable 2026-08-30)
- **score global (moyenne des RHAE de jeu) : 0,00** — aucun niveau complété sur aucun jeu
- jeux joués : **25/25** ; niveaux complétés : **0/183**
- modèle : `qwen3.8:27b` (décision du 2026-09-12), mode `state`, gardes H16,
  mécanismes U34/U35/U37 actifs, fenêtre 229 376
- plafonds par jeu : 80 actions/niveau, 300 actions/jeu, 1 500 000 tokens/jeu,
  400 tours ; temps/jeu **1 200 s** pour `ls20` et `tr87`, **2 400 s** pour les
  23 autres (point tranché le 2026-09-18)

## Par jeu

| Jeu | Niveaux | Actions | Appels | Tokens prompt | Inférence (s) | Tours | Durée (s) | Superviseur | Plafond (s) |
|---|---|---|---|---|---|---|---|---|---|
| `ar25-0c556536` | 0 / 8 | 20 | 27 | 273 652 | 1 269 | 25 | 2 470 | 1 | 2 400 |
| `bp35-0a0ad940` | 0 / 9 | 16 | 30 | 361 012 | 1 467 | 27 | 2 565 | 0 | 2 400 |
| `cd82-fb555c5d` | 0 / 6 | 20 | 30 | 294 126 | 1 198 | 25 | 2 660 | 1 | 2 400 |
| `cn04-2fe56bfb` | 0 / 6 | 19 | 24 | 328 022 | 1 555 | 24 | 2 467 | 0 | 2 400 |
| `dc22-fdcac232` | 0 / 6 | 20 | 30 | 287 364 | 1 228 | 22 | 2 510 | 1 | 2 400 |
| `ft09-0d8bbf25` | 0 / 6 | 20 | 28 | 281 491 | 1 367 | 26 | 2 571 | 1 | 2 400 |
| `g50t-5849a774` | 0 / 7 | 20 | 25 | 244 216 | 1 315 | 21 | 2 429 | 1 | 2 400 |
| `ka59-38d34dbb` | 0 / 7 | 16 | 29 | 289 741 | 1 379 | 25 | 2 480 | 0 | 2 400 |
| `lf52-271a04aa` | 0 / 10 | 16 | 25 | 312 285 | 1 471 | 20 | 2 422 | 0 | 2 400 |
| `lp85-305b61c3` | 0 / 8 | 19 | 26 | 260 831 | 1 486 | 26 | 2 490 | 0 | 2 400 |
| `ls20-9607627b` | 0 / 7 | 12 | 14 | 138 423 | 675 | 13 | 1 207 | 0 | 1 200 |
| `m0r0-492f87ba` | 0 / 6 | 12 | 28 | 344 853 | 1 370 | 24 | 2 409 | 0 | 2 400 |
| `r11l-495a7899` | 0 / 6 | 19 | 26 | 253 674 | 1 413 | 25 | 2 425 | 0 | 2 400 |
| `re86-8af5384d` | 0 / 8 | 24 | 26 | 257 219 | 1 307 | 25 | 2 465 | 1 | 2 400 |
| `s5i5-18d95033` | 0 / 8 | 16 | 27 | 269 336 | 1 389 | 26 | 2 413 | 0 | 2 400 |
| `sb26-7fbdac44` | 0 / 8 | 17 | 26 | 264 531 | 1 327 | 22 | 2 414 | 0 | 2 400 |
| `sc25-635fd71a` | 0 / 6 | 20 | 30 | 299 326 | 1 133 | 27 | 2 423 | 1 | 2 400 |
| `sk48-d8078629` | 0 / 8 | 25 | 30 | 291 219 | 1 184 | 28 | 2 473 | 1 | 2 400 |
| `sp80-589a99af` | 0 / 6 | 16 | 25 | 338 944 | 1 484 | 21 | 2 439 | 0 | 2 400 |
| `su15-1944f8ab` | 0 / 9 | 14 | 29 | 283 027 | 1 382 | 25 | 2 423 | 0 | 2 400 |
| `tn36-ef4dde99` | 0 / 7 | 22 | 29 | 283 090 | 1 133 | 27 | 2 493 | 1 | 2 400 |
| `tr87-cd924810` | 0 / 6 | 11 | 15 | 150 853 | 646 | 13 | 1 217 | 0 | 1 200 |
| `tu93-0768757b` | 0 / 9 | 22 | 26 | 254 119 | 1 305 | 23 | 2 477 | 1 | 2 400 |
| `vc33-5430563c` | 0 / 7 | 17 | 31 | 303 174 | 1 289 | 30 | 2 465 | 0 | 2 400 |
| `wa30-ee6fef47` | 0 / 9 | 21 | 29 | 283 870 | 1 214 | 22 | 2 478 | 1 | 2 400 |

Tous les jeux se sont arrêtés au plafond de temps. RHAE 0,00 partout.

## Coûts agrégés (25 jeux)

- appels au modèle : **665** ; tokens de prompt : **6 948 398** ; tokens générés : **331 257**
- durée d'inférence cumulée : **8,9 h** (32 000 s) ; durée cumulée de jeu : **16,5 h** (59 296 s)
- actions dépensées : **454** ; tours joués : **592**
- sur les 23 jeux à 2 400 s : **18,7 actions/jeu**, **132 s par action**, **89 s par
  appel** dont **48 s d'inférence** — 10 470 tokens de prompt et 497 générés par appel

## Événements

- continuations en contexte frais : 0 ; HTTP 413 : 0 ; game over : 0 ; résumés de
  coupure : 0 — sur les 25 jeux
- pas d'idéation d'ouverture : 25/25 ; interventions du superviseur : **11**
  (toutes au seuil des 20 actions, chacune avec sonde fraîche et curation du
  ledger appliquée) ; 14 jeux n'ont jamais atteint le seuil (11 à 19 actions)
- perte de première tentative au pont 443 : **~680 appels sur 681**, tous
  récupérés par l'échelle §H4.5 (quelques escalades t2/t3, aucune mort de
  transport) — cause mesurée le 2026-09-27 : préremplissage froid, voir
  `docs/SPEC_HARNAIS.md` §H15.11
- actions invalides refusées en les nommant : **93 sur les 19 jeux** dont le
  journal porte le compteur (362 actions jouées sur ces jeux, ~0,26 par action) ;
  motifs relevés sur les 5 derniers jeux : valeurs manquantes ou en trop (16),
  nom d'outil hors espace exposé (1)
- retries de patch (§H15.4) : **52 sur 19 jeux**, tous récupérés
- pas à observation inchangée : **69 sur les 14 jeux** qui portent le compteur (~25 % des pas)

## Comparaison à la tranche 1 (`u25-t1-final.md`, `qwen3.6:35b`, 1 200 s/jeu)

| | Tranche 1 | Tranche 2 |
|---|---|---|
| modèle | `qwen3.6:35b` | `qwen3.8:27b` |
| plafond de temps | 1 200 s | 2 400 s (23 jeux), 1 200 s (2 jeux) |
| niveaux complétés | 0/183 | 0/183 |
| actions / jeu | 29,5 | 18,2 (18,7 à 2 400 s) |
| appels / jeu | 41 | 26,6 |
| secondes / action (durée de jeu) | 41,5 | 131 |
| inférence / appel | 28 s | 48 s |
| perte hors inférence / appel | ~2 s | ~41 s (première tentative perdue) |
| tokens de prompt / appel | 9 744 | 10 449 |
| tokens générés / appel | 495 | 498 |
| actions invalides / action | 0,25 (161/646) | 0,26 (93/362, 19 jeux) |
| interventions du superviseur | 0 | 11 |

Lecture : avec un budget de temps doublé, la tranche 2 a joué ~40 % d'actions en
moins par jeu — le débit par action est divisé par trois. Deux composantes,
toutes deux mesurées : l'inférence par appel passe de 28 s à 48 s (modèle plus
lent à générer), et chaque appel perd ~41 s hors inférence, la première tentative
étant coupée par le pont 443 pendant un préremplissage froid de ~10 500 tokens
(~170 tokens/s). L'amélioration §H15.8 de la tranche 1 (paramètres annoncés) n'a
pas réduit le taux d'actions invalides (0,26 contre 0,25 par action) ; les motifs
ont changé (plus de noms inventés en série, des valeurs manquantes ou en trop).

## Comparaison aux références publiées

| Source | RHAE | Actions |
|---|---|---|
| **cette campagne** | **0,00** | **454** |
| AVO (billet NVIDIA, 2026-08-21) | 100,00 | 6 624 |
| VISTA (page projet) | 100,00 | 7 542 |
| Tycho, Opus 5 | 100,00 | 6 641 |

## Écarts au périmètre et limites

- Le plafond de TEMPS a lié sur les 25 jeux : 11 à 25 actions par jeu, toujours
  sous la baseline humaine du seul premier niveau. Les plafonds d'actions, de
  tokens et de tours ne sont jamais approchés.
- Le plafond de temps a été porté de 1 200 s à 2 400 s après les deux premiers
  jeux (point tranché le 2026-09-18) : les agrégats mêlent deux périmètres, nommés
  dans la table.
- Scorecards : un par jeu, tous fermés, réconciliation exacte à chaque fois ;
  identifiants dans chaque rapport de jeu.
