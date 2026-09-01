# CHANGELOG

## [Non publié]

### 2026-09-01 — U29a3 : environnement Dépôt logiciel du banc a (§S4)

- Détail exécutable de §S4 écrit et committé avant le code : cycle des demandes
  (affectation → revue → [échec CI] → CI verte), générateur nominal seedé,
  validité des cinq actions, `merge` sur CI rouge VALIDE et cassant (le critère
  B.1 « sans casser la CI » y prend son sens), résolution
  `demandes correctement résolues / demandes jugées`, obligations évaluées sur
  l'état réel avec `wait` dû en divergence.
- `src/avo/bancs/skillexec/depot.py` : générateur d'épisodes déterministe
  (mêmes garanties que l'Entrepôt : bruit sur flux séparé, événements
  référençant le nominal), état de vérité master/branches/PR/CI, transitions
  `commit`/`create_pr`/`merge`/`fix_ci`/`wait`, résolution portée au relevé
  (`resolution`, `demandes_resolues`, `demandes_jugees`).
- Preuves : 30 unitaires (`tests/unit/test_banc_depot.py`), balayage « mots du
  banc hors `src/avo/bancs/` » vide, campagne complète verte (lint, mypy strict
  112 fichiers, 592 unitaires, 148 intégration, 5 E2E, build). Le branchement
  adaptateur+CLI du dépôt arrive avec U29a4 (§S7) ; le message du dispatch
  `avo.bancs` le dit désormais.

### 2026-09-01 — Relevé d'incident du banc (§S5.3)

