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

### 2026-08-30 — Cinquième source (SKILL.state) et backlog détaillé

- Ajout dans `knowledge/` de l'export complet du papier SKILL.state (arXiv:2608.26263, fourni par le responsable) : texte intégral, figure d'architecture, dix tableaux, prompts des quatre runtimes, PDF d'origine ; index et synthèse mis à jour (gestion de contexte à état structuré borné, validation JSON stricte, benchmarks candidats InterCode CTF et τ-Bench).
- Réécriture de `docs/BACKLOG.md` en backlog détaillé : phases 0–5, unités U2.1 à U6.3 avec dépendances, Definition of Done spécifiques et blocages externes nommés (B1 joignabilité endpoint, B2 nom du modèle, B3 périmètre benchmarks).
- `docs/JOURNAL.md` : entrée d'étude du 2026-08-30 ; `README.md` et `CLAUDE_PROJECT.md` mis au compte de cinq sources.

## [Publié]

_Aucune publication pour le moment._
