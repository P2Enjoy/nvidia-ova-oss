# Registre d'incohérences

Défauts constatés, avec leur mesure. Une entrée résolue est RETIRÉE ; quand le
registre devient vide, le fichier lui-même est supprimé du dépôt (CLAUDE.md §5).

## Ouverts

### 2026-09-12 — Transport : `IncompleteRead` répété du pont 443 sur les longues générations, épisode CTF seed 1 non mesurable

- **Constat.** Sur le défi `encodage` du seed 1 (banc b), l'appel `/api/chat`
  est coupé en plein flux (`http.client.IncompleteRead`, 94 634 octets lus au
  premier run, 12 300 au rejeu), l'échelle de relances H4.5 (5 tentatives,
  attentes jusqu'à 90 s) s'épuise et l'épisode meurt.
- **Mesure.** Deux exécutions indépendantes le 2026-09-12 (05:27Z après ~22 min
  de jeu ; rejeu 09:12Z, 14 relances au total dans l'épisode), une seule
  exécution live en cours à chaque fois (le plafond de parallélisme n'est pas
  en cause). Les 25 autres épisodes du même socle et la campagne ARC ont
  traversé le même pont sans mourir : le mode d'échec est corrélé aux
  générations LONGUES de ce défi (le modèle raisonne longtemps), pas à la
  charge. Même signature que la coupure mi-flux décrite pour un gateway dans
  l'export GVS5H (§4.5, `IncompleteRead`).
- **Issue retenue.** Ligne de base du banc b consignée sur les 9 épisodes
  aboutis (7/9), seed 1 marqué NON MESURABLE sur cette infrastructure — pas un
  échec du modèle. Correction étrangère à l'unité en cours (U36, socle de
  mesure) : le comportement du client reste inchangé ; la reprise sur coupure
  de flux relève du chantier « résumé de coupure » (U34, spec H17) qui peut
  l'instruire, ou d'une reprise de flux au niveau transport (§H4) si les
  mesures s'accumulent.
- **Nuance mesurée (session planifiée du même jour, série b indépendante).**
  Sur la réplication, le seed 1 est mort une fois sur un incident d'endpoint
  (`ServerError` HTTP 500, 21 actions) et son rejeu unique a ABOUTI sans mort
  de transport (30 actions, budget épuisé, échec sémantique `encodage`) :
  le mode d'échec n'est pas systématique sur ce seed, et la réplication est
  mesurable en 10 épisodes (7/10, `HISTORIQUE.md`). L'accumulation de mesures
  pour une reprise de flux transport reste à l'identique.

### 2026-09-01 — `scripts/smoke_pile.sh` : le contrôle `RESET` ne suit plus le contrat du rejoueur ARC

