# Backlog

Statuts : `[ ]` non commencé · `[~]` en cours ou insuffisamment vérifié · `[x]` terminé et intégralement vérifié.

Une unité ne passe à `[x]` qu'après validation de sa Definition of Done (CLAUDE.md §17). Les DoD ci-dessous listent les preuves **spécifiques** de l'unité ; les exigences transversales (traçabilité `@spec`/`@verifies`, documentation synchronisée, commit poussé) s'appliquent toujours.

Ordre d'exécution : les phases se suivent ; à l'intérieur d'une phase, les unités sont ordonnées par dépendance. Blocages externes actuels, rappelés sur les unités concernées :

- **B1 — Endpoint injoignable** : l'endpoint Ollama fourni est sain mais servi sur un port non-443, alors que la sortie réseau de l'environnement n'autorise que le port 443 (diagnostic et options : `docs/JOURNAL.md`, entrée du 2026-08-27 suite). *Nécessite une action humaine.*
- **B2 — Modèle non confirmé** : le nom du modèle à utiliser sur l'endpoint n'est pas encore communiqué. *Nécessite une action humaine.*
- **B3 — Périmètre benchmarks à arbitrer** : ARC-AGI-3 est le benchmark central des sources ; InterCode CTF et Sierra τ-Bench (papier SKILL.state) sont candidats comme benchmarks interactifs complémentaires ; l'accès à l'API ARC Prize (scorecard officiel) reste à confirmer. *Nécessite un arbitrage du responsable.*

---

## Phase 0 — Connaissance (close)

### U1 — Import des sources de référence dans `knowledge/` `[x]`

Exporter en markdown + images locales les sources de référence, avec provenance, PDF d'origine et index : billet NVIDIA AVO/ARC-AGI-3, papier AVO arXiv:2603.24517, page projet VISTA, papier Tycho arXiv:2607.28287 (réalisés le 2026-08-27), puis papier SKILL.state arXiv:2608.26263 fourni par le responsable (réalisé le 2026-08-30).

- DoD : exports fidèles présents ; images extraites et liées en relatif ; tous les liens d'images résolvent (vérifié par script) ; figures recadrées inspectées visuellement ; index `knowledge/README.md` à jour ; commits poussés. — **Satisfaite.**

---

## Phase 1 — Spécification (aucun code du harnais avant la clôture de U2.1–U2.4)

### U2.1 — Spécification du cœur du harnais AVO `[ ]`

Rédiger `docs/SPEC_HARNESS.md` : formalisation `Vary(Pₜ) = Agent(Pₜ, K, f)` ; boucle Planning → Implementation → Evaluation → Bug-Fixing ; contrats des composants (agent, outils, mémoire, lignée, score) ; **gestion de contexte à état d'exécution structuré** adaptée de SKILL.state — prompt par pas `(P, Σₜ, Oₜ)`, patch `ΔΣₜ` avec fusion `⊕` et suppression par null, validation déterministe côté runtime, rollback-retry, raisonnement jeté après projection — dimensionnée pour `OLLAMA_CONTEXT_LENGTH` ; articulation avec la mémoire durable type notes (GUIDE/WORKING à la VISTA) et avec la lignée git (commit conditionnel : correct ET ≥ meilleur score committé) ; format des trajectoires (JSONL rejouable).

- Dépend de : U1.
- DoD : document relu contre le papier AVO (§3), SKILL.state (§3, §5.7, limites §7) et le billet NVIDIA ; chaque exigence numérotée et testable ; écarts assumés vis-à-vis des papiers documentés avec justification ; commit documentaire poussé.

### U2.2 — Spécification du client d'inférence et de la configuration `[ ]`

