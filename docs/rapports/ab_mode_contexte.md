# A/B des deux modes de contexte, sur rejeu (U27)

Comparaison du mode `transcript` (§H5, historique complet renvoyé à chaque segment) et du mode `state` (§H15, état structuré Σ recomposé en `O(1)` par tour) sur le jeu synthétique local `cible-synthetique`, mêmes plafonds, mode rejeu — aucun secret requis, rien n'est publié.

| Mesure | `transcript` | `state` |
|---|---|---|
| RHAE moyen | 100.00 | 100.00 |
| Actions | 76 | 76 |
| Appels au modèle | 228 | 76 |
| Tokens cumulés | 6384 | 2128 |
| Taille moyenne de prompt (tokens) | 24.00 | 24.00 |
| Retries de patch | 0 | 0 |

Lecture : un nombre d'appels ou un budget de tokens moindre en `state` reflète le contrat `O(1)` par tour (§H15.1) plutôt que l'historique cumulé de `transcript` ; un RHAE et un nombre d'actions comparables signifient que le changement de mode ne dégrade pas la partie jouée. Des retries de patch non nuls sont attendus du seul mode `state` (§H15.4) — `transcript` ne décode aucun patch.

Limite : mesure sur rejeu local uniquement (jeu synthétique, réponses scriptées) — le départage en conditions réelles (endpoint et cache de préfixe réels, coût observé) reste le périmètre de U28 (`[LIVE]`, en session interactive, avec le responsable). En particulier, le rejoueur HTTP répond verbatim les `prompt_eval_count`/`eval_count` enregistrés une seule fois (§H4.7) : la « taille moyenne de prompt » ci-dessus est donc identique pour les deux modes par construction du rejeu, et ne dit rien de la croissance réelle du prompt en `transcript` face au `O(1)` de `state` (§H15.1) — c'est le nombre d'appels au modèle qui porte ce signal ici, pas la taille par appel.