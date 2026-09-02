# Registre d'incohérences

Défauts constatés, avec leur mesure. Une entrée résolue est RETIRÉE ; quand le
registre devient vide, le fichier lui-même est supprimé du dépôt (CLAUDE.md §5).

## Ouverts

### 2026-09-02 — L'échelle de relances H4.5 est plus courte que les rafales de 500 mesurées sur le pont

- **Constat.** `ATTENTES_RETRY = (1, 4, 16, 45, 90)` s couvre, appels compris
  (~40 s max chacun via le pont), environ six minutes d'indisponibilité. Les
  rafales de HTTP 500 du pont (« the edge function timed out », limite de 40 s
  avant premiers en-têtes alors que l'origine répond) durent au moins autant.
- **Mesure.** 2026-09-02, run `s20-derive-entrepot-h10-s1` : rafale de
  02:38:19 à 02:44:07, les cinq relances épuisées, épisode mort à 2/10
  événements (`arret: incident : ServerError: erreur serveur HTTP 500`).
  Même profil que la campagne de la suite 20 (journal).
- **Issue retenue.** Allonger l'échelle (un ou deux barreaux de l'ordre de
  180 s) ou la rendre configurable, pour couvrir les rafales mesurées sans
  retarder le diagnostic des erreurs non transitoires. Correction étrangère à
  l'unité de la session (H16.1) : comportement laissé inchangé, à traiter dans
  un commit dédié par une session dont c'est le chemin.

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
