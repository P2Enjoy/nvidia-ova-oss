# Campagne pilote U24, run `pilote-u24c` — 2026-09-01

Copie committée du `report.md` du run (`runs/` est ignoré par git), exigée par la
Definition of Done de U24. Scorecard officiel : `2e57f802-d74a-437f-a376-95f56ffd4904`.

Faits mesurés du run, relevés dans `metrics.jsonl` et le journal d'exécution :

- jeu `cd82-fb555c5d` servi, `RESET` accepté, 3 actions jouées (réconciliation
  locale/API exacte : 3 = 3), gardes H16 exercées (documentaire redemandée 2× puis
  satisfaite ; évaluation redemandée 1×) ;
- 7 appels d'inférence aboutis, 149 705 tokens de prompt, 3 185 générés,
  fenêtre demandée 98 304 ; croissance du prompt 9 378 → 38 515 en 7 appels ;
- casse à ~48 k de prompt : série de `500` à retries épuisés (4 tentatives,
  ~3,5 min) → jeu clos en ÉCHEC NOMMÉ, campagne terminée proprement, scorecard
  fermé et résumé persisté — le comportement corrigé la veille a fonctionné ;
- défaut mis au jour : la section Coûts du rapport ci-dessous annonce zéro
  tokens/durée/actions alors que les métriques portent la dépense réelle — les
  coûts d'un jeu clos en échec nommé étaient perdus par l'agrégation (corrigé,
  spéc A7.3 amendée dans le même changement).

---

# Campagne ARC-AGI-3 — live

Run : `pilote-u24c`

## Résultat

- mode : **live**
- score global (moyenne des RHAE de jeu) : **0.00**
- jeux joués : **0** — jeux refusés par le backend : **1**
- plafonds : 80 actions/niveau, 300 actions/jeu, 400 tours max, temps/jeu 1800.0, tokens/jeu 1500000

## Par jeu

_Aucun jeu joué._

## Jeux refusés par le backend (hors score)

- `cd82-fb555c5d` : ServerError: erreur serveur HTTP 500

## Détail par niveau

_Aucun niveau._

## Coûts

- appels au modèle : **7**
- tokens de prompt : **0**
- tokens générés : **0**
- actions dépensées : **0**
- tours joués : **0**
- durée cumulée : **0.00 s**

## Événements

- continuations en contexte frais : **0**
- refus de contexte (HTTP 413) absorbés : **0**
- interventions du superviseur : **0**
- versions committées à la lignée : **0**
- parties perdues (game over) : **0**

## Comparaison aux références publiées

| Source | RHAE | Actions |
|---|---|---|
| **cette campagne** | **0.00** | **0** |
| AVO (billet NVIDIA, 2026-08-21) | 100.00 | 6624 |
| VISTA (page projet) | 100.00 | 7542 |
| Tycho, Opus 5 | 100.00 | 6641 |

## Limites et écarts

- Scorecard de la campagne : `2e57f802-d74a-437f-a376-95f56ffd4904`.
