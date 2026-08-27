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

- Bloqué par : U2 uniquement. L'endpoint et le modèle ne sont plus des blocages : endpoint testé et validé de bout en bout le 2026-08-27 (authentification, tool calling, contexte long), modèle de travail `qwen3.6:35b` (`docs/JOURNAL.md`, entrée du 2026-08-27 (suite 2)).
- Contraintes d'implémentation issues des mesures : historique append-only (cache de préfixe), budget de contexte sous la marge de 15 % du proxy avec gestion du `HTTP 413`, politique de raisonnement explicite.
- DoD : tests unitaires et d'intégration propres verts (endpoint simulé localement pour les tests) ; démonstration reproductible documentée.

## U4 — Superviseur (anti-stagnation) `[ ]`

Implémenter l'agent superviseur : détection de stagnation et de cycles improductifs, revue de trajectoire, intervention conditionnelle qui redirige l'agent principal.

- Bloqué par : U3.
- DoD : tests spécifiques verts, comportement démontré sur un scénario reproductible.

## U5 — Interface(s) de benchmark `[ ]`

Implémenter l'interface de tâche d'évaluation, en commençant par ARC-AGI-3 en mode direct-interaction texte (grilles 64×64 exactes, actions sans description des règles), et le calcul RHAE ; brancher l'API officielle ARC Prize (accès disponible) et fournir un environnement local de rejeu déterministe pour les tests, afin qu'aucune exécution d'essai n'ouvre de scorecard.

- Bloqué par : U3. Périmètre arrêté : ARC-AGI-3, ensemble public, seul benchmark du périmètre initial (décision du 2026-08-27, `docs/JOURNAL.md`).
- Accès API ARC Prize fourni et vérifié le 2026-08-27 (`ARC_API_KEY`) : 25 jeux et 183 niveaux exposés, avec les `baseline_actions` humaines par niveau, qui font foi pour le calcul du RHAE.
- DoD : rejeu déterministe testé ; comptage d'actions et scores vérifiés contre la définition officielle.

## U6 — Campagne d'évaluation et rapport `[ ]`

Exécuter le harnais sur ARC-AGI-3 (ensemble public) avec le modèle fourni, collecter les scores, actions et coûts, produire le rapport comparatif face aux références de `knowledge/` (AVO 100.00/6 624 ; VISTA 100.00/7 542 ; Tycho 100.00/6 641).

- Bloqué par : U3–U5. Endpoint, modèle et accès ARC Prize disponibles et validés.
- Toute campagne passant par l'API officielle dépose ses résultats dans un scorecard rattaché au compte du responsable : le périmètre exact (jeux retenus, plafonds d'actions, budget de temps) est arrêté dans la spécification avant exécution, et l'accord du responsable est requis avant la première campagne officielle.
- DoD : résultats reproductibles, rapport committé, CHANGELOG mis à jour.
