# A/B du patron ledger, sur rejeu (U37)

Comparaison du harnais NU (mécanismes H18 inactifs, le comportement d'avant U37) et du harnais ENRICHI (`AVO_PLAN_LEDGER` et `AVO_IDEATION_OUVERTURE` actifs, §H18.4) sur le jeu synthétique local `cible-synthetique`, mêmes plafonds, même mode `state`, mêmes réponses scriptées sur le même chemin parfait (cassettes générées, §A8.5). Le rejeu prouve le COMPORTEMENT du harnais — le pas d'idéation est joué, gratuit au score, le ledger voyage dans Σ — jamais la qualité des choix du modèle : celle-ci se mesure en conditions réelles (U38).

| Mesure | harnais nu | harnais enrichi |
|---|---|---|
| actions jouées | 76 | 76 |
| niveaux complétés | 3 | 3 |
| RHAE | 100.000 | 100.000 |
| tours (appels de pas) | 76 | 77 |
| pas d'idéation (§H18.2) | 0 | 1 |
| curations (§H18.3) | 0 | 0 |
| tokens de prompt | 1824 | 1848 |
| tokens générés | 304 | 308 |

Lecture : à chemin parfait identique, le harnais enrichi joue le même nombre d'actions et complète les mêmes niveaux — l'idéation coûte un tour d'appel sans coûter d'action au score, et le protocole du ledger grossit chaque prompt (le préremplissage domine le coût, §H1.3.1). Le gain attendu du patron — moins d'ancrage, un plan curé — ne peut pas apparaître sur des réponses scriptées : c'est l'objet de l'A/B réel (U38), qui départage à budget constant.
