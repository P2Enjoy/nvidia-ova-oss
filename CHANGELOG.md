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

### 2026-08-27 — Périmètre des benchmarks arrêté

- Décision prise par défaut au titre de `CLAUDE.md` §1, « Autonomie de décision » : le benchmark de référence est **ARC-AGI-3, ensemble public**, seul benchmark du périmètre initial. Motif, options écartées et réserve sur le scorecard officiel consignés dans `docs/JOURNAL.md` ; mentions d'attente retirées de `README.md` et `docs/BACKLOG.md`.

## [Publié]

_Aucune publication pour le moment._
