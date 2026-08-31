# Registre d'incohérences

Défauts constatés, avec leur mesure. Une entrée résolue est RETIRÉE ; quand le
registre devient vide, le fichier lui-même est supprimé du dépôt (CLAUDE.md §5).

## Ouverts

_Aucune entrée ouverte._

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
