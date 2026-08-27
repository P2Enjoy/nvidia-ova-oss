# CHANGELOG

## [Non publié]

### 2026-08-27 — Import des sources de connaissance et initialisation de la documentation projet

- Ajout de `knowledge/` : export markdown fidèle, avec images locales, des quatre sources de référence du projet :
  - billet NVIDIA « AVO Reaches 100% on ARC-AGI-3 » (2026-08-21) ;
  - papier AVO, arXiv:2603.24517 (spécification du harnais à implémenter), avec les 7 figures extraites et le PDF d'origine ;
  - page projet VISTA (vista-research.github.io), avec 30 images miroirs et les tableaux de résultats par jeu ;
  - papier Tycho, arXiv:2607.28287, avec les 18 figures extraites et le PDF d'origine.
- Ajout de `knowledge/README.md` : index des sources, provenance, synthèse de ce qu'elles établissent pour le dépôt.
- Réécriture du `README.md` : le dépôt porte désormais le projet « harnais AVO open source » et non plus la description de la base factory.
- Initialisation de `CHANGELOG.md`, `docs/JOURNAL.md`, `docs/BACKLOG.md`, `docs/DAT.md` (embryonnaire) et `CLAUDE_PROJECT.md`.

### 2026-08-27 — Test de l'endpoint d'inférence et contrat de configuration

- Diagnostic complet de joignabilité de l'endpoint Ollama fourni par le responsable : serveur sain et servi en TLS pour le public (vérifié depuis des points de mesure externes), mais injoignable depuis l'environnement d'exécution dont la sortie réseau est limitée au port 443 ; options de déblocage consignées (`docs/JOURNAL.md`).
- Documentation du contrat de configuration (`OLLAMA_HOST`, `OLLAMA_API_KEY`, `OLLAMA_CONTEXT_LENGTH`) dans `README.md` et `CLAUDE_PROJECT.md`, sans valeur sensible ; mise à jour du blocage de l'unité U3 dans `docs/BACKLOG.md`.

### 2026-08-27 — Endpoint d'inférence validé de bout en bout

- Test complet de l'endpoint fourni depuis l'environnement de travail : joignabilité TLS, authentification vérifiée par la négative (`401` sans clé et avec clé invalide), version du serveur, listing des modèles sur les deux surfaces, complétion, **tool calling**, chargement effectif de la fenêtre de contexte demandée (confirmé par `/api/ps`) et exploitation réelle d'un contexte long (aiguille retrouvée dans un prompt de plus de 200 000 tokens).
- Trois contraintes de conception mesurées et consignées (`docs/JOURNAL.md`) : coût dominé par le préremplissage (d'où un historique append-only pour le cache de préfixe), plafond de contexte par clé assorti d'une marge de 15 % côté proxy (gestion du `HTTP 413` en cas nominal), modèle à raisonnement dont le raisonnement consomme le budget de sortie.
- Retrait des mentions de blocage devenues fausses : l'injoignabilité de l'endpoint relevée précédemment était propre à l'environnement d'exécution d'alors, pas au serveur. `README.md` (état actuel, variables d'environnement, limites connues), `docs/BACKLOG.md` (U3 n'est plus bloquée que par U2) et `CLAUDE_PROJECT.md` (contrat d'endpoint) mis à jour ; l'entrée de journal correspondante est marquée résolue sur place.
- Documentation du modèle de travail `qwen3.6:35b` et du rôle réel de `OLLAMA_CONTEXT_LENGTH`.

### 2026-08-27 — Accès ARC Prize fourni et vérifié

- Ajout de la variable `ARC_API_KEY` au contrat de configuration (`README.md`, `CLAUDE_PROJECT.md`), sans valeur ; clé vérifiée en lecture seule (`401` sans clé, `200` avec) sans ouvrir de scorecard ni jouer de partie.
- L'API officielle expose 25 jeux et 183 niveaux avec les références humaines par niveau, qui font désormais foi pour le calcul du RHAE à la place des tables recopiées dans `knowledge/` ; recoupement exact vérifié sur un jeu.
- Règle consignée dans le backlog et les règles locales : évaluer via l'API officielle publie un scorecard sur le compte du responsable, donc les exécutions d'essai passent par un environnement local de rejeu et la première campagne officielle requiert son accord.
- Retrait de la réserve sur l'absence d'accès ARC Prize, devenue fausse.

### 2026-08-27 — Périmètre des benchmarks arrêté

- Décision prise par défaut au titre de `CLAUDE.md` §1, « Autonomie de décision » : le benchmark de référence est **ARC-AGI-3, ensemble public**, seul benchmark du périmètre initial. Motif, options écartées et réserve sur le scorecard officiel consignés dans `docs/JOURNAL.md` ; mentions d'attente retirées de `README.md` et `docs/BACKLOG.md`.

### 2026-08-27 — U4 : `llm-replay`, contrat de l'endpoint enregistré et rejoué

