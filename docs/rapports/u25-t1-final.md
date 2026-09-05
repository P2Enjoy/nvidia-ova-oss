# Campagne ARC-AGI-3 officielle — U25, tranche 1 : rapport final agrégé (A7.3)

Campagne du 2026-09-04/05, sessions planifiées suites 43 à 45. Un scorecard par jeu
(une invocation `run-arc` par jeu, motif machine éphémère — journal suite 43) ;
les 25 jeux déclarés par `/api/games` sont tous joués une fois.

## Résultat global

- mode : **live** (API officielle ARC-AGI-3, autorisation du responsable 2026-08-30)
- **score global (moyenne des RHAE de jeu) : 0,00** — aucun niveau complété sur aucun jeu
- jeux joués : **25/25** ; niveaux complétés : **0/183**
- modèle : `qwen3.6:35b`, mode de contexte `state`, gardes H16 actives, fenêtre 229 376
- plafonds par jeu : 80 actions/niveau, 300 actions/jeu, **1 200 s/jeu**, 1 500 000 tokens/jeu, 400 tours

## Par jeu

| Jeu | Niveaux | Actions | Baseline jeu | RHAE | Arrêt |
|---|---|---|---|---|---|
| `ar25-0c556536` | 0 / 8 | 35 | 748 | 0.00 | plafond de temps |
| `bp35-0a0ad940` | 0 / 9 | 16 | 651 | 0.00 | plafond de temps |
| `cd82-fb555c5d` | 0 / 6 | 32 | 171 | 0.00 | plafond de temps |
| `cn04-2fe56bfb` | 0 / 6 | 27 | 789 | 0.00 | plafond de temps |
| `dc22-fdcac232` | 0 / 6 | 33 | 1228 | 0.00 | plafond de temps |
| `ft09-0d8bbf25` | 0 / 6 | 27 | 208 | 0.00 | plafond de temps |
| `g50t-5849a774` | 0 / 7 | 18 | 879 | 0.00 | plafond de temps |
| `ka59-38d34dbb` | 0 / 7 | 32 | 730 | 0.00 | plafond de temps |
| `lf52-271a04aa` | 0 / 10 | 39 | 1339 | 0.00 | plafond de temps |
| `lp85-305b61c3` | 0 / 8 | 33 | 388 | 0.00 | plafond de temps |
| `ls20-9607627b` | 0 / 7 | 47 | 776 | 0.00 | plafond de temps |
| `m0r0-492f87ba` | 0 / 6 | 24 | 1107 | 0.00 | plafond de temps |
| `r11l-495a7899` | 0 / 6 | 35 | 233 | 0.00 | plafond de temps |
| `re86-8af5384d` | 0 / 8 | 38 | 1255 | 0.00 | plafond de temps |
| `s5i5-18d95033` | 0 / 8 | 28 | 638 | 0.00 | plafond de temps |
| `sb26-7fbdac44` | 0 / 8 | 21 | 213 | 0.00 | plafond de temps |
| `sc25-635fd71a` | 0 / 6 | 18 | 350 | 0.00 | plafond de temps |
| `sk48-d8078629` | 0 / 8 | 57 | 1070 | 0.00 | plafond de temps |
| `sp80-589a99af` | 0 / 6 | 30 | 518 | 0.00 | plafond de temps |
| `su15-1944f8ab` | 0 / 9 | 11 | 361 | 0.00 | plafond de temps |
| `tn36-ef4dde99` | 0 / 7 | 14 | 317 | 0.00 | plafond de temps |
| `tr87-cd924810` | 0 / 6 | 50 | 414 | 0.00 | plafond de temps |
| `tu93-0768757b` | 0 / 9 | 10 | 462 | 0.00 | plafond de temps |
| `vc33-5430563c` | 0 / 7 | 40 | 447 | 0.00 | plafond de temps |
| `wa30-ee6fef47` | 0 / 9 | 22 | 1843 | 0.00 | plafond de temps |

## Coûts agrégés (25 jeux, hors doublon)

- appels au modèle : **1027**
- tokens de prompt : **10 007 214**
- tokens générés : **508 492**
- durée d'inférence cumulée : **8.0 h** (28922 s)
- actions dépensées : **737** ; tours joués : **995**
- durée cumulée de jeu : **8.5 h**
- moyennes par jeu : ~41 appels, ~29 actions, ~39 tours

## Événements

- continuations en contexte frais : 0 ; HTTP 413 : 0 ; interventions du superviseur : 0 ;
  game over : 0 ; refus d'outil : 0 — sur l'ensemble des 25 jeux.
- **Doublon** : `tu93-0768757b` joué deux fois par deux sessions chevauchées avant le
  protocole anti-collision (backlog U25) — second run 0/9 niveaux,
  23 actions, rapport `u25-t1-tu93-bis.md`, scorecard `7af8dabf…`.
  Le premier run fait foi ; le doublon n'entre pas dans les agrégats.

## Comparaison aux références publiées

| Source | RHAE | Actions |
|---|---|---|
| **cette campagne** | **0,00** | **737** |
| AVO (billet NVIDIA, 2026-08-21) | 100,00 | 6 624 |
| VISTA (page projet) | 100,00 | 7 542 |
| Tycho, Opus 5 | 100,00 | 6 641 |

## Écarts au périmètre et limites

- **Le plafond de TEMPS (1 200 s/jeu) a lié sur les 25 jeux** : ~25–30 s d'inférence
  par tour ≈ 37–46 tours par jeu, soit 10 à 57 actions — sous la baseline humaine du
  seul premier niveau de chaque jeu. Les plafonds d'actions (80/niveau, 300/jeu), de
  tokens (1,5 M/jeu) et de tours (400) ne sont jamais approchés. Toute lecture du
  score doit tenir compte de cette borne : la campagne mesure le harnais SOUS un
  budget de temps serré, pas à l'épuisement de ses actions.
- Les références publiées (AVO, VISTA, Tycho) atteignent 100,00 avec 6 600–7 500
  actions par campagne, soit ~9× le total d'actions que le budget de temps a permis
  ici ; l'écart de conditions est structurel, pas incident.
- Ordre du listing `/api/games` instable d'un jour à l'autre (mesuré suite 44) ;
  l'ensemble des jeux joués fait foi, consigné au backlog U25.
- Scorecards : un par jeu, tous fermés ; identifiants dans chaque rapport de jeu
  (`docs/rapports/u25-t1-<jeu>.md`).
