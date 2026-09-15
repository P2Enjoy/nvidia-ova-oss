# A/B réel U38 — harnais enrichi contre harnais nu, bancs U29, `qwen3.8:27b`

Périmètre consigné au journal AVANT lancement (2026-09-15). Bras NU = lignes de
base U36 (`HISTORIQUE.md`, deux réplications du 2026-09-12, mêmes paramètres,
harnais sans U34/U35/U37). Bras ENRICHI = cette campagne : mécanismes U34
(résumé de coupure), U35 (sonde fraîche), U37 (ledger, idéation, curation) à
leurs défauts `true`, mode `state`, gardes actives, séquentiel, une exécution
live à la fois. Effectifs faibles (3+3+10+10) : lecture qualitative, appariée
seed à seed, jamais surinterprétée.

## Scores

| Banc | Bras nu (U36, 2 répl.) | Bras enrichi (U38) | Lecture |
|---|---|---|---|
| a dépôt (h25, s1–3) | 0,987 · 0,987 | **0,853** (0,56 / 1,00* / 1,00) | sous la bande, porté par s1 seul |
| a entrepôt (h25, s1–3) | 0,867 · 1,00 | **0,96** (1,00 / 0,96 / 0,92) | dans la bande |
| b CTF (h30, s1–10) | 7/9 (s1 non mes.) · 7/10 | **6/9** (s2 non mes.) | ISO seed à seed (voir ci-dessous) |
| c τ (h20, s1–10) | 10/10 · 10/10 | **10/10** (0 violation) | identique |

\* s2 dépôt : rejeu unique après incident HARNAIS corrigé en session (voir
« Défauts corrigés ») ; premier passage 12 correctes / 13 événements avant la
mort — l'épisode allait bien, l'incident était le défaut de validation.

## Appariement CTF seed à seed

| Seed | Famille | Nu (planifiée) | Enrichi | Concordance |
|---|---|---|---|---|
| s1 | encodage | ✗ budget | ✗ budget (30 act.) | = (et MESURABLE ici, là où la série interactive nue l'avait perdu en transport) |
| s2 | fouille | ✓ | non mesurable (2 morts transport, rejeu unique consommé) | infrastructure |
| s3 | encodage | ✓ | ✓ (21 actions) | = |
| s4 | encodage | ✗ budget | ✗ budget | = |
| s5 | piste | ✓ | ✓ (3 actions) | = |
| s6 | piste | ✓ | ✓ (3 actions, REJEU v1.14 après incident harnais corrigé) | = |
| s7 | archive | ✓ | ✓ (14 actions) | = |
| s8 | encodage | ✗ budget | ✗ budget (rejeu après mort transport) | = |
| s9 | binaire | ✓ | ✓ (3 actions) | = |
| s10 | piste | ✓ | ✓ (3 actions) | = |

Sur les 9 seeds mesurables des deux côtés : concordance **9/9** — mêmes
captures, mêmes échecs, tous les échecs de la famille `encodage` sur budget.
Les mécanismes H18 n'ont ni gagné ni perdu un drapeau.

## Le seul écart : dépôt s1 (0,56), l'ancrage de plan — la régression GVS5H §4.4 observée en vrai

L'idéation de s1 a produit un plan CORRECT (« attendre la revue approuvée puis
ouvrir la PR », etc.) ; mais au fil du run le ledger a enflé (une tâche
« commit branch_X » par branche, 11–12 tâches, curation superviseur SANS
réduction 11→12) et l'acteur a exécuté SON plan au lieu de répondre aux
ÉVÉNEMENTS : 11 actions jouées par anticipation, toutes refusées (9 `commit`,
1 `create_pr`, 1 `merge`). Sur le même environnement, s3 — curation agressive
12→2 — fait un sans-faute, et s2 rejoué également : l'écart nu/enrichi du banc
dépôt tient à un seed sur trois. C'est le mode de régression décrit par le
papier (le plan précoce qui ancre l'aval, §4.4), dont les contre-mesures du
papier sont précisément la sonde fraîche (U35, active) et la curation (U37,
active mais qui n'a pas réduit sur ce run).

## Défauts GÉNÉRAUX du harnais découverts et corrigés dans la session (l'objet de U31/U38 : jouer, observer, corriger)

1. **Fusion du ledger trop stricte** (`u38-depot-s2`) : clore une tâche
   existante exigeait la réémission complète ; un patch `{'id','statut'}`
   sémantiquement parfait a tué le run en `RetriesEpuises`. Corrigé : fusion
   champ à champ par `id` (spec H18.1 révisée, prompts v1.13). Rejeu : 1,00.
2. **Invite d'idéation sans forme d'action** (`u38-ctf-s6`) : « l'action ne
   sera pas jouée » a induit `"action": ""`, refusé trois fois par le contrat
   strict — mort au tour 1 sur un plan parfait dès la première tentative.
   Corrigé : le pas d'idéation tolère l'action vide et l'invite dit la forme
   (spec H18.2 révisée, prompts v1.14) ; plus la normalisation d'un `id`
   numérique (dérive de format sous redemandes). Rejeu : drapeau capturé en
   3 actions.

## Décision (persistée ici, au journal et dans le backlog)

**Les mécanismes U34, U35 et U37 restent actifs par défaut à la reprise
de U31.** Motifs : iso ou mieux sur trois bancs sur quatre (τ identique, CTF
iso seed à seed, entrepôt dans la bande) ; l'écart du dépôt tient à un seed
unique dont le mode d'échec est documenté et dont les morts imputables au
harnais sont corrigées et prouvées en rejeu réel ; les interrupteurs (§H18.4,
§H17.4, §H10.4) gardent la comparaison rejouable à tout moment. Limites
nommées : effectifs faibles, et l'ancrage de plan du dépôt s1 est LE point à
surveiller en U31 — si le motif se répète, la réponse générique est du côté
de la discipline de curation (réduire, pas seulement ajouter), jamais d'une
règle d'environnement.

Infrastructure, hors décision : trois morts de transport (`IncompleteRead`
mi-flux du pont sur générations longues — s2 ×2, s8 ×1) rejoignent la mesure
du registre 2026-09-12 ; l'accumulation plaide pour une reprise de flux au
niveau transport (§H4), unité à part entière si la boucle U31 la confirme.