Chapitre dédié de la spécification : surface OpenAI-compatible d'Ollama (`/v1/chat/completions`, `/v1/models`) et endpoints natifs utiles (`/api/show`, `/api/version`) ; authentification `Bearer` ; contrat des variables (`OLLAMA_HOST`, `OLLAMA_API_KEY`, `OLLAMA_CONTEXT_LENGTH`, nom du modèle, budgets) ; timeouts, retries à backoff, gestion des erreurs et des coupures ; comptage tokens/latence/coût par appel et par run ; stratégie de sorties structurées (mode JSON/grammaire si le serveur l'expose, sinon validation + rollback-retry côté runtime, imposée par la taxonomie d'erreurs open-weight de SKILL.state : 68 % écrasements d'état, 20 % schéma, 12 % JSON malformé) ; journalisation sans secret.

- Dépend de : U1. Indépendante de B1 (spécifier n'exige pas l'accès).
- DoD : contrat de configuration complet (rôle, format, obligatoire/facultatif, exemple non sensible) ; matrice des erreurs serveur → comportements ; commit poussé.

### U2.3 — Spécification du superviseur `[ ]`

Signaux de stagnation observables sur la trajectoire (aucun nouveau meilleur score sur N pas, répétition d'actions ou de patchs, plateau de score, échec en boucle de la même hypothèse) ; seuils configurables ; protocole d'intervention (revue de la trajectoire, production de directives, injection dans le contexte de l'agent principal) ; journal des interventions ; critères d'arrêt d'un run.

- Dépend de : U2.1.
- DoD : signaux définis mesurablement ; scénarios d'intervention décrits avec entrées/sorties attendues ; commit poussé.

### U2.4 — Spécification de l'interface ARC-AGI-3 `[ ]`

Interface de tâche direct-interaction en texte seul : observations = grilles 64×64 exactes (aucune image), actions disponibles sans description des règles ni du but, contrôle RESET et comptage des actions scorées conformes au protocole officiel ; historique typé des frames à la Tycho (décision / transitoires d'animation / terminaux de complétion / terminaux fatals / initialisations) ; mémoire de partie (notes durables + état structuré Σ) ; politique de continuation en contexte frais ; intégration : API ARC Prize (scorecard officiel, si accès — B3) et/ou moteur local, avec rejeu déterministe des trajectoires enregistrées ; définition RHAE reprise à l'identique de la méthodologie officielle (eₗ = min(115, 100·(hₗ/aₗ)²) si niveau complété, wₗ = ℓ, plafonnement par la complétion pondérée).

- Dépend de : U2.1. Arbitrage B3 souhaitable mais non bloquant pour spécifier ARC-AGI-3.
- DoD : protocole d'interaction spécifié champ par champ ; formule de score transcrite et illustrée sur un exemple numérique tiré des données VISTA ; commit poussé.

### U2.5 — Spécification du protocole d'évaluation et des benchmarks complémentaires `[ ]`

Périmètre de la campagne (« common benchmarks ») : ARC-AGI-3 en central ; proposition InterCode CTF et Sierra τ-Bench (benchmarks interactifs publics du papier SKILL.state) et/ou reproduction SkillExecBench — **à arbitrer (B3)** ; pour chaque benchmark retenu : source des tâches, harnais de tâche, métriques (score officiel, actions, tokens, coût, temps), budgets par run, nombre de runs, format des rapports et des artefacts (trajectoires, scorecards).

- Dépend de : U2.1 ; **bloquée en clôture par B3** (peut être rédigée en proposition et soumise à arbitrage).
- DoD : protocole écrit, budgets chiffrés, arbitrage du responsable consigné ; commit poussé.

### U2.6 — DAT complet, plan de tests et raffinement du backlog `[ ]`

Compléter `docs/DAT.md` (composants, flux, formats de données, arborescence cible, choix techniques et compromis, stratégie de reprise) ; plan de tests global (unitaires, intégration avec serveur LLM simulé, E2E sur environnement jouet déterministe) ; données de développement (générateurs seedés, fixtures de trajectoires) ; mise à jour du présent backlog si la spécification déplace des frontières.

- Dépend de : U2.1–U2.5.
- DoD : DAT sans « à définir » sur le périmètre spécifié ; chaque unité de la phase 2+ pointe vers ses chapitres de spec ; commit poussé.

---

## Phase 2 — Socle technique du harnais

### U3.1 — Squelette du projet Python `[ ]`

Initialiser le projet : `pyproject.toml`, arborescence `src/` + `tests/`, lint/format/typecheck (outillage à fixer en U2.6), pytest, commandes documentées dans le README (installation, tests, lancement), conteneurisation de développement (image + compose, l'environnement sachant démarrer dockerd) si retenue en U2.6.

- Dépend de : U2.6.
- DoD : `install`, `lint`, `typecheck`, `test` passent en local et sont documentés ; structure conforme au DAT ; commit poussé.

### U3.2 — Client d'inférence OpenAI-compatible `[ ]`

Implémenter le client conforme à U2.2 : chat completions, inventaire modèles, métadonnées `/api/show` ; Bearer ; timeouts/retries/backoff ; comptage tokens-latence-coût ; journalisation sans secret ; **serveur simulé local** (réponses scriptées, fautes injectables : coupures, JSON invalide, latence) pour les tests.

- Dépend de : U3.1. Validation contre l'endpoint réel **bloquée par B1/B2** (les tests sur simulé ne le sont pas).
- DoD : tests unitaires (nominal, limites, erreurs) et test d'intégration contre le serveur simulé verts ; smoke test réel exécuté et consigné dès B1/B2 levés.

### U3.3 — Runtime d'état d'exécution structuré `[ ]`

Implémenter Σ : schéma par domaine, patch ΔΣ (fusion `⊕`, suppression par null), validation déterministe (clés, types, structures), rollback-retry sur patch invalide, persistance/reprise sur disque, garde de budget contexte.

- Dépend de : U3.1.
- DoD : tests unitaires couvrant les trois modes d'erreur de la taxonomie SKILL.state (écrasement/omission de clés, incohérences de schéma, JSON malformé) plus nominal et reprise ; verts.

### U3.4 — Boucle agent principale `[ ]`

Boucle `(P, Σₜ, Oₜ) → (Rₜ, ΔΣₜ, aₜ)` : construction de prompt, parsing robuste, registre d'outils/actions, exécution d'action, trajectoire JSONL rejouable, articulation avec les notes durables.

- Dépend de : U3.2, U3.3.
- DoD : tests avec LLM simulé scripté (scénarios multi-pas déterministes, y compris patchs invalides et retries) verts ; une trajectoire enregistrée se rejoue à l'identique.

### U3.5 — Lignée évolutionnaire, base de connaissances et scoring `[ ]`

Population Pₜ (paires solution/score), commit git conditionnel (correctitude ET score ≥ meilleur committé), exposition de la lignée à l'agent ; montage lecture de K ; fonction f branchable (vecteur par configuration de test, 0 si échec de correction).

- Dépend de : U3.4.
- DoD : tests unitaires et d'intégration (lignée sur dépôt git temporaire, refus de commit sur régression) verts.

### U3.6 — Intégration bout-en-bout sur environnement jouet `[ ]`

Environnement jouet déterministe seedé (type mini-Warehouse, conforme au plan de tests U2.6) piloté par le harnais complet : d'abord avec LLM simulé (E2E reproductible en CI locale), puis avec l'endpoint réel en smoke test.

- Dépend de : U3.4, U3.5. Smoke test réel **bloqué par B1/B2**.
- DoD : E2E simulé vert et documenté (commande unique) ; run réel court exécuté, trajectoire et coûts consignés dans le journal dès B1/B2 levés.

---

## Phase 3 — Superviseur

### U4.1 — Détection de stagnation et de cycles `[ ]`

Métriques de trajectoire et seuils configurables conformes à U2.3 ; évaluation continue pendant un run.

- Dépend de : U3.4.
- DoD : tests unitaires sur trajectoires synthétiques (stagnation vraie détectée, progression normale non signalée) verts.

### U4.2 — Intervention conditionnelle `[ ]`

Rôle superviseur : revue de la trajectoire, directives produites et injectées dans le contexte de l'agent principal, journal des interventions, plafonds d'intervention.

- Dépend de : U4.1.
- DoD : scénarios E2E avec LLM simulé (déclenchement, contenu injecté, reprise de la progression) verts ; comportement observé consigné.

---

## Phase 4 — Interfaces de benchmark

### U5.1 — Client d'environnement ARC-AGI-3 `[ ]`

Client du service ARC-AGI-3 (API ARC Prize et/ou moteur local selon B3) : sessions, frames, actions, niveaux ; enregistrement typé des frames (décision/transitoire/terminal/initialisation) ; archivage des trajectoires.

- Dépend de : U3.1, U2.4 ; accès service **à confirmer (B3)**.
- DoD : tests d'intégration contre un service simulé conforme au protocole ; connexion réelle vérifiée dès l'accès confirmé.

### U5.2 — Interface de tâche ARC-AGI-3 pour le harnais `[ ]`

Adaptateur direct-interaction texte : grille 64×64 exacte comme observation, actions sans description, RESET, mémoire de partie (notes + Σ), continuation en contexte frais sous le budget `OLLAMA_CONTEXT_LENGTH`.

- Dépend de : U5.1, U3.6.
- DoD : partie complète jouée de bout en bout sur environnement simulé avec LLM simulé ; trajectoire rejouable ; tests verts.

### U5.3 — Scoreur RHAE et vérifications `[ ]`

Calcul RHAE local conforme à la définition officielle, comptage strict des actions scorées, rejeu déterministe.

- Dépend de : U5.1.
- DoD : tests unitaires validés contre des valeurs par niveau publiées (fixtures tirées des tableaux VISTA de `knowledge/`) ; verts.

### U5.4 — Benchmarks complémentaires retenus `[ ]`

Selon l'arbitrage B3 (InterCode CTF, Sierra τ-Bench, SkillExecBench-like…) : à découper en sous-unités par benchmark une fois U2.5 close.

- Dépend de : U2.5 (arbitrage), U3.6.
- DoD : à définir par benchmark retenu lors du découpage.

---

## Phase 5 — Campagne d'évaluation

### U6.1 — Recette de l'endpoint réel et choix du modèle `[ ]`

Dès B1 levé : test fonctionnel complet (version serveur, `/v1/models`, `/api/show` — vérifier la fenêtre de contexte annoncée face à `OLLAMA_CONTEXT_LENGTH` —, complétion réelle chronométrée) ; inventaire des modèles disponibles ; choix du modèle avec le responsable (B2) ; consignation dans le journal et la configuration.

- Bloquée par : **B1, B2**.
- DoD : rapport de recette consigné ; modèle fixé et documenté.

### U6.2 — Runs pilotes et calibrage `[ ]`

Sous-ensemble de tâches par benchmark retenu ; calibrage des budgets (actions, tokens, coût, temps), des seuils superviseur et des prompts ; itérations du harnais consignées.

- Dépend de : U6.1, U5.2–U5.4.
- DoD : runs pilotes reproductibles, budgets arrêtés, ajustements documentés.

### U6.3 — Campagne complète et rapport `[ ]`

Exécution de la campagne sur le périmètre arbitré ; collecte scores/actions/tokens/coûts ; rapport comparatif face aux références de `knowledge/` (ARC-AGI-3 : AVO 100.00 RHAE / 6 624 actions, VISTA 100.00 / 7 542, Tycho 100.00 / 6 641 ; benchmarks SKILL.state le cas échéant) ; mise à jour CHANGELOG et documentation.

- Dépend de : U6.2.
- DoD : résultats reproductibles archivés (trajectoires, scorecards) ; rapport committé ; backlog et documents à l'état réel.
