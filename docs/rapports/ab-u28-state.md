# A/B des modes de contexte en conditions réelles (U28), run `ab-u28-state` — 2026-09-01

Copie committée du `report.md` du run (`runs/` est ignoré par git), précédée du
dépouillement comparatif. Scorecard officiel : `4cedc4e1-e9fd-4ab2-96cf-34a35385cb81`,
fermé, résumé persisté, réconciliation compteurs locale/API EXACTE (33 actions = 33,
`divergences: []`, par niveau identique).

Terme A : `pilote-u24d` (mode `transcript`, `docs/rapports/pilote-u24d.md`).
Terme B : `ab-u28-state` (mode `state`, ce run). Mêmes jeu (`cd82-fb555c5d`,
baselines [55, 8, 41, 21, 23, 23] revérifiées identiques avant lancement), mêmes
plafonds (80 actions/niveau, 300 actions/jeu, 1 200 s/jeu, 1 500 000 tokens/jeu,
400 tours), même fenêtre (98 304), mêmes gardes H16 actives, même modèle
(`qwen3.6:35b`) à travers le même pont.

## Mesures en main

| Mesure | `transcript` (u24d) | `state` (u28) |
|---|---|---|
| niveaux complétés | 0/6 | 0/6 |
| RHAE | 0.00 | 0.00 |
| actions jouées | 6 | **33** |
| tours joués | 6 | 42 |
| appels au modèle | 28 | 43 |
| tokens de prompt cumulés | 1 105 505 | **389 879** |
| tokens générés | 7 874 | 13 663 |
| durée d'inférence cumulée | 554,6 s | 863,2 s |
| durée de jeu (plafond 1 200 s) | 1 321,3 s | 1 209,4 s |
| prompt maximal observé | 73 180 | **9 223** |
| prompt moyen par appel | ~39 482 | **9 067** (min 8 890) |
| continuations en contexte frais | 2 | **0** |
| refus de contexte (413) | 0 | 0 |
| retries de patch (§H15.4) | — | 1 (clé inconnue refusée, corrigée au retry) |
| actions invalides (résolution §H15.8) | — | 3 (2 arité, 1 ponctuation traînante) |
| gardes H16 | actives (redemandes mesurées dès le pilote b) | actives, 7 redemandes (2 prédiction, 5 évaluation) |
| interventions du superviseur | 0 | 1 (rafale Bug-Fixing) |
| incidents endpoint | 500 transitoires absorbés | 1 `500` absorbé au 1er retry |

Dérivés : ~36,6 s et ~11 815 tokens de prompt par action en `state`, contre
~220 s et ~184 251 en `transcript` — **5,5× plus d'actions dans le même budget de
temps, ~15× moins de tokens de prompt par action**.

## Lecture

- **L'empreinte O(1) du papier SKILL.state se constate en réel** : prompt borné
  entre 8 890 et 9 223 tokens sur 43 appels, aucune continuation, la zone de
  casse de l'endpoint (~120 k à travers le pont) n'est jamais approchée — là où
  `transcript` montait à 73 180 avec 2 continuations.
- **La validation stricte des patchs travaille** : une clé hors schéma
  (`actions_niveau`) a été refusée en nommant le champ, et le modèle s'est
  corrigé au retry suivant (§H15.4, taxonomie SKILL.state §5.7).
- **Le débit d'exploration change d'ordre de grandeur** (6 → 33 actions), mais
  ni l'un ni l'autre mode n'a complété de niveau en 20 min sur ce jeu : le RHAE
  0.00 reste plafonné par la complétion (§A6.1) des deux côtés — l'A/B mesure le
  COÛT et la MÉCANIQUE, pas encore la capacité de résolution.
- Bruit de format mesuré : « action1, » (ponctuation traînante) a coûté un tour ;
  normalisation générique livrée dans la même session (§H15.8 amendé, test
  d'intégration rouge avant correction).
- Limite de comparaison : `transcript` bénéficie du cache de préfixe côté
  serveur (les tokens de prompt comptés ne disent pas tous un préremplissage
  froid) ; la durée d'inférence cumulée (554,6 s contre 863,2 s) le reflète.
  À budget de TEMPS égal, `state` a néanmoins joué 5,5× plus d'actions.

## Recommandation (consignée, décision du responsable attendue avec U25)

Pour la campagne étendue U25, **mode `state` recommandé par défaut** : même
budget de temps → 5,5× plus d'actions jouées, prompt borné loin de la zone de
casse de l'endpoint, zéro continuation, coût par action ~15× moindre en tokens
de prompt, gardes et superviseur opérants. Le mode `transcript` reste
l'alternative configurable (`AVO_CONTEXT_MODE`), notamment si un jeu
récompensait la mémoire longue intra-niveau que Σ résume. La décision finale
appartient au responsable, avec le périmètre U25 (arbitrage demandé au journal,
2026-09-01 suite 6).

---

# Campagne ARC-AGI-3 — live

Run : `ab-u28-state`

## Résultat

- mode : **live**
- score global (moyenne des RHAE de jeu) : **0.00**
- jeux joués : **1**
- plafonds : 80 actions/niveau, 300 actions/jeu, 400 tours max, temps/jeu 1200.0, tokens/jeu 1500000

## Par jeu

| Jeu | Niveaux complétés | Actions | Baseline | RHAE | Arrêt |
|---|---|---|---|---|---|
| `cd82-fb555c5d` | 0 / 6 | 33 | 171 | 0.00 | budget de temps du jeu épuisé (1200.0 s) |

## Détail par niveau

| Jeu | Niveau | Baseline hₗ | Actions aₗ | Complété | Poids wₗ |
|---|---|---|---|---|---|
| `cd82-fb555c5d` | 1 | 55 | 33 | non | 1 |
| `cd82-fb555c5d` | 2 | 8 | 0 | non | 2 |
| `cd82-fb555c5d` | 3 | 41 | 0 | non | 3 |
| `cd82-fb555c5d` | 4 | 21 | 0 | non | 4 |
| `cd82-fb555c5d` | 5 | 23 | 0 | non | 5 |
| `cd82-fb555c5d` | 6 | 23 | 0 | non | 6 |

## Coûts

- appels au modèle : **43**
- tokens de prompt : **389879**
- tokens générés : **13663**
- durée d'inférence cumulée : **863.15 s**
- actions dépensées : **33**
- tours joués : **42**
- durée cumulée de jeu : **1209.38 s**

## Événements

- continuations en contexte frais : **0**
- refus de contexte (HTTP 413) absorbés : **0**
- interventions du superviseur : **1**
- versions committées à la lignée : **0**
- parties perdues (game over) : **0**

## Comparaison aux références publiées

| Source | RHAE | Actions |
|---|---|---|
| **cette campagne** | **0.00** | **33** |
| AVO (billet NVIDIA, 2026-08-21) | 100.00 | 6624 |
| VISTA (page projet) | 100.00 | 7542 |
| Tycho, Opus 5 | 100.00 | 6641 |

## Limites et écarts

- Scorecard de la campagne : `4cedc4e1-e9fd-4ab2-96cf-34a35385cb81`.
- Au moins un jeu s'est arrêté sur : budget de temps du jeu épuisé (1200.0 s).
- Jeux non terminés : `cd82-fb555c5d`. Leur RHAE est plafonné par la complétion (§A6.1).
