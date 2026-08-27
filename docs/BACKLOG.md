# Backlog

Statuts : `[ ]` non commencé · `[~]` en cours ou insuffisamment vérifié · `[x]` terminé et intégralement vérifié.

Une unité ne passe à `[x]` qu'après validation de sa Definition of Done (CLAUDE.md §17).

---

## U1 — Import des sources de connaissance dans `knowledge/` `[x]`

Exporter en markdown + images locales les quatre sources de référence (billet NVIDIA AVO/ARC-AGI-3, papier AVO arXiv:2603.24517, page projet VISTA, papier Tycho arXiv:2607.28287), avec provenance, PDF d'origine et index.

- DoD : 4 exports fidèles présents ; images extraites et liées en relatif ; tous les liens d'images résolvent (vérifié par script) ; figures recadrées inspectées visuellement ; index `knowledge/README.md` écrit ; commit poussé.
- Réalisé le 2026-08-27. Vérifications listées dans `docs/JOURNAL.md` (entrée du 2026-08-27). Unité documentaire : pas de tests automatisés associés.

## U2 — Spécification complète du harnais AVO `[ ]`

Rédiger et committer, avant toute ligne de code, la spécification du harnais dans `docs/` (et compléter `docs/DAT.md`) à partir de `knowledge/` : architecture (agent principal, boucle Planning→Implementation→Evaluation→Bug-Fixing, mémoire persistante, lignée git, superviseur), contrat de configuration (variables d'environnement pour l'endpoint compatible OpenAI, le modèle, les budgets), interface de tâche (dont l'interface ARC-AGI-3 direct-interaction en grilles texte 64×64), protocole d'évaluation et métriques (RHAE selon la définition officielle reprise dans l'export Tycho), plan de tests (unitaires, intégration, E2E) et découpage des unités d'implémentation.

- DoD : spécification relue contre les trois sources techniques ; contrat d'API et de configuration défini sans secret ; `docs/DAT.md` mis à jour ; backlog détaillé des unités d'implémentation ; commit documentaire poussé.

## U3 — Cœur du harnais : boucle agent + client endpoint compatible OpenAI `[ ]`

Implémenter l'agent principal conformément à U2 : client d'inférence (API compatible OpenAI, retry/timeout/journalisation), boucle d'agent avec outils, mémoire persistante, lignée de solutions versionnée, fonction de score `f` branchable.

- Bloqué par : U2 ; par la joignabilité de l'endpoint (fourni le 2026-08-27 mais servi sur un port non-443 alors que l'environnement ne sort qu'en 443 — diagnostic complet dans `docs/JOURNAL.md`, options de déblocage listées, **nécessite une action humaine**) ; et par le nom du modèle à utiliser (**nécessite une action humaine**).
- DoD : tests unitaires et d'intégration propres verts (endpoint simulé localement pour les tests) ; démonstration reproductible documentée.

## U4 — Superviseur (anti-stagnation) `[ ]`

Implémenter l'agent superviseur : détection de stagnation et de cycles improductifs, revue de trajectoire, intervention conditionnelle qui redirige l'agent principal.

- Bloqué par : U3.
- DoD : tests spécifiques verts, comportement démontré sur un scénario reproductible.

## U5 — Interface(s) de benchmark `[ ]`

Implémenter l'interface de tâche d'évaluation, en commençant par ARC-AGI-3 en mode direct-interaction texte (grilles 64×64 exactes, actions sans description des règles), et le calcul RHAE local ; intégrer l'API officielle ARC Prize si un accès est disponible.

- Bloqué par : U3 ; périmètre exact des benchmarks à confirmer par le responsable (**nécessite une action humaine**).
- DoD : rejeu déterministe testé ; comptage d'actions et scores vérifiés contre la définition officielle.

## U6 — Campagne d'évaluation et rapport `[ ]`

Exécuter le harnais sur les benchmarks retenus avec le modèle fourni, collecter les scores, actions et coûts, produire le rapport comparatif face aux références de `knowledge/` (AVO 100.00/6 624 ; VISTA 100.00/7 542 ; Tycho 100.00/6 641).

- Bloqué par : U3–U5, endpoint et modèle fournis.
- DoD : résultats reproductibles, rapport committé, CHANGELOG mis à jour.