- Format de cassette JSONL : échanges HTTP réels, appariés sur méthode, chemin, nature d'authentification et empreinte du corps canonisé. Ni clé ni hôte n'atteignent le disque — seule la nature de l'authentification est notée, les en-têtes de réponse passent par une liste blanche, et l'expurgation est vérifiée par un test qui cherche un secret dans le fichier écrit.
- Serveur de rejeu : sert exclusivement des échanges enregistrés et rend une erreur nommant l'écart quand une requête ne correspond à aucune entrée, au lieu de fabriquer une réponse. Injection des seules fautes que le serveur réel ne produit pas à la demande (500, latence, coupure).
- **Contrat réel enregistré** : 7 échanges couvrant le refus sans clé, la version, le listing des modèles, une conversation, une conversation avec appel d'outil, le refus sur clé invalide et le dépassement de contexte avec son corps de quota. La requête de dépassement, de près de 2 Mo, n'est pas stockée : son empreinte suffit à l'appariement.
- Cibles `make record-llm`, `make test-int-live` (détection de dérive contre le serveur réel) et `make seed` (contrôle de présence des fixtures, sans jamais fabriquer de contrat). Le fichier `.env` est passé au conteneur par Docker : aucun analyseur maison, aucun secret dans le code.
- Preuves : 31 tests verts (19 unitaires, 12 d'intégration HTTP réels dont le rejeu intégral de la cassette enregistrée), lint, format et mypy strict sur 24 fichiers ; `make test-int-live` vert, aucune dérive.

### 2026-08-27 — On ne simule plus l'endpoint : on l'enregistre et on le rejoue

- Décision remplacée sur objection du responsable : un serveur dédié étant fourni, l'endpoint d'inférence n'est pas une dépendance impossible à exécuter localement et **ne se simule pas** (`CLAUDE.md` §15). Le faux serveur Ollama prévu par la spécification est abandonné — réimplémenter un contrat mesurable revient à l'inventer et garantit sa dérive.
- `docs/SPEC_HARNAIS.md` §H4.7 réécrit en **enregistreur/rejoueur** : `make record-llm` capture les échanges HTTP du vrai endpoint dans des cassettes expurgées de la clé et de l'hôte ; les tests les rejouent hors ligne ; une requête sans correspondance rend une erreur explicite au lieu d'une réponse inventée ; `make test-int-live` détecte toute dérive du contrat réel. Seules les fautes que le serveur ne produit pas à la demande (500, latence, coupure) sont injectées — les 401 et 413 réels sont enregistrés.
- Composant renommé `llm-replay` par symétrie avec `arc-replay`, qui reste un service local pour une raison différente et documentée : chaque appel réel à l'API ARC publie un scorecard.
- U4 réécrite en conséquence, U7 ajustée, `make record-llm` et `make test-int-live` ajoutées au contrat ; README, DAT, plan directeur et Makefile mis en cohérence.

### 2026-08-27 — U3 : squelette du harnais et chaîne d'outillage conteneurisée

- Paquet `avo` (`src/avo`) sans aucune dépendance d'exécution, arborescence des sous-paquets prévus par la spécification, point d'entrée `python -m avo` avec `--version` et une aide qui déclare les sous-commandes du contrat ; une sous-commande spécifiée mais non livrée refuse explicitement en nommant l'unité de backlog qui la livrera.
- **Toute la chaîne d'outillage s'exécute dans Docker** (`Dockerfile`, `Makefile`) : pytest, ruff et mypy vivent dans l'image, jamais sur la machine hôte. Chaque cible lance un conteneur jetable sur le dépôt monté en volume ; une garde nomme le correctif quand le démon Docker est injoignable.
- Mode dégradé `AVO_NO_DOCKER=1` pour les environnements sans Docker : exécute les tests avec la seule bibliothèque standard, en annonçant que le lint est réduit et le typecheck non exécuté.
- Tests écrits avec `unittest` (bibliothèque standard) : exécutables sous pytest dans le conteneur comme sans rien installer. Sept tests unitaires couvrent la version, l'invocation réelle du module et le refus des commandes non livrées.
- Campagne complète exécutée dans le conteneur : ruff (check et format), mypy en mode strict, pytest — 7 tests verts, aucune anomalie. Le Makefile détecte le mode rootless (où `--user` doit être omis) et dirige les caches des outils hors du dépôt.
- Spécification mise en accord (`docs/SPEC_HARNAIS.md` §H2.1, §H2.3, §H2.4), plan directeur, backlog (U3 close, périmètre de U5 ajusté), README (prérequis, commandes, structure, limites).

### 2026-08-27 — Spécification complète du harnais et plan d'exécution (U2 close)

- Ajout de `docs/SPEC_HARNAIS.md` (noyau agent, chapitres H1–H14 : stack stdlib, configuration, client d'inférence natif Ollama, transcript append-only et continuation en contexte frais, notes persistantes, outils, boucle P→I→E→B, lignée git jetable avec politique « correct ∧ ≥ meilleur », superviseur, observabilité, politique de raisonnement, plan de tests) — rédigé après relecture intégrale des quatre exports de `knowledge/` et sur les contraintes mesurées de l'endpoint.
- Ajout de `docs/SPEC_ARCAGI3.md` (chapitres A1–A8 : formalisation et protocole officiel d'après l'export Tycho, client API, environnement local de rejeu avec jeu synthétique `cible` spécifié en forme fermée, rendu texte 64×64 et mémoire de frames sans perte, interface direct-interaction calquée sur VISTA, RHAE selon la définition Tycho §3.1, campagne sous garde d'accord, plan de tests). Les tests n'atteignent jamais l'API officielle (garde anti-publication).
- Ajout de `docs/MASTER_PLAN.md` : ordre d'exécution (lots A–F), règle des unités [LIVE] interdites au worker, définition de la campagne de preuves (`make check`, hors ligne), adaptation de la vérification utilisateur à un produit CLI, condition de fin de la boucle planifiée.
- `docs/BACKLOG.md` redécoupé : U1–U2 closes, 23 unités d'implémentation U3–U25 tenant chacune dans une session, chacune avec références `@spec`, périmètre et preuves propres.
- `docs/DAT.md` complété (composants, flux, données, interfaces externes, choix actés, compromis) ; `README.md` (stack réelle, prérequis, contrat de commandes, structure, limites) et `CLAUDE_PROJECT.md` (règle de code spécifié, unités [LIVE], vérification CLI) mis en cohérence.

## [Publié]

_Aucune publication pour le moment._