- `banc.json` s'écrit désormais MÊME quand l'épisode est interrompu par une
  erreur (panne d'endpoint plus longue que les relances §H4.5) : `arret` porte
  `incident : <classe>: <message>`, les compteurs valent ce qui a réellement été
  consommé, et l'erreur remonte inchangée. Mesuré le 2026-09-01 : un épisode h25
  de ~13 minutes perdu sans aucune mesure sur des HTTP 500 continus de plus de
  quatre minutes (journal, suite 16).

### 2026-09-01 — U29a2 : adaptateur du banc a et CLI `banc`

- Adaptateur de boucle du banc a (`src/avo/bancs/skillexec/adaptateur.py`) :
  contrat `Environnement` sur l'Entrepôt, quatre outils étiquetés `action` avec
  paramètre `prediction` (§H16.2), contexte de tâche donné en message système
  (§S1.3, §S6.2), issue de la dernière action composée dans l'observation
  (§S2.3), relevé `banc.json` écrit dans le workspace (§S5.3).
- Nouvelle sous-commande `python -m avo banc <nom> --env … --seed … --horizon …`
  (§S6.3) : boucle complète sous gardes, mode `replay` (pile locale) ou `live`
  (endpoint réel) ; la CLI du noyau reste générique, le dispatch vit sous
  `avo.bancs`.
- Mode `state` : le message système d'un pas est désormais celui du contexte
  monté par l'appelant (défaut `prompts.SYSTEME`, ARC inchangé) — §H15.8 amendé ;
  c'est la surface par laquelle un adaptateur fournit son contexte de tâche à K.
- Preuves : 18 unitaires (`tests/unit/test_banc_adaptateur.py`), intégration en
  rejeu HTTP réel (`tests/integration/test_banc_sur_rejeu.py`), cassette E2E
  déterministe `e2e_banc_entrepot.jsonl` + scénario CLI réelle
  (`tests/e2e/test_banc_replay.py`), `make seed`/`make seed-e2e` étendus.

### 2026-09-01 — U29a1 : banc a (patron SkillExecBench), spécification et environnement Entrepôt

- Nouvelle spécification `docs/SPEC_BANCS.md` (§S1–§S7) : cadre commun des bancs
  d'affinage (adaptateurs minces, noyau §H intouché), banc a en entier —
  environnements Entrepôt et Dépôt logiciel, générateurs seedés, score continu,
  bruit de condition 1, scores de référence open-weight consignés (§S5.4),
  découpage en unités U29a1–a4.
- Environnement Entrepôt livré (`src/avo/bancs/skillexec/`) : générateur
  d'épisodes déterministe à double flux (événements/bruit séparés), état de
  vérité et transitions validées, obligations par événement, relevé et score
  continu (§S5.1). 26 preuves unitaires (`tests/unit/test_banc_entrepot.py`).

### 2026-09-01 — Le mode de contexte `state` devient le défaut (décision du responsable)

- `AVO_CONTEXT_MODE` passe de `transcript` à `state` par défaut, sur décision du
  responsable du 2026-09-01 au vu de l'A/B en conditions réelles
  (`docs/rapports/ab-u28-state.md` : 33 actions contre 6 à budget de temps égal,
  ~15× moins de tokens de prompt par action). Le mode `transcript` reste
  activable explicitement. Spéc §H15.0/§H15.7 amendées, README et DAT alignés,
  preuve du défaut révisée (`tests/unit/test_config.py`).

### 2026-09-01 — U28 : A/B transcript/state en conditions réelles, robustesse de la résolution d'action

- A/B des deux modes de contexte sur l'API ARC officielle à périmètre constant
  (run `ab-u28-state`, scorecard `4cedc4e1…` fermé, réconciliation locale/API
  exacte) : rapport comparatif committé (`docs/rapports/ab-u28-state.md`) —
  33 actions contre 6 à budget de temps égal, prompt borné (max 9 223 tokens),
  0 continuation ; recommandation `state` par défaut pour U25 consignée,
  suivie par la décision du responsable du 2026-09-01 (entrée ci-dessus).
- Résolution générique d'action (§H15.8) : la ponctuation traînante du jeton de
  nom est normalisée (bruit de format mesuré en réel), test d'intégration rouge
  avant correction.
- Le test CLI de campagne épingle `AVO_CONTEXT_MODE` : un `.env` local en mode
  `state` faisait diverger le chemin d'exécution de la cassette `transcript`.

### 2026-09-01 — U24 : campagne pilote live menée à terme, robustesse générale du harnais

- Campagne pilote `pilote-u24d` jouée à terme sur l'API ARC officielle
  (`cd82-fb555c5d`, plafonds §A7.1) : scorecard `3b34284d…` fermé,
  réconciliation compteurs locale/API exacte, rapport committé
  (`docs/rapports/pilote-u24d.md`, pilote c avorté documenté dans
  `docs/rapports/pilote-u24c.md`).
- Rapport de campagne (§A7.3 amendé) : les lignes d'inférence de la section
  Coûts viennent des métriques du run — un jeu clos en échec nommé garde sa
  dépense réelle (tokens, appels, durée d'inférence) au lieu d'un zéro
  mensonger ; l'écart actions/tours des jeux refusés est nommé.
- Transport (§H4.5 amendé) : retries étendus à six requêtes (paliers 45 s et
  90 s) — à travers le pont, chaque tentative échouée réchauffe le cache de
  préfixe ; une panne transitoire de quelques minutes devient un retard au lieu
  de clore le jeu.
- A/B des modes de contexte : le générateur épingle l'environnement complet des
  scénarios E2E — un `.env` local à fenêtre différente changeait
  `options.num_ctx` et faisait refuser les deux mini-campagnes par le rejoueur.
- mypy strict rétabli sur les scénarios de campagne (socle partagé hérité au
  lieu d'un emprunt de méthodes inter-classes).

### 2026-09-01 — U30 : gardes de méthode dans les phases (spéc H16 + implémentation)

- `docs/SPEC_HARNAIS.md` §H16 : la structure impose ce que le prompt conseille —
  quatre gardes à l'intérieur des phases P→I→E→B, jamais de nouvelle phase,
  jamais fatales, bornées, débrayables (`AVO_GARDES`, défaut actif ;
  `AVO_GARDE_RETRIES`, défaut 2), valables dans les deux modes de contexte.
- Garde documentaire (H16.1) : les outils d'action restent verrouillés tant que
  `WORKING.md` est vide (mode `state` : champ `hypotheses` de Σ) ; le premier
  Planning compose K (contexte de tâche + notes durables) avec la demande
  « ce que je sais / ce que j'ignore / comment le découvrir ».
- Garde de prédiction (H16.2) : chaque outil d'action exige un paramètre
  `prediction` ; l'appel sans prédiction est une erreur d'outil, l'action n'est
  pas jouée et rien n'est compté (correction au passage : une action refusée par
  un outil ne relit plus l'issue précédente). La prédiction part tronquée dans le
  champ `reasoning` du fil officiel — auditable dans le scorecard. En mode
  `state`, ligne `PREDICTION:` extraite avant que le raisonnement ne soit jeté.
- Garde d'évaluation (H16.3) : l'invite présente prédit-contre-observé et exige
  `VERDICT: confirmee|contredite` ; sans verdict après redemandes, la prédiction
  est réputée contredite. Le verdict remplace l'heuristique de sous-chaîne.
- Garde de persistance (H16.4) : complétion, game over ou intervention du
  superviseur exigent une écriture de `GUIDE.md` avant la prochaine action
  (compteur d'écritures monotone des notes, jamais une comparaison de contenu).
- Preuves : 17 unitaires boucle + 6 unitaires interface + compteur de notes,
  intégration sur `cible` (partie parfaite sous gardes, artefacts exigés
  présents, zéro événement de garde au nominal) et A/B avant/après gardes
  (mêmes issues, mêmes appels, artefacts en plus) ; cassettes E2E régénérées
  sous gardes — mêmes 228/241/76 échanges ; prompts version 1.1.

### 2026-08-31 — Arrêt de la boucle sur l'état terminal du jeu (préalable de U24)

- La boucle agent s'arrête dès que l'environnement déclare un état terminal
  (§H8.3) : le contrat `Environnement` porte `etat_terminal()`, l'interface ARC
  rend « victoire » sur l'état `WIN` (§A5.4), et plus aucun appel au modèle n'est
  émis après la fin du jeu. Le motif d'arrêt du rapport dit désormais
  « victoire » au lieu de « tours_epuises » sur une partie gagnée.
- `GAME_OVER` reste non terminal : `RESET` relance la tentative et la boucle
  traite l'échec en Bug-Fixing, comportement inchangé.
- Mesuré sur les scénarios E2E régénérés : 228 appels au modèle au lieu de 316 en
  mode `transcript`, 76 au lieu de 120 en mode `state`, mêmes 76 actions et même
  RHAE 100.00 (rapport A/B `docs/rapports/ab_mode_contexte.md` mis à jour).

### 2026-08-31 — U22 (clos) : sonde du contrat API ARC réel, fil mesuré des deux côtés

- `scripts/sonde_arc.py` : sonde du contrat de fil de l'API ARC-AGI-3 officielle —
  scorecard étiqueté `probe`/`sonde-u22` ouvert et fermé au nom du responsable
  (`7528ca63-3eff-4866-97c3-8c4a6ded0e63`), RESET + ACTION6 joués sur un jeu réel,
  capture requête→réponse expurgée committée (`tests/fixtures/arc/episodes/`).
- `docs/SPEC_ARCAGI3.md` A1.3/A1.4/A2.1/A3.3/A4.2/A5.2/A5.3 : le format de fil passe
  de « supposé d'après l'export Tycho » à « mesuré » — `frame` au singulier,
  `levels_completed`/`win_levels` (ni niveau courant, ni compteur d'actions par
  frame), `available_actions` en entiers 0–7 (RESET jamais déclaré), `game_id`
  requis dans chaque action, `card_id` requis au RESET et absent des actions,
  `x`/`y` pour ACTION6 (`row`/`col` refusé, mesuré), affinité de session par
  cookies `AWSALB*`, jeux listés non servis par le backend (refus nommé),
  `GET /api/scorecard/<id>` non fiable (404 mesuré avant partie et après fermeture).
- `avo.arc.client` : lecture et émission du fil mesuré, conversion
  `(row, col) → {x: col, y: row}` confinée au client, pot de cookies par instance
  (`TransportUrllib`), `FrameResult` porte `niveaux_requis` et
  `remise_a_zero_complete`, le niveau courant étant dérivé.
- `avo.arc.interface` : `reset` toujours offert (le fil ne le déclare jamais),
  comptage local seul (la réconciliation officielle passe par le résumé de
  scorecard, preuve de campagne U24), outil `action7` (annulation, jeux qui la
  servent).
- `mocks/arc_replay` : même contrat mesuré (refus nommés identiques à l'API,
  résumé de scorecard en `environments`), déviation d'épisode étendue au corps des
  requêtes et rendue en 409 (un 5xx serait retenté et perdrait son motif).
- `tests/integration/test_episode_reel_sonde.py` : l'épisode réel de la sonde
  rejoué vert par le client contre `arc-replay` (corps émis conformes à ce que
  l'API a accepté, réponses réelles parsées sans perte).
- Cassettes E2E régénérées (`make seed-e2e`) : les observations rendues au modèle
  changent avec la liste d'actions déclarées.
- Campagne complète verte : 473 tests unitaires, 138 d'intégration, 4 E2E, lint,
  format, mypy strict.

### 2026-08-30 (suite 6 à 7) — U27 (clos) : mode `state` de la boucle et A/B sur rejeu

- `docs/SPEC_HARNAIS.md` §H15.8 : précise qu'un pas du mode `state` correspond à un
  tour entier (pas à une phase P/I/E/B), et les conséquences d'implémentation qui en
  découlent (un seul appel LLM par tour, rollback-retry par tour, résolution
  générique de l'action depuis le schéma de l'outil, Bug-Fixing implicite,
  persistance de Σ par tour, `413` compté puis fatal).
- `AVO_CONTEXT_MODE` (`transcript`/`state`, défaut `transcript`) dans `avo.config`.
- `avo.loop.boucle.BoucleAgent` : un chemin d'exécution dédié au mode `state`
  (`_jouer_tour_etat`) — prompt `(P, Σₜ, Oₜ)` + notes composé à neuf à chaque tour,
  résolution générique de l'action (nom + paramètres requis lus depuis le schéma de
  l'outil, jamais codés en dur), rollback-retry borné sur patch invalide.
- `avo.memory.workspace.Workspace.ecrire_etat`/`lire_etat` : persistance de Σ dans
  `runs/<run_id>/state/etat.json`, aller-retour exact ; un `BoucleAgent` construit
  sur un workspace qui en porte déjà un le recharge.
- `avo.arc.campagne.ResultatJeu.retries_patch` (défaut `0`, mode `state` seulement,
  §H15.4/§H15.8) : alimenté par `bilan.retries_patch`, nécessaire au rapport A/B.
- `avo.arc.rapport_ab` (fonction pure) : `MesureMode` (RHAE moyen, actions, appels
  au modèle, tokens cumulés, taille moyenne de prompt, retries de patch) et
  `rapport()`, le markdown comparatif `transcript` vs `state`.
- `tests/e2e/generer_cassette_etat.py` : cassette de scénario `state` dédiée
  (`e2e_etat_victoire.jsonl`, 120 échanges, capture en deux passes, régénération
  identique vérifiée) — chemin parfait du jeu `cible-synthetique` traduit en textes
  d'action du contrat `state`.
- `scripts/generer_rapport_ab.py` (`make rapport-ab`) : rejoue deux mini-campagnes
  `python -m avo run-arc --mode replay`, une par `AVO_CONTEXT_MODE`, et écrit
  `docs/rapports/ab_mode_contexte.md` — RHAE 100.00 et 76 actions identiques dans
  les deux modes, 120 appels au modèle en `state` contre 316 en `transcript`.
- Préventif : le sous-processus de `scripts/generer_rapport_ab.py` épingle
  `OLLAMA_HOST`/`ARC_BASE_URL`/le jeton de rejeu pour neutraliser tout `.env` local
  (§A8.5), après qu'une première version en a manqué et a réellement interrogé
  l'endpoint live avant d'être interrompue — aucune donnée n'est restée sur le
  disque, aucun scorecard ARC n'a été ouvert.
- Preuves : tests unitaires (`AVO_CONTEXT_MODE`, persistance de Σ, aller-retour de
  `retries_patch`), 9 tests d'intégration contre le vrai rejoueur HTTP (patch
  valide, rollback-retry, budget épuisé, action inconnue, événement porté par
  l'environnement, persistance et reprise de Σ), `tests/e2e/test_ab_mode_contexte.py`
  (le rapport comparatif committé est rejouable à l'octet près depuis la CLI
  réelle). `make check` intégralement vert (467 unitaires, 132 d'intégration, 4
  E2E), zéro régression.

### 2026-08-30 — U26 : état d'exécution structuré (SKILL.state), mode `state`

- `docs/SPEC_HARNAIS.md` §H15 : contrat d'exécution `(P, Σₜ, Oₜ)` → `(Rₜ, ΔΣₜ, aₜ)`, opérateur de fusion `⊕` à suppression par `null`, schéma possédé et validé par le runtime, rollback-retry borné, persistance/reprise de Σ, schéma ARC v1 à quatre champs (`position`, `essai`, `hypotheses`, `objets`).
- `avo.context.etat` : `Etat` (typé, immuable, toujours conforme au schéma), `decoder_pas` (bloc `state_patch`/`action` de l'annexe A.4 SKILL.state), `appliquer`, `CompteurRetries`, sérialisation JSON aller-retour.
- Module pur, sans branchement dans la boucle agent : le mode `state` lui-même (variable `AVO_CONTEXT_MODE`) est le périmètre de U27, à venir.

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

### 2026-08-28 — U23 : campagnes ARC-AGI-3, de la commande au rapport

- `python -m avo run-arc` : la commande qui joue réellement. Elle enchaîne les jeux, monte l'agent complet sur chacun — interface, outils d'inspection et de notes, boucle, superviseur, lignée —, mesure le RHAE depuis l'historique typé et les baselines du serveur, et écrit tout dans `runs/<id>/`.
- **Quatre mécanismes livrés mais jamais appelés sont enfin branchés sur la boucle** : la continuation en contexte frais (préventive, qui demande son état à l'agent ; réactive sur refus de contexte, écrite par le harnais puisque le segment refusé ne répond plus), les interventions du superviseur, les métriques par appel, par action et par événement, et la proposition d'une version de lignée à chaque niveau complété. Sans eux, un rapport aurait annoncé « 0 continuation, 0 intervention » — vrai et trompeur à la fois, puisque aucune ne pouvait survenir.
- **Garde d'accord** : une campagne live sans `--j-autorise-la-publication` est refusée, et le refus dit pourquoi — jouer enregistre un scorecard sur votre compte. Les quatre plafonds (actions par niveau, actions par jeu, temps par jeu, tokens par jeu) sont obligatoires en live ; leur absence est un refus qui les nomme. L'accord est **persisté avec la campagne**, de sorte qu'une reprise le relit au lieu de se l'accorder toute seule.
- **Reprise** : `python -m avo resume <run_id>` repart d'un run interrompu sans rejouer les jeux terminés. La reprise est de granularité **jeu** : reprendre une partie en cours supposerait de retrouver la frame courante, qu'aucune requête ne rend gratuitement, et le score mêlerait deux tentatives.
- **Rapport** `report.md` : tableau par jeu, détail par niveau qui rend le RHAE vérifiable à la main, coûts, événements, comparaison aux références publiées — et une section de **limites** qui dit ce que la campagne n'établit pas, à commencer par le fait qu'un score obtenu en rejeu ne se compare pas à un score ARC-AGI-3.
- Cibles `make run-arc` et `make resume` corrigées : elles partagent le réseau de l'hôte, sans quoi elles ne joignaient jamais la pile.
- Preuves : 550 tests verts, dont une mini-campagne réelle dont les artefacts sont relus sur disque, deux preuves passant par le point d'entrée réel, et la reprise démontrée par la négative — elle s'exécute avec un client d'inférence qui lève s'il est appelé.

### 2026-08-28 — U20 : RHAE, l'efficacité d'action relative à l'humain

- `avo.arc.rhae` : la mesure officielle du benchmark, implémentée d'après la définition Tycho §3.1. Efficacité d'un niveau plafonnée à 115, niveaux tardifs pondérés plus lourd que les premiers, et score de jeu pris comme **minimum** entre l'efficacité pondérée et un plafond par complétion — de sorte qu'aller très vite sur un niveau ne compense jamais les niveaux non terminés.
- **La somme porte sur tous les niveaux du jeu, pas sur ceux atteints.** C'est la seule lecture qui donne un sens au plafond : sur les seuls niveaux atteints, terminer le premier niveau d'un jeu qui en compte trois vaudrait 100, à égalité avec une partie entièrement gagnée. Avec l'ensemble complet, cette même partie vaut au mieux 16,67.
- **Une action compte pour le niveau depuis lequel elle a été jouée.** L'API renvoie l'action qui complète le niveau 1 avec le numéro du niveau 2 ; l'imputer au suivant volerait une action au premier et en ajouterait une au second — deux scores faux, et de façon compensée, donc invisible sur le total des actions.
- **Une donnée impossible lève au lieu de valoir zéro** : baseline nulle ou négative, niveau hors bornes, trou dans la suite des niveaux, moyenne demandée sur zéro jeu. Rendre 0 ferait passer un défaut de protocole pour une mauvaise performance de l'agent, et le rapport serait faux sans que rien ne le signale.
- Contrat d'implémentation (A6.4) écrit et committé **avant** la première ligne de code, comme l'exige la méthode de travail du dépôt.
- Preuves : 511 tests verts. Contre le rejeu ARC en HTTP, une partie parfaite rend **exactement 100.00** avec des baselines demandées à `/api/games` et non écrites en dur ; une partie perdue, relancée puis gagnée compte **43 actions** au premier niveau — 44 si le RESET de création avait été facturé.
- Ordre du plan corrigé : U23 (runner et rapport) passe avant U21 (E2E), dont la preuve passe par la commande que U23 livre.

### 2026-08-28 — U19 : interface de tâche direct-interaction

- `avo.arc.interface` : l'interface qui relie le client ARC, le rendu, la mémoire de frames et la boucle. Un outil par commande que la frame courante déclare — le filtrage vient de la frame, pas d'une liste figée : quand l'environnement cesse d'offrir une commande, l'agent cesse de la voir, et il l'apprend en observant plutôt qu'en heurtant une erreur.
- **Descriptions muettes sur les effets** : « Joue la commande ACTION1. Coûte une action. » Ce module est le seul endroit où un indice de jeu pourrait se glisser ; dire ce qu'une action *fait* donnerait à l'agent ce qu'il doit inférer et fausserait l'évaluation sans que rien ne l'indique dans les scores.
- Comptage officiel tenu localement et **réconcilié avec celui du serveur** : le compte du serveur fait foi, mais tout écart est journalisé, conservé et remonté — jamais absorbé en silence.
- `RegistreOutils.synchroniser` : un groupe d'outils peut désormais suivre l'environnement et non seulement l'état de la boucle. Sans lui, le registre construit une fois pour le run aurait continué d'exposer des commandes que la frame n'offre plus.
- Revue « zéro indice de jeu » consignée au journal et **rendue exécutable** : un balayage statique des constantes de tous les modules dont un texte atteint le modèle, et un balayage des corps de requête réellement émis pendant un run.
- Preuves : 476 tests verts, dont une partie parfaite dépensant exactement la baseline sans un seul écart de comptage, une perte qui réduit les commandes offertes au modèle jusque dans le tableau `tools` émis, et un niveau complété par l'agent scripté dont le bilan alimente réellement le scorer de lignée.

### 2026-08-28 — U18 : rendu texte et mémoire de frames sans perte

- `avo.arc.rendu` : rendu canonique d'une grille 64×64 précédé d'une ligne d'état, et analyse inverse. **Aucune interprétation ajoutée** — pas de nom d'objet, pas de mise en évidence : souffler « voici la cible » reviendrait à donner la réponse que l'agent doit inférer, et fausserait l'évaluation sans que rien ne l'indique dans les scores.
- `avo.arc.memoire` : toute frame reçue est conservée, décision comme transitoire, et l'agent décide seul de ce qu'il veut revoir. `inspect` rend les découpes **avec les index en marge**, sans lesquels un motif ne peut pas être rattaché aux coordonnées à cliquer ; `read_pixels` donne les valeurs exactes ; `diff` liste les cellules changées et **borne** cette liste, une énumération de milliers de cellules noyant l'information et le budget de contexte.
- Les outils annoncent dans leur description qu'ils sont **gratuits au score** : inspecter longuement avant d'agir ne coûte rien, seule l'action en coûte.
- Preuves : 435 tests verts, dont la propriété rendu ∘ analyse = identité et sept tests sur les frames que le serveur envoie réellement.

### 2026-08-28 — U17 : client de l'API ARC-AGI-3

- `avo.arc.client` : réponses normalisées, **étiquetage de chaque frame selon son rôle réel** — transitoire, décision, initialisation de reset ou de niveau, terminal gagnant ou perdant. Une frame terminale n'est pas une frame de décision : sans cette distinction, le harnais pourrait rattacher une action à une grille depuis laquelle il était impossible d'agir.
- Historique typé rattachant chaque action à la frame d'où elle a été choisie, persisté par niveau dans le workspace du run.
- **Garde anti-publication structurelle** : en mode rejeu, construire un client vers autre chose qu'un hôte local lève à la construction. Jouer via l'API officielle enregistre un scorecard ; un test qui l'atteindrait par accident publierait un résultat. La base ARC pointe désormais la pile locale en mode rejeu.
- Politique de transport extraite et partagée avec le client d'inférence : la spécification exige « les mêmes règles », et deux implémentations parallèles auraient fini par diverger sans que rien ne le signale.
- Preuves : 393 tests verts, dont une partie complète menée par le client contre le serveur local — la première rencontre des deux côtés du contrat de fil.

### 2026-08-28 — U16 : contrat ARC-AGI-3 local et jeu synthétique `cible`

- `mocks/arc_replay` : moteur du jeu `cible` **en forme fermée** — la baseline de chaque niveau se calcule au lieu d'être mesurée, si bien qu'une partie parfaite dépense un nombre d'actions connu à l'avance et que le RHAE attendu sera vérifiable au chiffre près.
- Serveur stdlib exposant le contrat officiel : listing avec baselines, cycle de scorecard, commandes de jeu rendant frames, état, score et actions disponibles. Mode rejeu d'épisodes dont toute déviation est dite explicitement plutôt qu'absorbée.
- Le format de fil, jusqu'ici seulement annoncé « à confirmer », est désormais **écrit** dans la spécification et implémenté des deux côtés. Sans contrat écrit, client et rejeu auraient divergé silencieusement.
- Service ajouté à la pile compose avec healthcheck, partie arc du seed, fumée de pile étendue aux deux services.
- Assumé et écrit : contrairement au rejeu du serveur d'inférence, celui-ci simule un contrat non mesuré — chaque partie réelle publierait un scorecard. La sonde à venir produira l'épisode authentique qui fera référence.
- Preuves : 359 tests verts, dont une partie gagnée à la main par requêtes HTTP dépensant exactement la somme des baselines.

### 2026-08-28 — U15 : superviseur anti-stagnation

- `avo.supervisor` : trois détecteurs **mesurés, jamais interprétés** — stagnation, cycle improductif, rafale de corrections. Un déclencheur qui dépendrait de ce que le modèle raconte de lui-même serait aveugle au moment précis où il tourne en rond.
- Le cycle improductif exige une **double condition** : la même action répétée **et** la frame inchangée. Répéter une action qui produit des effets différents est une exploration légitime.
- L'intervention est un appel séparé sur **contexte propre** : le superviseur reçoit un résumé factuel et les notes, jamais l'historique de l'acteur — hériter du contexte, ce serait hériter de l'ornière dont il doit le sortir. Son résultat est injecté en append sous une balise, avec cooldown et journalisation du motif.
- **Il n'a aucun outil et ne joue jamais d'action** : son seul pouvoir est d'écrire un message que l'acteur reste libre d'ignorer. Un superviseur qui agirait rendrait le score inattribuable.
- Les variables qui règlent le seuil et le cooldown, nommées par la spécification, manquaient à la configuration.
- Preuves : 324 tests verts, avec un cas négatif pour chaque détecteur et quatre tests d'intégration passant par le vrai client et le vrai rejeu.

### 2026-08-28 — U14 : lignée de solutions et fonction de score

- `avo.lineage` : dépôt git jetable et dédié par run, portant la suite des versions validées selon la politique du papier AVO — une version n'entre dans la lignée que si elle est correcte **et** au moins aussi bonne que la meilleure déjà committée. Une régression reste dans la trajectoire interne de recherche.
- **Isolation absolue du dépôt du projet** : toute commande git emploie un répertoire de dépôt et un arbre de travail explicites, si bien que git ne remonte jamais l'arborescence. Un test compare le statut du dépôt du projet avant et après plusieurs propositions.
- Défaut corrigé par la preuve : la garde d'isolation s'exécutait après l'écriture des notes. Sur une lignée non isolée, rien ne doit être écrit nulle part.
- Fonction de score branchable : score lexicographique `(niveaux complétés, −actions)` pour ARC, où progresser prime et où, à progression égale, moins d'actions vaut mieux ; scorer déterministe pour éprouver la boucle.
- `git` devient la seule dépendance système, ajoutée aux deux images. Le principe « zéro dépendance Python d'exécution » reste tenu.
- Preuves : 297 tests verts, dont trois progressions donnant trois versions aux scores exacts et une régression intercalée refusée.

### 2026-08-28 — U13 : boucle agent Planning → Implementation → Evaluation → Bug-Fixing

- `avo.loop` : machine d'états **close** — tout événement impossible dans l'état courant lève en nommant les événements admis, plutôt que de rester sur place et de produire un run qui tourne sans avancer. La machine est du code, le contenu des phases est du prompt : une transition qui dépendrait de l'interprétation d'un texte libre serait irreproductible.
- L'environnement prime sur le discours du modèle : niveau complété et partie perdue sont des faits qu'il rend, seule la contradiction est déclarée par le modèle. Sans cela, le score serait manipulable par le texte.
- Les outils d'action ne sont exposés qu'à la phase où agir est permis : ailleurs, le modèle ne peut pas dépenser une action par mégarde.
- Prompts versionnés, courts, et **sans aucune règle de jeu** — vérifié par un test qui cherche une liste de termes interdits. Un indice glissé là invaliderait toute l'évaluation sans que rien ne le signale dans les scores.
- Bornes d'actions distinctes par niveau et par jeu, dépassement menant à un arrêt propre qui nomme la borne franchie. Les variables correspondantes, nommées par la spécification, manquaient à la configuration.
- Défaut de conception corrigé par la preuve : la boucle appelait l'environnement directement, si bien que l'outil d'action n'était jamais exécuté. L'action passe désormais par le registre.
- Preuves : 271 tests verts, dont huit faisant tourner la boucle en HTTP réel contre le rejeu, sur un environnement factice.

### 2026-08-28 — U12 : registre d'outils et dispatch

- `avo.tools.registre` : un outil se déclare par un nom, une description, un schéma de paramètres, une fonction et des étiquettes. L'exposition au modèle est filtrée par étiquette, ce qui permettra de n'offrir les outils d'action qu'à l'état où agir est permis.
- **Rien de ce que fait un outil n'interrompt le run** : nom inconnu accompagné de la liste des outils disponibles, argument obligatoire absent, type incorrect, énumération non respectée, argument inconnu, arguments JSON invalides, fonction qui lève — tout revient au modèle sous forme de texte diagnostiquable pour qu'il se corrige.
- Exécution séquentielle produisant un message `role: tool` par appel, en append-only ; garde du nombre d'appels par tour qui clôt le tour par un message explicite plutôt que de tronquer en silence, avec un compteur cumulable entre lots.
- Défaut corrigé : la variable de garde, nommée par la spécification, était absente du tableau des variables et de la configuration. Ajoutée aux trois endroits.
- Preuves : 245 tests verts, dont cinq d'intégration routant l'appel d'outil réellement demandé par le modèle jusqu'à un vrai outil de notes.

### 2026-08-28 — U11 : notes persistantes

- `avo.memory.notes` : `GUIDE.md` et `WORKING.md` dans le workspace du run, aux rôles distincts — compréhension durable d'un côté, brouillon du niveau courant de l'autre. Deux noms et pas trois : un espace de notes libre se transformerait en système de fichiers parallèle dont plus rien ne garantirait la relecture.
- Validation stricte des noms, avec tolérance de casse et d'extension mais refus de tout chemin d'évasion. Une note jamais écrite est vide, pas absente ; une note vide est annoncée dans le bloc injecté plutôt qu'omise, car son absence est une information pour l'agent.
- Outils `note_read` et `note_write` avec leurs schémas : le domaine lève, la surface d'outil convertit en texte rendu au modèle pour qu'il se corrige, sans jamais interrompre le run.
- Deux défauts corrigés : un renvoi de spécification vers un chapitre inexistant, et une signature de métrique où un champ pouvait remplir l'horodatage par accident — révélé par le typage strict, il n'aurait produit qu'une métrique silencieusement fausse.
- Preuves : 217 tests verts, dont la promesse centrale vérifiée sur la chaîne réelle — après renouvellement du contexte, le contenu noté réapparaît et l'ancienne observation a disparu.

### 2026-08-28 — U10 : budget de contexte et continuation en contexte frais

- `avo.context.contexte` : seuil de continuation dérivé du budget utile, estimation suivant la calibration, ouverture d'un segment frais composé exactement du message système, de l'état de continuation, des notes et de l'observation courante, l'ancien segment étant archivé et non effacé.
- Le refus pour contexte trop grand est traité en **cas nominal** : il apprend le plafond réel annoncé par le serveur et déclenche la même continuation, sans jamais rejouer sur le segment plein. Deux refus **consécutifs** — le second survenant sur le segment frais que la continuation vient de créer — lèvent une erreur explicite nommant les valeurs en cause : aucune continuation ne peut plus aider. Un échange abouti remet la série à zéro.
- L'historique reprend fidèlement les appels d'outils demandés par le modèle, sans quoi un tour suivant lui présenterait une conversation dont il ne reconnaîtrait pas ses propres actes.
- Preuves : 191 tests verts. Les tests d'intégration n'emploient aucun refus simulé : ils rejouent celui que le vrai serveur a rendu, avec son corps de quota authentique.

### 2026-08-28 — U9 : transcript append-only

- `avo.context.transcript` : structure **fonctionnelle** — ajouter un message rend un nouveau transcript partageant le préfixe, l'instance existante n'étant jamais modifiée. Message système figé à l'ouverture du segment, types gelés, aucune méthode d'insertion, de retrait ou de remplacement.
- Empreintes de préfixe et gardes associées : un historique dont la tête aurait changé est détecté et signalé par une erreur explicite, au lieu d'être accepté en silence. Motif mesuré : le préremplissage domine le coût, et une tête modifiée invalide le cache de préfixe du serveur — ce qui ne se voit pas dans les résultats, seulement dans la facture de temps.
- Preuves : 164 tests verts, dont dix tours enchaînés vérifiant la stabilité de chaque préfixe, la détection d'une tête réécrite ou d'un message inséré, un test de surface garantissant qu'aucune API de mutation n'existe sur le type, et cinq tests tenant l'invariant sur l'échange réellement enregistré.

### 2026-08-28 — U8 : journalisation, workspace de run et comptabilité des tokens

- `avo.runlog` : journalisation JSON d'une ligne, niveaux, identifiant de run corrélant toutes les lignes, et **filtre qui masque les valeurs sensibles** dans le message comme dans les champs imbriqués — la garantie « aucun secret » ne repose donc pas sur la discipline des appelants.
- `avo.memory.workspace` : arborescence complète du run, manifeste portant la configuration résolue sans secret et la version du harnais, métriques en JSONL, transcripts numérotés par segment, rapport. Un run s'audite sans le dépôt.
- `avo.context.tokens` : estimation locale des tokens et registre qui se recalibre sur le compte réel rendu par le serveur, sans se dérégler si celui-ci ne rend pas ses compteurs.
- `make smoke-live` devient réelle : version du serveur, modèles servis, complétion courte et appel d'outil contre le VRAI endpoint. Hors campagne, exige `.env`.
- Preuves : 137 tests verts, dont un run complet contre le rejeu du contrat réel qui cherche la clé dans **tous** les fichiers produits. Fumée live verte.

### 2026-08-28 — U7 : client d'inférence

- `avo.llm.client` : construction du corps `/api/chat`, réponse normalisée (contenu, raisonnement, appels d'outils, compteurs, durées), erreurs typées — refus d'authentification **fatal**, dépassement de contexte portant les champs réels du quota, erreur serveur et erreur de transport **retentées**, erreur de protocole. Retries bornés à trois nouvelles tentatives avec attentes de 1, 4 et 16 secondes affectées d'un jitter de ±25 %, jamais sur un refus 4xx.
- **L'enregistreur construit désormais ses corps avec le client**, et le contrat a été réenregistré sur cette base : la cassette porte exactement ce que le client émet. Sans cela, une simple différence de sérialisation aurait suffi à ce qu'aucun échange enregistré ne s'apparie jamais.
- Détail du contrat découvert et spécifié : sur la surface native, un appel d'outil arrive avec `done_reason: "stop"` et non `"tool_calls"`. La détection se fait sur la présence de `message.tool_calls` — sans quoi la boucle agent aurait ignoré tous les appels d'outils.
- Correction d'un défaut consigné au registre : la configuration n'imposait pas le plancher de budget de sortie lorsque le raisonnement natif est actif, alors que la spécification l'exige. Règle implémentée et testée.
- Clarification de la politique de retry, dont la formulation était ambiguë.
- Preuves : 94 tests verts dont 27 pour le client et 7 contre le rejeu du contrat réel, détection de dérive verte contre le serveur réel, lint, format et mypy strict.

### 2026-08-28 — U6 : configuration du harnais

- `avo.config` : lecture de l'environnement puis d'un `.env` minimal, avec précédence de l'environnement. Une ligne de fichier ininterprétable est une erreur qui nomme son numéro de ligne, jamais une ligne ignorée en silence.
- Validation nommée de chaque variable : entier strictement positif, réel borné, booléen aux formes usuelles, URL http(s) avec hôte vérifié et slash final retiré. Une configuration fausse s'arrête au démarrage en désignant la variable fautive.
- Deux modes : en **rejeu**, aucun secret n'est requis et la configuration pointe la pile locale ; en **live**, l'absence d'un secret est une erreur explicite — jamais une valeur par défaut.
- Budget de prompt dérivé de la marge que le proxy applique, et plafond appris depuis un `413` qui **abaisse seulement** la fenêtre : une réponse d'erreur ne peut pas relever silencieusement une limite choisie plus étroite.
- Aucun secret journalisable : le résumé et la représentation masquent les clés, vérifié par test et par exécution réelle.
- Preuves : 60 tests verts dont 28 pour la configuration, lint, format et mypy strict.

### 2026-08-28 — U5 : pile de services locale

- `Dockerfile` multi-étages : image de **production** `avo` (176 Mo — le paquet seul, aucune dépendance d'exécution) séparée de l'image de développement `avo-dev` (320 Mo — seul endroit où vivent make, pytest, ruff et mypy).
- `docker-compose.yml` : service `llm-replay` sur le port 11435, dépôt monté, healthcheck HTTP sur un nouveau point `/_health` indépendant des cassettes. **Aucun secret n'entre dans la pile** : sans clé fournie, le rejoueur accepte tout jeton porteur et ne distingue que l'absence d'en-tête, ce qui suffit à démontrer refus et succès.
- Cibles `build`, `up`, `down`, `ps`, `logs` et `smoke-pile`, refusées depuis l'intérieur d'un conteneur avec un message expliquant qu'elles pilotent Docker depuis l'hôte.
- Correction d'un défaut trouvé à l'exécution : le rejeu écoutait sur la boucle locale du conteneur, inatteignable par le port publié. L'interface d'écoute devient explicite — boucle locale par défaut, `0.0.0.0` passé par la pile.
- Preuves : image de production construite, service `healthy`, fumée de 6 contrôles verts depuis l'hôte par le port publié, cycle `up → down → up` rejoué, campagne complète verte (32 tests, lint, format, mypy strict).

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

### 2026-08-30 — Cinquième source (SKILL.state) et lot G au backlog

- Ajout dans `knowledge/` de l'export complet du papier SKILL.state (arXiv:2608.26263, fourni par le responsable) : texte intégral, figure d'architecture, dix tableaux transcrits, prompts exacts des quatre runtimes comparés, PDF d'origine ; index mis à jour, SKILL.state y étant présenté comme **alternative mesurable** au transcript append-only retenu par H5 (contrainte mesurée du cache de préfixe), à départager par A/B.
- Ajout du **lot G** au backlog et au plan directeur : U26 (chapitre H15 puis runtime d'état structuré `avo.context.etat` — patch `⊕`, validation par le runtime, rollback-retry, preuves calquées sur la taxonomie d'erreurs open-weight du papier), U27 (mode `state` optionnel de la boucle, défaut `transcript` inchangé, A/B sur rejeu avec rapport), U28 [LIVE] (A/B en conditions réelles après la campagne pilote), U29 (benchmarks InterCode CTF / τ-Bench — hors périmètre, en attente d'arbitrage explicite du responsable).
- Mentions périmées corrigées : `README.md` (état actuel remis au réel — U3–U20 et U23 livrées, prochaine unité U21 ; cinq sources), `CLAUDE_PROJECT.md` (plage d'unités, terminologie SKILL.state).
- Branche de session rattrapée sur `main` par **fusion** (pas de réécriture d'historique) : le redécoupage de backlog committé avant de connaître l'avancement réel est remplacé par les ajouts ci-dessus.

### 2026-08-30 — Recette de joignabilité de la session et `.env.example`

- Vérification de la joignabilité de l'endpoint LLM depuis la session interactive : sortie réseau limitée au port 443 (contrôles discriminants rejoués), serveur sain vu de l'extérieur — conclusion du 2026-08-27 inchangée ; conséquence consignée : les unités [LIVE] s'exécutent depuis un environnement non limité au 443 (celui du worker convient).
- Ajout de `.env.example` (suivi par git, `!.env.example` dans `.gitignore`) : les 20 variables du projet — 17 applicatives (H3.1) et 3 d'outillage — avec rôle, format, caractère requis, défaut et exemple non sensible ; exhaustivité contrôlée par script contre `config.py`, le Makefile et les scripts.
- Table des variables du `README.md` complétée (sept variables applicatives manquantes, note d'outillage, renvoi vers `.env.example`).

### 2026-08-30 — Pont HTTPS 443 vers l'endpoint d'inférence (Netlify)

- Ajout de `infra/llm-proxy/` (fonction edge Netlify) et du `netlify.toml` racine : relais des surfaces `/api/*` et `/v1/*` vers l'endpoint, authentification en passthrough (aucun secret ni adresse en dur — l'URL d'origine vit dans la variable de site `LLM_ORIGIN_URL`), `404` hors API, erreurs explicites. Site déployé sur le compte Netlify du responsable et recetté de bout en bout depuis un environnement limité au port 443 : `401` sans clé, version, tags, complétion réelle et streaming NDJSON à travers le pont (mesures au journal).
- Conséquence : les unités [LIVE] deviennent exécutables depuis les sessions interactives ; `OLLAMA_HOST` peut pointer le pont (`.env.example` et `CLAUDE_PROJECT.md` mis à jour ; limite de plate-forme documentée : 40 s avant en-têtes de réponse).
- Observation consignée : l'endpoint sert désormais aussi `qwen3.8:27b` (absent le 2026-08-27) ; le modèle de travail reste `qwen3.6:35b`.

### 2026-08-30 — U21 : E2E de partie complète, pont de build TLS, routine horaire autorisée sur ARC Prize

- U21 livrée et close : cassettes de scénario seedées et committées (capture en deux passes déterministe, auto-vérifiée), E2E par la CLI réelle sur la pile compose — victoire 3 niveaux à RHAE exactement 100.00 (76 actions, rapport, lignée à 3 commits, reprise sans nouvel appel au modèle) et échec → RESET → victoire à la valeur fermée (43 actions au niveau 1) ; cibles `make seed-e2e` et `test-e2e` par le réseau de l'hôte ; campagne `make check` verte.
- Construction : support générique d'un CA de proxy TLS interceptant (`certs/`, spécifié en H2.4) — l'image se construit désormais derrière un proxy d'environnement, sans jamais désactiver la vérification TLS.
- Routine planifiée « CloudWorker AVO (horaire) » provisionnée par le responsable : prompt = `docs/.routine` + variables non persistées (endpoint via le pont HTTPS 443, clés) ; doctrine persistée — unités [LIVE] prenables par la routine munie des secrets et de l'autorisation de publication, interdiction de benchmaxing sans exception (MASTER_PLAN §3, CLAUDE_PROJECT).
- Registre : la boucle ne s'arrête pas sur l'état terminal du jeu (44 tours d'inférence à vide mesurés) — issue retenue : préalable de U24 ; MASTER_PLAN §4 aligné sur le réel (`build` s'exécute en sus de `make check`).

## [Publié]

_Aucune publication pour le moment._