- **Constat.** Le script de fumée envoie `POST /api/cmd/RESET` avec un corps `{}`
  et attend `NOT_FINISHED`. Le rejoueur (`mocks/arc_replay/serveur.py`, fidèle à
  l'API réelle) exige `game_id` dans chaque action et `card_id` au `RESET` : ce
  contrôle ne peut plus passer, quel que soit l'état de la pile.
- **Mesure.** Relevé le 2026-09-01 sur pile fraîche et saine (`docker compose ps`
  rend les deux services *healthy*, `/api/games` rend 200 avec le jeu cible) :
  `curl -X POST -d '{}' /api/cmd/RESET` → `{"error": "game (absent) not found"}` ;
  avec `game_id` seul → `{"error": "card_id (absent) inconnu ou fermé"}`. La fumée
  conclut `ECHEC` alors que la pile fonctionne (les 4 E2E passent sur cette même
  pile).
- **Issue retenue.** Aligner le contrôle sur le contrat réel : ouvrir un scorecard
  (`POST /api/scorecard/open`), puis `RESET` avec `game_id` et `card_id`. Correction
  étrangère à l'unité en cours (U29a2) : comportement laissé inchangé, à traiter
  dans un commit dédié par une session dont c'est le chemin.

## Traitées dans la session qui les a rencontrées

### 2026-09-02 — `.env.example` annonçait `transcript` comme défaut de `AVO_CONTEXT_MODE`

- **Constat.** Le bloc `AVO_CONTEXT_MODE` de `.env.example` décrivait `transcript`
  comme défaut, alors que le défaut réel est `state` depuis la décision du
  2026-09-01 (U28, `avo.config`, §H15.7) — README et spécification étaient à jour,
  ce fichier avait été oublié.
- **Mesure.** `grep AVO_CONTEXT_MODE .env.example` → « (transcript) » ;
  `charger().contexte_mode` → `state` ; README §variables → défaut `state`.
- **Traitement.** Défaut étranger à l'unité U32, consigné ici et corrigé dans un
  commit dédié : le bloc décrit `state` comme défaut avec sa date de décision.
  Aucun comportement n'est modifié.

### 2026-08-30 — MASTER_PLAN §4 annonçait `build` dans `make check`

- **Constat.** MASTER_PLAN §4 décrivait `make check` comme incluant `build` ;
  la cible réelle (Makefile, U3) ne l'inclut pas — exclusion délibérée pour que
  la campagne reste exécutable DANS un conteneur, où docker n'existe pas.
- **Mesure.** `grep '^check:' Makefile` → `check: lint typecheck test-unit
  test-int test-e2e` ; la documentation « sans make sur l'hôte » exécute bien
  `make check` en conteneur.
- **Issue retenue et appliquée.** Le document est aligné sur le réel : `make
  build` s'exécute en sus depuis l'hôte lors de la campagne de fin de session.
  MASTER_PLAN §4 corrigé dans cette session.

### 2026-08-28 — Le README annonçait `arc-replay` comme « à venir »

- **Constat.** Le `README.md` décrivait le service `arc-replay` du port 8765 avec la
  mention « à venir en U16 ». U16 est close depuis le 2026-08-28 et le service tourne.
- **Mesure.** Relevé le 2026-08-28 : `docker compose ps` rend `arc-replay` *healthy*
  depuis plus de deux heures, et `GET http://127.0.0.1:8765/api/games` rend `200` avec
  le jeu `cible-synthetique` et ses baselines.
- **Traitement.** Défaut étranger à l'unité U23, consigné ici. Corrigé dans un commit
  dédié : la mention d'attente est retirée et le service est décrit tel qu'il est.
  Aucun comportement n'est modifié.

### 2026-08-28 — `python -m avo --help` renvoyait la reprise à une unité déjà close

- **Constat.** La table `_A_VENIR` de `avo.cli` attribuait la sous-commande `resume`
  à l'unité U13. U13 est close depuis le 2026-08-28 et son périmètre (`@spec` H8,
  H12) ne couvre pas §H13.2 : c'est U23 qui livre la reprise, avec `run-arc`.
- **Mesure.** `python -m avo --help` affichait « resume [U13] reprise d'un run
  existant » alors que `docs/BACKLOG.md` porte U13 en `[x]`. Un lecteur cherchant
  l'unité responsable la trouvait close et la commande refusant toujours de
  s'exécuter.
- **Traitement.** Défaut étranger à l'unité U19, consigné ici. Corrigé dans un commit
  dédié : la table renvoie désormais à U23, seule unité dont le périmètre porte
  §H13.2. Le comportement de la commande est inchangé — elle refuse toujours en
  nommant son unité.

### 2026-08-28 — La configuration n'imposait pas le plancher de `AVO_NUM_PREDICT` quand `AVO_THINK=true`

- **Constat.** `docs/SPEC_HARNAIS.md` §H12.1 énonce : « `AVO_THINK=true` reste
  disponible ; dans ce cas `AVO_NUM_PREDICT ≥ 8192` est imposé par la config. »
  Le module `avo.config` livré par U6 n'appliquait pas cette contrainte : une
  configuration `AVO_THINK=true` avec `AVO_NUM_PREDICT=64` était acceptée.
- **Mesure.** Reproduit le 2026-08-28 : `charger(Mode.REJEU, env={"AVO_THINK": "true",
  "AVO_NUM_PREDICT": "64"})` rendait une `Config` valide au lieu d'une `ConfigInvalide`.
- **Conséquence.** Le raisonnement natif consomme le budget de sortie avant tout
  contenu : la réponse revient vide avec `finish_reason: length`, exactement le
  comportement mesuré le 2026-08-27 et que §H12 vise à empêcher.
- **Traitement.** Défaut étranger à l'unité U7, donc consigné ici plutôt que corrigé
  au passage (`docs/CloudWorker.md` §3.1). Il a toutefois été traité **en préalable de
  U7 dans la même session** (§4.2, second cas) : le client d'inférence consomme
  précisément ces deux réglages, et livrer un client qui les honore par-dessus une
  configuration qui ne les contraint pas aurait laissé le défaut se manifester à
  l'exécution. Règle implémentée dans `avo.config` avec son test.
