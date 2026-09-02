# Backlog

Statuts : `[ ]` non commencé · `[~]` en cours ou insuffisamment vérifié · `[x]` terminé et intégralement vérifié.

Ordre d'exécution et Definition of Done commune : `docs/MASTER_PLAN.md`. Chaque unité
cite ses chapitres de spécification (`docs/SPEC_HARNAIS.md` = H, `docs/SPEC_ARCAGI3.md`
= A) ; ses spécifications sont déjà écrites — une session la prenant code directement.
Les unités marquées **[LIVE]** exigent les secrets d'environnement ; leur prise
obéit à MASTER_PLAN §3 — la routine planifiée provisionnée par le responsable les
prend comme les autres, une session sans secrets ne les prend jamais.

---

## U1 — Import des sources de connaissance dans `knowledge/` `[x]`

Réalisé le 2026-08-27 (4 exports fidèles, images, PDF, index ; vérifications au
journal). Unité documentaire close.

## U2 — Spécification complète du harnais `[x]`

Réalisé le 2026-08-27 : `docs/SPEC_HARNAIS.md` (H1–H14), `docs/SPEC_ARCAGI3.md`
(A1–A8), `docs/MASTER_PLAN.md`, backlog redécoupé en unités d'une session, DAT mis à
jour. Spécification rédigée après lecture intégrale des quatre exports et sur les
mesures live du 2026-08-27 (endpoint, `/api/games`). Unité documentaire close —
c'est la dernière : toutes les suivantes livrent du code.

---

## Lot A — Socle

## U3 — Squelette Python et outillage conteneurisé `[x]`

`@spec` H2. `pyproject.toml` (paquet `avo`, py ≥ 3.11, zéro dépendance runtime ;
dev : pytest, ruff, mypy **dans l'image**), arborescence H2.2, `Dockerfile` de
développement, `Makefile` Docker-first avec toutes les cibles H2.3 (celles dont
l'objet n'existe pas encore échouent en nommant leur unité), `python -m avo
--version`, `.gitignore` complété (`runs/`). README : Prérequis/Commandes/Structure
réécrits sur le réel.

- Preuves : test unitaire de `--version` ; `make lint`, `make typecheck`,
  `make test-unit` verts ; `make check` vert (périmètre existant).
- **Livré et intégralement vérifié le 2026-08-27**, campagne complète exécutée **dans
  le conteneur** : `ruff check` et `ruff format --check` (14 fichiers), `mypy` en mode
  strict (14 fichiers, aucune anomalie), `pytest` (7 tests verts, dont une invocation
  réelle de `python -m avo` dans un processus séparé et le refus explicite de chaque
  commande non livrée). Vérification opérateur (MASTER_PLAN §5) des commandes de la
  CLI, sur l'hôte puis dans le conteneur : sorties et codes de sortie conformes.
  Contrôlé également qu'une exécution conteneurisée ne laisse ni cache ni fichier
  `root` dans le dépôt monté.

## U4 — `llm-replay` : enregistrement et rejeu du vrai endpoint `[x]`

`@spec` H4.7. **Aucun faux serveur Ollama n'est écrit** : le contrat n'est pas
inventé, il est capturé sur le serveur dédié fourni. Livrer (a) l'enregistreur —
un mode du client H4 qui écrit chaque échange HTTP réel dans une cassette
`tests/fixtures/llm/cassettes/*.jsonl`, expurgée de la clé et de l'hôte ; (b) le
rejoueur `mocks/llm_replay/`, qui sert ces cassettes en appariant les requêtes sur
une clé stable et rend une **erreur explicite** si une requête ne correspond à
aucune entrée ; (c) l'injection de fautes que le serveur réel ne produit pas à la
demande (500, latence, coupure) ; (d) les cibles `make record-llm` et
`make test-int-live` (toutes deux exigent `.env`) ; (e) `make seed` (partie llm).
Les erreurs **réelles** — 401 sans clé et avec clé invalide, 413 avec son corps de
quota — sont enregistrées depuis le vrai serveur, où elles ont déjà été mesurées le
2026-08-27, jamais fabriquées.

- Preuves : unitaires (appariement de requêtes, expurgation vérifiée en cherchant la
  clé dans les cassettes écrites, erreur explicite sur requête inconnue, injection de
  fautes) ; intégration HTTP réelle contre le rejoueur sur port éphémère.
- **[LIVE] pour l'enregistrement uniquement** : la capture initiale des cassettes
  appelle le vrai endpoint (coût GPU modeste, aucun effet de bord irréversible). Le
  worker planifié peut livrer le code et les tests de rejeu ; si `.env` est absent,
  il laisse l'unité `[~]` en nommant les cassettes restant à enregistrer.
- **Livré et intégralement vérifié le 2026-08-27.** Contrat réel enregistré :
  7 échanges (`tests/fixtures/llm/cassettes/contrat_endpoint.jsonl`, 5,6 Ko) —
  401 sans clé, 200 version, 200 tags, 200 conversation, 200 conversation avec
  appel d'outil, 401 clé invalide, 413 avec son corps de quota
  (`max_context_tokens = 229376`). La requête de dépassement pesant 1,98 Mo n'est
  pas stockée : seule son empreinte l'est. Aucun secret ni hôte dans la cassette,
  vérifié par test. Preuves : 12 tests unitaires de cassette, 12 tests d'intégration
  HTTP réels (dont le rejeu des 7 échanges enregistrés, l'erreur explicite sur
  requête inconnue et l'injection de fautes), `make test-int-live` vert contre le
  serveur réel — aucune dérive. Campagne complète verte en conteneur : ruff, ruff
  format, mypy strict (24 fichiers), 31 tests.

## U5 — Pile compose des services `[x]`

`@spec` H2.4. L'image de développement est déjà livrée par U3 : cette unité livre la
**pile de services** — `docker-compose.yml` (service `llm-replay`, healthcheck ;
`arc-replay` rejoindra en U16), image de production (`make build`), `make up/down/seed`
opérationnels, README/DAT mis à jour (lancement, ports).

- Preuves : `make build` ; `make up` puis healthcheck vert vérifié par script ;
  E2E de fumée : `curl` du service de rejeu via le port composé, 401 sans clé, 200 avec.
- **Livré et intégralement vérifié le 2026-08-28.** `Dockerfile` multi-étages :
  `avo` (production, 176 Mo, paquet seul) et `avo-dev` (320 Mo, outillage).
  `docker-compose.yml` : service `llm-replay` sur 11435, healthcheck sur `/_health`,
  dépôt monté, **aucun secret injecté**. Cibles `build`, `up`, `down`, `ps`, `logs`,
  `smoke-pile` livrées, les cibles de pile étant refusées depuis l'intérieur d'un
  conteneur avec un message qui le dit. Fumée `scripts/smoke_pile.sh` : **6 contrôles
  verts** (healthcheck `healthy`, `/_health` 200, `/api/version` 401 sans clé et 200
  avec, `/api/tags` 200, corps rejoué identique à l'enregistrement). Cycle
  `up → down → up` rejoué. Campagne complète verte : 32 tests, lint, format, mypy
  strict (24 fichiers).
- Défaut trouvé et corrigé pendant l'unité : le rejoueur écoutait sur la boucle
  locale **du conteneur**, que le port publié n'atteint pas. L'interface d'écoute est
  désormais explicite — `127.0.0.1` par défaut pour ne rien exposer par accident,
  `0.0.0.0` passé par la pile.

## Lot B — Client LLM

## U6 — Configuration `avo.config` `[x]`

`@spec` H3. Lecture env + `.env`, validation nommée, modes replay/live, budget
`H3.2`, aucune valeur secrète journalisée.

- Preuves : tests unitaires nominal/limites/erreurs (variable absente, entier
  invalide, budget dérivé, mode live sans secret → erreur explicite).
- **Livré et intégralement vérifié le 2026-08-28.** `src/avo/config.py` : analyse de
  `.env` (commentaires, guillemets, `export`, ligne ininterprétable → erreur nommant
  le numéro de ligne), précédence environnement > fichier, validation nommée de
  chaque variable (entier, réel borné, booléen, URL), modes rejeu/live, budget
  `floor(contexte / 1,15) − num_predict`, plafond appris qui **abaisse seulement**
  (un `413` ne peut pas élargir une fenêtre configurée plus étroite), et masquage
  des secrets dans `resume()` comme dans `repr()`.
  **28 tests unitaires** couvrant ces cas ; vérification opérateur dans le conteneur
  sur les deux modes, la clé réelle n'apparaissant ni dans le résumé ni dans la
  représentation. Campagne complète verte : 60 tests, lint, format, mypy strict.

## U7 — Client d'inférence `[x]`

`@spec` H4.1–H4.5. `LLMClient.chat` sur `/api/chat` (think, options, tools), parsing
`ChatResult`, erreurs typées, retries bornés avec jitter.

- Preuves : unitaires (parsing, classification d'erreurs, politique de retry) ;
  intégration contre `llm-replay` sur **cassettes enregistrées du vrai serveur** :
  nominal, tool_call, 401 fatal, 413 → `ContextOverflow` avec ses champs réels,
  500 → retries puis échec, latence < timeout. `make test-int-live` rejoue les mêmes
  scénarios contre l'endpoint réel pour détecter toute dérive du contrat.
- **Livré et intégralement vérifié le 2026-08-28.** `src/avo/llm/client.py` :
  construction du corps (§H4.2) avec surcharges typées, `ChatResult` normalisé,
  erreurs typées (`AuthError` fatale, `ContextOverflow` portant les champs réels,
  `ServerError`, `TransportError`, `ProtocolError`), retries bornés avec jitter,
  transport et attente injectables. **L'enregistreur construit désormais ses corps
  avec le client** (§H4.7) : la cassette porte exactement ce que le client émet, et
  le contrat a été réenregistré sur cette base. Preuves : 27 tests unitaires,
  7 tests d'intégration du client contre le rejeu du contrat réel, `make
  test-int-live` vert — aucune dérive. Campagne complète : **94 tests**, lint,
  format, mypy strict (29 fichiers).
- Détail du contrat découvert et spécifié : sur la surface native, un appel d'outil
  arrive avec `done_reason: "stop"` et non `"tool_calls"` — la détection se fait sur
  la présence de `message.tool_calls` (§H4.3, propriété `demande_outil`).

## U8 — Comptabilité, journalisation, workspace de run `[x]`

`@spec` H4.6, H6.1, H11 ; H4.8. `runlog` (logs JSON sans secret, id de run),
`manifest.json`, `metrics.jsonl`, transcripts JSONL par segment ; `TokenLedger`
(estimé vs réel) ; cible `make smoke-live` (jamais dans check).

- Preuves : unitaires (aucune fuite de secret dans les sorties — test qui greppe la
  clé dans les logs produits ; métriques cumulées correctes) ; intégration : un
  échange complet contre llm-replay produit un workspace conforme H6.1.
- **Livré et intégralement vérifié le 2026-08-28.** `avo.runlog` (JSON une ligne,
  run_id corrélant, **filtre qui masque les secrets dans le message comme dans les
  champs imbriqués** — la garantie ne repose donc pas sur la discipline des
  appelants), `avo.memory.workspace` (arborescence H6.1, manifeste sans secret,
  `metrics.jsonl`, transcripts par segment, `report.md`),
  `avo.context.tokens` (estimation calibrée par le compte réel du serveur),
  lectures `version()`/`modeles()` du client et **`make smoke-live` réelle**.
  Preuves : 35 tests unitaires, 8 d'intégration dont la recherche de la clé dans
  **tous** les fichiers produits par un run. Campagne : **137 tests**, lint, format,
  mypy strict (37 fichiers). Fumée live verte contre le serveur réel.
- Sous-commande `resume` ré-attribuée de U8 à U13 : elle reconstruit l'état ET repart
  sur un segment frais, ce qui suppose la boucle agent, pas le seul workspace.

## Lot C — Contexte et mémoire

## U9 — Transcript append-only `[x]`

`@spec` H5.1–H5.2. Structure immuable en tête, hash de préfixe, sérialisation,
estimation calibrée corrigée par `prompt_eval_count`.

- Preuves : unitaires — l'invariant : après N tours simulés, le hash du préfixe
  envoyé au tour k est préfixe de celui du tour k+1 ; toute API qui muterait la tête
  n'existe pas (test de surface du module).
- **Livré et intégralement vérifié le 2026-08-28.** `avo.context.transcript` :
  structure **fonctionnelle** — `ajouter` rend un nouveau transcript partageant le
  préfixe, l'instance existante n'est jamais modifiée ; `Message` et `Transcript`
  gelés avec `slots` ; message système figé à l'ouverture du segment ; empreintes
  `empreinte()` / `empreinte_prefixe(n)` et gardes `prolonge()` /
  `verifier_prolonge()` levant `PrefixeRompu`. Preuves : 22 tests unitaires — dont
  dix tours enchaînés où chaque préfixe reste stable, la détection d'une tête
  réécrite, d'un message inséré au milieu et d'un système modifié, et le **test de
  surface** vérifiant qu'aucune des méthodes de mutation listées n'existe sur le
  type — et 5 tests d'intégration sur l'échange réel enregistré, y compris la
  calibration de l'estimation par le `prompt_eval_count` du serveur.
  Campagne : **164 tests**, lint, format, mypy strict (40 fichiers).

## U10 — Budget et continuation en contexte frais `[x]`

`@spec` H5.3–H5.4, H3.2. Déclenchement au seuil, état de continuation écrit par
l'agent, nouveau segment (système + continuation + notes + observation), `413` →
continuation immédiate + budget appris, double-413 → erreur fatale explicite.

- Preuves : unitaires (seuils, recalcul du budget) ; intégration contre llm-replay
  avec petit budget forcé : la continuation se produit, le contenu du segment frais
  est exactement celui spécifié, un 413 simulé est absorbé, deux → erreur.
- **Livré et intégralement vérifié le 2026-08-28.** `avo.context.contexte` : seuil
  dérivé du budget (`ratio × budget_prompt`), estimation qui suit la calibration,
  `continuer()` composant le segment frais **exactement** système + continuation +
  notes + observation et archivant l'ancien sans l'effacer, `absorber_depassement()`
  qui apprend le plafond réel et compte les dépassements **consécutifs**,
  `BudgetIncoherent` au second. L'historique reprend fidèlement les appels d'outils
  demandés par le modèle. Preuves : 21 tests unitaires et 6 d'intégration — ces
  derniers n'emploient **aucun 413 simulé** : ils rejouent celui que le vrai serveur
  a rendu, avec son corps de quota authentique. Campagne : **191 tests**, lint,
  format, mypy strict (43 fichiers).

## U11 — Notes persistantes `[x]`

`@spec` H6.2, H7.3. `GUIDE.md`/`WORKING.md` dans le workspace, outils
`note_read`/`note_write` (limités à ces deux noms), injection en tête de segment
frais.

- Preuves : unitaires (lecture/écriture/refus d'un autre nom) ; intégration :
  après continuation (U10), les notes réapparaissent dans le prompt du segment frais.
- **Livré et intégralement vérifié le 2026-08-28.** `avo.memory.notes` :
  `GUIDE.md` et `WORKING.md` dans `runs/<id>/notes/`, validation stricte des deux
  seuls noms (casse et extension tolérées, tout chemin d'évasion refusé), lecture
  d'une note jamais écrite rendant une chaîne vide et non une absence, révision
  intégrale d'une note, `vider()` pour un changement de niveau, bloc
  `pour_segment_frais()` annonçant les notes vides plutôt que de les omettre, et
  surface d'outil `note_read` / `note_write` avec leurs schémas — le domaine lève,
  la surface convertit en texte rendu au modèle (§H7.4). Preuves : 20 tests
  unitaires et 6 d'intégration, dont la promesse centrale vérifiée sur la chaîne
  réelle : après continuation le contenu noté réapparaît et l'ancienne observation a
  bien disparu. Campagne : **217 tests**, lint, format, mypy strict (46 fichiers).
- Deux défauts corrigés au passage : `H6.2` renvoyait à un chapitre `H7.5` inexistant
  (H7 s'arrête à H7.4), et `Workspace.metrique` acceptait qu'un champ de métrique
  remplisse son horodatage par accident.

## Lot D — Outils et boucle

## U12 — Registre d'outils et dispatch `[x]`

`@spec` H7. Déclaration (nom, description, schéma), rendu vers `tools` API, routage
des `tool_calls`, messages `role: tool` append-only, erreurs d'outil renvoyées au
modèle, garde `AVO_TOOL_STEPS_MAX`.

- Preuves : unitaires (dispatch, arguments invalides → erreur textuelle, garde) ;
  intégration : scénario llm-replay à tool_calls multiples, transcript conforme.
- **Livré et intégralement vérifié le 2026-08-28.** `avo.tools.registre` :
  déclaration (nom, description, schéma, fonction, étiquettes), `schemas()` filtrant
  par étiquette pour n'exposer les outils d'action qu'à l'état où agir est permis,
  routage rendant **tout** incident au modèle sous forme de texte diagnostiquable
  (nom inconnu avec la liste des outils, argument obligatoire absent, type
  incorrect, énumération non respectée, argument inconnu, arguments JSON invalides,
  fonction qui lève), validation minimale sans dépendance, exécution séquentielle
  produisant des messages `role: tool` append-only, et garde `AVO_TOOL_STEPS_MAX`
  cumulable entre lots qui clôt le tour par un message explicite.
  Preuves : 23 tests unitaires et 5 d'intégration, ces derniers routant **l'appel
  d'outil réellement demandé par le modèle** jusqu'à un vrai outil de notes.
  Campagne : **245 tests**, lint, format, mypy strict (49 fichiers).
- Défaut corrigé : `AVO_TOOL_STEPS_MAX`, nommée par H7.2, était absente du tableau
  des variables H3.1 et de la configuration. Ajoutée aux trois endroits.

## U13 — Boucle agent P→I→E→B `[x]`

`@spec` H8, H12. Machine d'états événementielle, prompts par phase versionnés
(prédiction avant action, bilan après — contrat A5.1), exposition conditionnelle des
outils d'action, bornes d'actions, `think:false` par défaut (H12).

- Preuves : unitaires des transitions (événements scriptés : action jouée, niveau
  complété, game over, contradiction) ; intégration : boucle complète contre
  llm-replay scripté sur un environnement factice en mémoire (sans ARC), bornes
  respectées, transcript append-only préservé.
- **Livré et intégralement vérifié le 2026-08-28.** `avo.loop.etats` (table de
  transitions close, `TransitionInterdite` nommant les événements admis),
  `avo.loop.prompts` (versionnés, courts, **sans aucune règle de jeu** — vérifié par
  un test qui cherche une liste de termes interdits), `avo.loop.boucle`
  (contrat `Environnement` minimal, outils filtrés par phase, action jouée **par
  l'outil**, bornes par niveau et par jeu). Preuves : 18 tests unitaires (94
  sous-tests) et 8 d'intégration faisant tourner la boucle **en HTTP réel** contre
  le rejeu, sur un environnement factice. Campagne : **271 tests**, lint, format,
  mypy strict (54 fichiers).
- Défaut de conception corrigé par la preuve : la boucle appelait l'environnement
  directement, court-circuitant le registre — l'outil d'action n'était jamais
  exécuté alors que §H8.1 exige d'agir « via l'outil d'action ». L'action passe
  désormais par le registre, et l'environnement conserve l'issue que la boucle relit.
- Défaut corrigé : `AVO_ACTIONS_MAX`, nommée par H8.3, était absente de la
  configuration ; H8.3 décrivait par ailleurs une borne « par niveau et par jeu »
  sans les distinguer. Deux variables désormais, documentées aux trois endroits.

## U14 — Lignée et fonction de score `[x]`

`@spec` H9. Dépôt git jetable sous `runs/<id>/lineage/`, politique « correct ∧ ≥
meilleur », `Scorer` branchable (scorer de test + scorer ARC H9.2), score dans le
message de commit.

- Preuves : unitaires (politique de commit : amélioration committée, régression
  refusée, égalité committée ; isolation — le `.git` de lignée n'est pas celui du
  projet, test qui le vérifie par chemin) ; intégration : trois progressions
  simulées → trois commits de lignée avec scores exacts.
- **Livré et intégralement vérifié le 2026-08-28.** `avo.lineage` : dépôt git jetable
  par run, **`--git-dir` et `--work-tree` explicites** pour que git ne remonte jamais
  l'arborescence, garde `LigneeNonIsolee` vérifiée **avant toute écriture**, politique
  « correct ∧ ≥ meilleur » (amélioration et égalité committées, régression refusée
  sans déplacer le meilleur score), `ScorerARC` lexicographique
  `(niveaux, −actions)` et `ScorerConstant` pour les tests. Preuves : 19 tests
  unitaires et 7 d'intégration, dont un qui compare le `git status` du **dépôt du
  projet** avant et après trois propositions. Campagne : **297 tests**, lint, format,
  mypy strict (57 fichiers).
- `git` devient la seule dépendance système du harnais, ajoutée aux deux images ;
  le principe « zéro dépendance Python d'exécution » reste tenu (H2.1).

## U15 — Superviseur `[x]`

`@spec` H10. Déclencheurs mesurables (stall, cycles, bug-fixing en rafale), appel LLM
séparé, injection `[SUPERVISEUR]` append-only, cooldown, journalisation des motifs.

- Preuves : unitaires des détecteurs sur trajectoires synthétiques (positifs ET
  négatifs) ; intégration : scénario llm-replay en stagnation → une intervention,
  cooldown respecté, motif dans `metrics.jsonl`.
- **Livré et intégralement vérifié le 2026-08-28.** `avo.supervisor` : trois
  détecteurs **mesurés, jamais interprétés** — stagnation (actions sans complétion
  **ni** entrée de lignée), cycle improductif (action répétée **et** frame inchangée
  sur une fenêtre), rafale de Bug-Fixing — puis intervention par **appel LLM séparé
  sur contexte propre**, injectée en append dans l'historique de l'acteur sous la
  balise `[SUPERVISEUR]`, avec cooldown et journalisation des motifs.
  Preuves : 23 tests unitaires (positifs **et** négatifs pour chaque détecteur : une
  action répétée aux effets différents ne déclenche pas, des actions variées sur
  frame figée non plus) et 4 d'intégration passant par le vrai client et le vrai
  rejeu HTTP. Campagne : **324 tests**, lint, format, mypy strict (60 fichiers).
- Variables `AVO_SUP_STALL_ACTIONS` et `AVO_SUP_COOLDOWN`, nommées par H10 mais
  absentes de la configuration et du tableau H3.1, ajoutées aux trois endroits.

## Lot E — ARC-AGI-3

## U16 — Serveur de rejeu `arc-replay` et jeu `cible` `[x]`

`@spec` A3 (+ A1 pour le contrat). Serveur stdlib au contrat A1.3/A2.1, moteur du jeu
`cible` (A3.2 : transitions, bordures, 3 clics → game over, RESET, baselines en forme
fermée, frame transitoire), mode épisodes (A3.3), intégration compose + healthcheck,
`make seed` (partie arc).

- Preuves : unitaires du moteur (déplacements, bordure, clics, game over, RESET,
  baseline par niveau) ; intégration HTTP réelle (partie gagnée à la main par
  requêtes, protocole A1.2 respecté action par action).
- **Livré et intégralement vérifié le 2026-08-28.** `mocks/arc_replay` : moteur du
  jeu `cible` en forme fermée (baselines `[39, 19, 18]` pour trois niveaux, calculées
  et non mesurées), serveur stdlib au contrat A1.3/A1.4, mode épisodes avec déviation
  explicite, service compose sur 8765 avec healthcheck, `make seed` (partie arc), et
  fumée de pile étendue. Preuves : 21 tests unitaires (10 sous-tests) et 14
  d'intégration HTTP, dont **une partie gagnée à la main par requêtes** dépensant
  exactement la somme des baselines. Campagne : **359 tests**, lint, format, mypy
  strict (66 fichiers).
- Le format de fil a été **mesuré** par la sonde U22 (2026-08-31) et le serveur de
  rejeu corrigé avec le client dans le même changement (A1.4).

## U17 — Client API ARC `[x]`

`@spec` A2 (+ A1.3–A1.5). `ArcClient` typé, `FrameResult`, historique typé A2.2
persisté, garde anti-publication A2.3, transport H4.5/H4.6.

- Preuves : unitaires (typage des frames, étiquetage, garde : hôte non-replay en
  mode replay → erreur) ; intégration contre arc-replay : partie complète, RESET,
  game over, épisode dévié → erreur explicite.
- **Livré et intégralement vérifié le 2026-08-28.** `avo.arc.client` : `FrameResult`
  typé, étiquetage des frames selon leur rôle réel (transitoire, décision, init de
  reset, init de niveau, terminal gagnant ou perdant), historique rattachant chaque
  action à la frame de décision d'où elle vient et persisté par niveau sous
  `runs/<id>/frames/`, erreurs typées, et **garde anti-publication structurelle**.
  Preuves : 22 tests unitaires et 11 d'intégration, dont **une partie complète menée
  par le client contre le serveur de U16** — la première rencontre des deux côtés du
  contrat de fil. Campagne : **393 tests**, lint, format, mypy strict (70 fichiers).
- Politique de transport **extraite dans `avo.transport`** et partagée avec le client
  d'inférence : A2.1 exige « les mêmes règles que H4.5/H4.6 », et deux
  implémentations parallèles auraient fini par diverger sans que rien ne le signale.
- `ARC_BASE_URL` pointe désormais la pile locale en mode rejeu, comme l'endpoint
  d'inférence (H3.4) : le mode ne peut plus atteindre un service qui publierait.

## U18 — Rendu texte, inspection, mémoire de frames `[x]`

`@spec` A4. Rendu canonique 64×64 + ligne d'état, coordonnées (row,col) 0-basées,
mémoire de frames sans perte, `inspect`, `read_pixels`, `diff`.

- Preuves : unitaires à sorties attendues exactes sur fixtures (rendu, découpes avec
  marges d'index, diff borné) ; propriété : rendu ∘ parsing = identité sur toute
  grille fixture.
- **Livré et intégralement vérifié le 2026-08-28.** `avo.arc.rendu` (rendu canonique
  64×64, ligne d'état, analyse inverse) et `avo.arc.memoire` (mémoire **sans perte**
  conservant décision et transitoire, `inspect` avec marges d'index, `read_pixels`,
  `diff` borné, et leurs schémas d'outil annonçant qu'ils sont **gratuits au score**).
  Preuves : 35 tests unitaires (6 sous-tests) — dont la propriété aller-retour et un
  test vérifiant qu'**aucune interprétation** ne se glisse dans le rendu — et 7
  d'intégration sur les frames que le serveur envoie réellement, où le `diff` voit
  les **deux** cellules que déplace le curseur. Campagne : **435 tests**, lint,
  format, mypy strict (74 fichiers).

## U19 — Interface de tâche direct-interaction `[x]`

`@spec` A5 (+ A1.2). Prompt de tâche minimal calqué VISTA (aucune règle de jeu nulle
part), outils `action1..6`/`reset` filtrés par la frame, comptage officiel + 
réconciliation A5.3, branchement complet sur la boucle U13 et le scorer U14.

- Preuves : unitaires (filtrage des actions déclarées, validation (row,col),
  comptage RESET conforme A1.2) ; intégration : l'agent (llm-replay scripté) joue des
  actions sur arc-replay via l'interface, l'historique typé et les compteurs sont
  exacts ; revue explicite « zéro indice de jeu » consignée.
- Fait : `avo.arc.interface` (`InterfaceArc`), `RegistreOutils.synchroniser` pour que
  le filtrage par frame atteigne la surface d'outils du modèle, `Workspace.frames`.
  Preuves : `tests/unit/test_interface_arc.py`, `tests/unit/test_registre_outils.py`
  (synchronisation d'un groupe), `tests/integration/test_interface_sur_arc_replay.py`
  (partie parfaite comptée à la baseline, perte réduisant les commandes offertes,
  niveau complété alimentant `ScorerARC`). Revue « zéro indice de jeu » : consignée
  dans `docs/JOURNAL.md` (2026-08-28, session n° 17) et rendue exécutable — le
  balayage porte sur les constantes de tous les modules dont un texte atteint le
  modèle, et sur les corps de requête réellement émis pendant un run.

## U20 — RHAE `[x]`

`@spec` A6. Implémentation de la définition Tycho §3.1, baselines depuis
`/api/games` (live) ou `cible` (replay).

- Preuves : unitaires — tous les vecteurs A6.3, valeurs exactes en forme fermée.
- Contrat d'implémentation écrit et committé avant le code (A6.4) : module pur
  `avo.arc.rhae`, refus explicites, et l'attribution des actions aux niveaux tranchée
  — une entrée d'historique compte pour le niveau **depuis lequel** elle a été jouée.
- Fait : `avo.arc.rhae` (`efficacite_niveau`, `rhae_jeu`, `rhae_global`,
  `niveaux_joues`, `RhaeInvalide`). Preuves : `tests/unit/test_rhae.py` (31 tests —
  les six vecteurs A6.3 avec leurs valeurs calculées à la main, la pondération
  distinguée d'une moyenne simple, tous les refus) et
  `tests/integration/test_rhae_sur_partie_reelle.py` (4 tests en HTTP réel : partie
  parfaite à 100.00 avec baselines venues de `/api/games`, total d'actions égal au
  comptage indépendant de l'interface, partie perdue-relancée-gagnée à 43 actions).
  Campagne complète verte le 2026-08-28 : 511 tests, mypy strict sur 80 fichiers.

## U21 — E2E : partie complète sur rejeu local `[x]`

`@spec` A8.3 (+ H13.2). Scénarios E2E par la CLI réelle sur pile compose : victoire
3 niveaux avec RHAE exact attendu, et scénario échec (game over → RESET → victoire) ;
artefacts (report, lignée, métriques) vérifiés ; reprise `resume` couverte.

- Preuves : `make test-e2e` vert avec les deux scénarios ; vérification opérateur
  MASTER_PLAN §5 exécutée et consignée.
- Contrat d'implémentation écrit et committé avant le code (A8.5) : cassettes de
  scénario seedées et committées, environnement épinglé (discriminant
  `AVO_NUM_PREDICT`), `test-e2e` par le réseau de l'hôte, valeurs attendues en
  forme fermée, reprise par la CLI réelle.
- **Livré et intégralement vérifié le 2026-08-30.** `tests/e2e/scenarios.py`
  (décor partagé, suites d'actions rejouant `chemin_optimal()`),
  `tests/e2e/generer_cassettes.py` (capture en deux passes, auto-contrôle du
  scénario et double génération comparée), cassettes seedées committées
  (`e2e_victoire.jsonl` 316 échanges, `e2e_echec.jsonl` 321), Makefile
  (`seed-e2e`, `test-e2e` par le réseau de l'hôte, aide remise au réel).
  Preuves : `make seed-e2e` (déterminisme vérifié) ; `make test-e2e` vert —
  victoire par sous-processus `python -m avo` réel (3/3 niveaux, 76 actions,
  RHAE **100.00** exact, rapport A7.3, frames par niveau, lignée à 3 commits
  `[n, −actions]`, 76 métriques d'action, reprise sans nouvel appel au modèle),
  échec → RESET → victoire par `cli.main` (game_over 1, niveaux [43, 19, 18],
  RHAE égal à la forme fermée min((100·(39/43)²+500)/6, 100) ≈ 97.04).
  Vérification opérateur MASTER_PLAN §5 exécutée : campagne réelle par la CLI
  dans le terminal, artefacts conservés et relus (`runs/e2e-operateur/` :
  rapport lu en entier, lignée `git log` v1→v3, arborescence) — consignée au
  journal. Un défaut étranger constaté et consigné au registre — la boucle ne
  s'arrêtait pas sur l'état terminal du jeu — corrigé le 2026-08-31 (§H8.3,
  préalable de U24).

## U22 — Sonde de contrat API officielle `[x]` **[LIVE]**

`@spec` A1.4, A2, A3.3. Un scorecard explicitement étiqueté sonde, RESET + quelques
actions sur un jeu court, capture de l'épisode réel expurgé → fixture A3.3,
confirmation/correction du format de fil (coordonnées A4.2 comprises) dans le client
ET arc-replay, journal détaillé. Publie un scorecard (accord du responsable du
2026-08-27 pour l'usage de l'API ; périmètre minimal).

- Preuves : épisode réel rejoué vert par `make test-int` ; écarts constatés corrigés
  et testés ; scorecard référencé au journal.
- **Livré et intégralement vérifié le 2026-08-31** (routine planifiée, autorisation
  du 2026-08-30). Sonde `scripts/sonde_arc.py` exécutée contre l'API officielle :
  scorecard `7528ca63-3eff-4866-97c3-8c4a6ded0e63` (étiquettes `probe`,
  `sonde-u22`), RESET + ACTION6 sur un jeu réel, fermé proprement ; capture
  expurgée committée (`tests/fixtures/arc/episodes/sonde_u22_brut.json` +
  `sonde_u22.jsonl`), recoupée avec l'OpenAPI publiée (`arc3v1.yaml`). Écarts
  mesurés et corrigés des deux côtés dans le même changement (A1.4 réécrit en
  contrat mesuré) : `frame` au singulier, `levels_completed`/`win_levels` sans
  niveau courant ni compteur par frame, `available_actions` en entiers (RESET
  jamais déclaré), `game_id` requis par action, `card_id` au RESET seul, `x`/`y`
  pour ACTION6 (`row`/`col` → 500 mesuré), cookies d'affinité `AWSALB*`, jeux
  listés non servis (refus nommé), `GET /api/scorecard/<id>` non fiable.
  Preuves : `tests/integration/test_episode_reel_sonde.py` (épisode réel rejoué
  vert par le client via `make test-int`), corps de requêtes vérifiés contre
  l'enregistré (déviation d'épisode étendue au corps), campagne complète verte
  (473 unitaires, 138 intégration, 4 E2E, mypy strict), cassettes E2E régénérées.

## Lot F — Campagne

## U23 — Runner de campagne et rapport `[x]`

`@spec` A7 (+ H13.2, H8.4). `run-arc` multi-jeux, plafonds obligatoires en live, garde
d'accord A7.2, reprise sans rejouer les jeux terminés, `report.md` complet A7.3.

- Preuves : unitaires (config, plafonds, garde : live sans drapeau → refus) ;
  intégration/E2E : mini-campagne replay sur `cible`, rapport conforme, reprise
  après interruption simulée.
- **Trois branchements manquants sont dans le périmètre**, parce que A7.3 exige que le
  rapport porte les coûts et les événements : rien n'émettait de métrique, le
  superviseur n'était appelé nulle part, et la boucle n'appelait jamais la
  continuation. Sans eux le rapport annoncerait structurellement zéro sur des lignes
  qu'il est censé mesurer. Contrat écrit en H8.4 (mesuré le 2026-08-28).
- Contrat d'implémentation écrit et committé avant le code (A7.4) : surface CLI,
  cohabitation des budgets de campagne avec H8.3, reprise de granularité **jeu** et son
  motif, structures et refus explicites.
- Fait : les quatre branchements de H8.4 sur `avo.loop.boucle` (continuation
  préventive et réactive, supervision, métriques, lignée), `avo.arc.campagne`
  (plafonds, garde d'accord, état de reprise, un client ARC et une lignée par jeu),
  `avo.arc.rapport` (sept sections A7.3), et les sous-commandes `run-arc` et `resume`.
  Cibles `make run-arc` / `make resume` corrigées : elles partagent le réseau de
  l'hôte, sans quoi elles ne joignaient pas la pile.
  Preuves : `tests/unit/test_campagne.py` (16), `tests/unit/test_rapport.py` (15),
  `tests/integration/test_campagne_sur_rejeu.py` (8, dont deux passant par `main()`).
  Vérification opérateur MASTER_PLAN §5 exécutée : campagne lancée par la CLI réelle,
  rapport lu, arborescence du run observée, et les trois refus vus au terminal.
  Campagne complète verte le 2026-08-28 : 550 tests, mypy strict sur 85 fichiers.

## U24 — Campagne pilote `[x]` **[LIVE]**

`@spec` A7. Périmètre serré (1–2 jeux courts, plafonds
stricts) consigné au journal avant lancement, endpoint réel + API réelle, scorecard
fermé, rapport committé sous `docs/rapports/`, enseignements (débits réels, coûts,
comportement du modèle) au journal.

- Preuves : rapport et scorecard référencés ; réconciliation compteurs locale/API
  exacte ; limites énoncées.
- Fait le 2026-09-01, quatrième tentative (`pilote-u24d`, autorisation du
  responsable du 2026-08-30 pour la session planifiée — point tranché : la
  mention « en session interactive » visait l'accord du responsable, donné) :
  jeu `cd82-fb555c5d` joué jusqu'au plafond de temps (1 200 s consignées avant
  lancement), scorecard `3b34284d…` fermé, réconciliation locale/API EXACTE
  (6 = 6, aucune divergence), rapport committé `docs/rapports/pilote-u24d.md`.
  Enseignements au journal : fenêtre courte 98 304 → 2 continuations, prompt max
  73 180 (zone de casse jamais approchée) ; retries patients → zéro `500` fatal ;
  débits réels 28 appels / 1,1 M tokens de prompt / 6 actions en 20 min.
  Les pilotes a–c (avortés) ont produit les correctifs généraux : pot de cookies
  partagé, refus nommé, échec d'inférence nommé, coûts depuis les métriques,
  retries patients — tous committés avec leurs preuves.
- Préalable livré le 2026-08-31 : l'arrêt de la boucle sur l'état terminal du jeu
  (§H8.3, §A5.4) — plus aucun appel d'inférence après la victoire, motif d'arrêt
  « victoire » dans le rapport (défaut du registre du 2026-08-30, corrigé et
  prouvé : unitaires, intégration, E2E régénérés).

## U25 — Campagne étendue et rapport final `[ ]` **[LIVE]**

`@spec` A7. Périmètre arrêté par le responsable (2026-09-01, session interactive),
exécution par tranches reprenables, rapport final comparatif aux références (A7.3)
committé, CHANGELOG et README mis à jour.

- **Périmètre arrêté (2026-09-01)** : tous les jeux que `/api/games` déclare ;
  plafonds par jeu : 80 actions/niveau, 300 actions/jeu, 1 200 s/jeu,
  1 500 000 tokens/jeu, 400 tours (ceux du pilote U24d) ; mode de contexte
  `state` (décision U28) ; budget global ILLIMITÉ tant que le modèle est
  `qwen3.6:35b` et que l'inférence passe par le gateway LLM du responsable
  (`CLAUDE_PROJECT.md`, « Budget d'inférence ») — toute autre configuration
  rouvre l'arbitrage de dépense. Exécution par tranches reprenables (A7,
  granularité jeu) au fil des sessions planifiées, dans le cadre de la mission
  permanente U31.
- **Déclencheur (décision du responsable, 2026-09-01, journal suite 11)** : la
  campagne ne se (re)joue que lorsque le harnais, affiné sur les bancs U29,
  atteint des résultats intéressants — scores comparables aux références
  publiées des modèles de taille similaire sur les bancs publics (consignées par
  la spécification U29), OU score qui a cessé de progresser (par défaut,
  révisable : trois itérations d'amélioration successives sans gain sur le banc
  concerné). La session qui constate le déclencheur le consigne au journal avec
  ses mesures, puis ouvre la campagne.
- Preuves : rapport final, scorecards, coûts mesurés ; écarts au périmètre nommés.

## Lot G — Contexte à état structuré (SKILL.state)

Source : `knowledge/arxiv-2608.26263-skill-state-long-horizon-agent-skills.md` (ajoutée
le 2026-08-30 sur fourniture du responsable). Le papier remplace l'historique
append-only par un état d'exécution structuré mutable : prompt de pas `(P, Σₜ, Oₜ)`,
raisonnement jeté après projection dans un patch d'état JSON validé, empreinte de
prompt O(1). Il démontre, à budget de tokens égal, que l'état structuré bat
troncature, résumé et compression (0,94 contre 0,18–0,52), une récupération immédiate
après dérive externe, et donne la taxonomie d'erreurs des modèles open-weight qui
impose la validation stricte des patchs. **Tension assumée avec H5** : le transcript
append-only du harnais a été choisi sur la contrainte mesurée du cache de préfixe
(préremplissage dominant, journal du 2026-08-27 suite 2) ; le mode état borne le
prompt mais reprémplit `(P, Σₜ, Oₜ)` à chaque tour. Le lot livre donc le mode en
**alternative configurable, jamais en remplacement**, et le départage par la mesure.

## U26 — Spécification H15 et runtime d'état structuré `[x]`

`@spec` H15 — chapitre à écrire par cette unité et à committer **avant le code**
(précédent des contrats A6.4/A7.4). H15 spécifie : le contrat d'exécution à état
structuré adapté de SKILL.state §3 — sortie de pas `(Rₜ, ΔΣₜ, aₜ)` avec bloc JSON
`{"state_patch": …, "action": …}` ; fusion `⊕` à sémantique de suppression par
null ; **schéma possédé et validé par le runtime, jamais par le modèle** ;
rollback-retry borné sur patch invalide (le patch refusé n'atteint jamais Σ) ;
persistance de Σ dans le workspace et reprise ; schéma ARC v1 de Σ (position, essai,
hypothèses testées, objets identifiés — champs exacts fixés par H15) ; articulation
avec H5 (mode exclusif par segment), H6.2 (les notes restent la mémoire durable
trans-niveaux, Σ est l'état opérationnel du niveau), H10 (les détecteurs du
superviseur lisent aussi les retries de patch), H12 (raisonnement jeté après
projection) ; et la limite « statistique suffisante » de SKILL.state §7, qui motive
de conserver l'archivage sans perte des frames (A4) inchangé. Puis livrer
`avo.context.etat` : état typé, application de patch, validation nommant le champ
fautif, erreurs typées, compteur de retries, sérialisation.

- Preuves : unitaires nominal/limites/erreurs couvrant la taxonomie §5.7 du papier —
  une clé existante absente du patch **survit** (fusion, pas remplacement), une
  incohérence de type/structure est refusée en nommant le champ, un JSON malformé
  déclenche le retry borné puis une erreur explicite ; propriété : `Σ ⊕ ΔΣ` ne mute
  jamais son entrée ; sérialisation aller-retour à l'identique.
- **Livré et intégralement vérifié le 2026-08-30.** §H15 écrit et committé avant le
  code (commit dédié). `avo.context.etat` : `Etat` (frozen, schéma ARC v1 à quatre
  champs toujours présents — `position`/`essai`/`hypotheses`/`objets`, `null` = reset
  au défaut, jamais une suppression de clé), `fusionner` (patch validé champ par
  champ, jamais appliqué partiellement), `decoder_pas` (bloc ```` ```json ```` à
  exactement `state_patch`/`action`, annexe A.4 du papier), `appliquer` (décodage +
  fusion), `CompteurRetries` (budget borné `RETRIES_MAX = 3`, `RetriesEpuises` sur
  dépassement), `vers_json`/`depuis_json` (aller-retour). Trois erreurs typées
  (`EtatInvalide`, `PatchMalforme`, `RetriesEpuises`), aucune absorbée en silence.
  Preuves : `tests/unit/test_etat.py`, 31 tests couvrant nommément les trois classes
  de la taxonomie §5.7 (écrasement/omission 68 %, type/structure 20 %, JSON malformé
  12 %), la non-mutation de l'entrée, et l'aller-retour de sérialisation ; module pur
  sans surface d'intégration ni E2E propres (aucune E/S). `make check` complet
  rejoué en fin de session, vert : lint, `ruff format`, mypy strict sur 91 fichiers,
  **458 tests unitaires** (dont les 31 de cette unité), **123 d'intégration**, **2
  E2E** — aucune régression. `make build` (image de production) vert. La persistance de Σ
  *dans le workspace du run* (`runs/<run_id>/state/etat.json`) et sa reprise
  (§H15.5) ne sont pas câblées par cette unité : ce module reste pur (aucune E/S) et
  fournit seulement les primitives ; le câblage dans la boucle et le workspace est le
  périmètre de U27 (« branchement dans la boucle »), seule unité qui consomme
  réellement un Σ persisté.

## U27 — Mode d'exécution `state` de la boucle et A/B sur rejeu `[x]`

`@spec` H15 (+ H15.8, H8.4, H3.1). Variable `AVO_CONTEXT_MODE` ∈ {`transcript`,
`state`}, défaut `transcript` — **aucun comportement existant ne change**, les
preuves U13/U23 restent valides telles quelles. En mode `state` : un pas = un tour
entier (§H15.8, précision d'implémentation écrite et committée avant le code) ; le
prompt de chaque tour est composé à neuf de `(P, Σₜ, Oₜ)` + notes, sans historique
accumulé ; le patch validé est appliqué avant l'action, dont le nom et les
paramètres sont résolus génériquement depuis le schéma de l'outil (jamais codés en
dur) ; la continuation H5.3–H5.4 est sans objet (un `413` y est compté puis fatal,
faute d'historique à raccourcir) ; métriques par tour ajoutées : taille de prompt,
retries de patch.

- **Livré et vérifié le 2026-08-30 :** `AVO_CONTEXT_MODE` dans `avo.config` ;
  `BoucleAgent._jouer_tour_etat` (un appel LLM par tour, rollback-retry borné sur
  `PatchMalforme`/`EtatInvalide`, résolution générique de l'action, événements
  toujours décidés par l'environnement) ; persistance/reprise de Σ dans le
  workspace (`Workspace.ecrire_etat`/`lire_etat`, `runs/<run_id>/state/etat.json`).
  Preuves : unitaires (`AVO_CONTEXT_MODE`, persistance de Σ) et 9 tests
  d'intégration contre le vrai rejoueur HTTP (§H4.7) — patch valide, clé absente du
  patch qui survit (§H15.2), rollback-retry puis succès, budget de retries épuisé
  qui lève une erreur fatale (§H15.4), action inconnue qui ne joue rien et se
  signale au tour suivant, événement porté par l'environnement qui prime,
  persistance ET reprise de Σ depuis un workspace existant. `make check`
  (lint, typecheck, test-unit, test-int) vert, zéro régression sur les 458 preuves
  préexistantes du mode `transcript`.
- **A/B sur rejeu, livré et vérifié le 2026-08-30 (session planifiée).**
  `ResultatJeu.retries_patch` (défaut `0`, aller-retour JSON, alimenté par
  `bilan.retries_patch`) pour que le rapport comparatif dispose du compte de
  retries par jeu. Cassette de scénario `state` dédiée
  (`tests/fixtures/llm/cassettes/e2e_etat_victoire.jsonl`, 120 échanges, générée
  par `tests/e2e/generer_cassette_etat.py` — même principe de capture en deux
  passes que le générateur `transcript`, régénération identique octet à octet
  vérifiée) : chemin parfait du jeu `cible-synthetique` traduit en textes d'action
  du contrat `state` (§H15.8), sur les mêmes plafonds que le scénario `transcript`
  (`--tours-max 120 --actions-max-niveau 100 --actions-max-jeu 200`). Depuis
  l'arrêt sur état terminal (§H8.3, livré le 2026-08-31), la cassette compte
  76 échanges : un appel par action, plus aucun après la victoire.
  `avo.arc.rapport_ab` (fonction pure, même principe que `avo.arc.rapport`) :
  `MesureMode` (RHAE moyen, actions, appels au modèle, tokens cumulés, taille
  moyenne de prompt, retries de patch) et `rapport()` qui compose le markdown
  comparatif. `scripts/generer_rapport_ab.py` rejoue les deux mini-campagnes par
  la CLI réelle (`python -m avo run-arc --mode replay`, sous-processus,
  MASTER_PLAN §5) sur `cible-synthetique`, une par `AVO_CONTEXT_MODE`, et écrit
  `docs/rapports/ab_mode_contexte.md` (`make rapport-ab`, cible Makefile
  documentée). **Garde-fou ajouté après un incident mesuré en session** : la
  première version du script ne fixait pas `OLLAMA_HOST`/`ARC_BASE_URL` dans
  l'environnement du sous-processus, et le `.env` local (réel, présent en session
  planifiée) a été lu en repli par `avo.config` — la première exécution a bien
  interrogé le VRAI endpoint (`qwen3.6:35b`, latences de 20 à 45 s observées dans
  les journaux) avant d'être interrompue. Corrigé en épinglant `OLLAMA_HOST`,
  `ARC_BASE_URL` et un jeton non secret dans l'environnement du sous-processus
  (même principe que `tests/e2e/scenarios.ENV_EPINGLE`, §A8.5) ; aucune donnée
  n'a été écrite dans le dépôt pendant l'incident (répertoire de runs temporaire),
  aucun scorecard ARC n'a été ouvert. Le rapport committé nomme explicitement la
  limite du rejeu sur la « taille moyenne de prompt » (valeur rejouée identique
  par construction du rejoueur HTTP, §H4.7 — le signal `O(1)` par tour se lit sur
  le nombre d'appels, 316 en `transcript` contre 120 en `state`, pas sur la taille
  par appel).
  Preuves : `tests/unit/test_campagne.py` (aller-retour de `retries_patch`),
  `tests/e2e/test_ab_mode_contexte.py` — le rapport committé est rejouable à
  l'octet près depuis la CLI réelle, et nomme les cinq mesures du contrat. `make
  check` (lint, typecheck, test-unit — 467 tests —, test-int — 132 tests —,
  test-e2e — 4 tests) intégralement vert, zéro régression. RHAE 100.00 et 76
  actions identiques dans les deux modes ; `state` : 120 appels contre 316 en
  `transcript` (le mode ne dégrade pas la partie jouée).

## U28 — A/B des deux modes en conditions réelles `[x]` **[LIVE]**

`@spec` H15, A7. En session interactive, après U24 : rejouer le périmètre pilote de
U24 en mode `state` sur l'endpoint réel et l'API réelle (mêmes jeux, mêmes
plafonds), comparer mesures en main : RHAE, actions, tokens prépremplis et générés,
coût, incidents (`413`, retries de patch), effet du cache de préfixe constaté.
Rapport comparatif committé ; recommandation du mode par défaut pour U25 arrêtée
**avec le responsable** sur ces mesures.

- Preuves : rapport committé sous `docs/rapports/` ; réconciliation des compteurs
  locale/API exacte ; recommandation et décision consignées au journal.
- **Mesures livrées le 2026-09-01 (session planifiée)** : run `ab-u28-state`
  (`cd82-fb555c5d`, mêmes plafonds et fenêtre que `pilote-u24d`, gardes actives)
  mené au plafond de temps, scorecard `4cedc4e1…` fermé, réconciliation
  locale/API EXACTE (33 = 33) ; rapport comparatif committé
  (`docs/rapports/ab-u28-state.md`) : 33 actions contre 6 à budget de temps égal,
  prompt borné 8 890–9 223 tokens (O(1) constaté), 0 continuation, 1 retry de
  patch corrigé, ~15× moins de tokens de prompt par action ; recommandation
  consignée (mode `state` par défaut pour U25).
- **Décision rendue et appliquée le 2026-09-01 (session interactive, journal
  suites 9–10)** : le responsable suit la recommandation — `state` est le mode
  par défaut. Bascule livrée : spéc §H15.0/§H15.7 amendées, défaut dans
  `avo.config`, README/DAT/CHANGELOG alignés, preuve du défaut révisée et bancs
  à cassettes `transcript` épinglés sur leur mode. Campagne complète verte
  (lint, mypy strict, 508 unitaires, 145 intégration, 4 E2E, build). Unité
  close.

## U29 — Benchmarks interactifs complémentaires : terrain d'affinage du harnais `[~]`

**Ouverte par le responsable le 2026-09-01** (session interactive, journal
suite 11) : le harnais s'AFFINE sur ces bancs avant de rejouer la campagne ARC
(déclencheur consigné dans U25). Les trois bancs du papier SKILL.state, dans cet
ordre :

- **a) patron SkillExecBench** — banc diagnostique déterministe à générateurs
  seedés (Warehouse : 500 étagères indépendantes, Store/Ship/Move/Wait ;
  Software Repository : graphe branches/commits/PR/CI, CherryPick/Merge/RunTests/
  Rollback), score continu actions correctes / événements, entièrement local et
  rejouable par cassettes — c'est aussi le mètre hors ligne des améliorations
  U31 ;
- **b) InterCode CTF** — 100 défis bash en conteneurs Docker (rétro-ingénierie,
  forensique, crypto, exploitation), pass@1 sur drapeau vérifié ;
- **c) Sierra τ-Bench** — workflows client Retail/Airline, utilisateur simulé
  par un second LLM, bases SQLite outillées, évaluateur officiel sur l'état
  final.

L'unité commence par sa spécification (chapitres S1+, committée avant le code),
qui consigne notamment les scores de référence publiés des modèles open-weight de
taille comparable (source : export SKILL.state), puis se redécoupe en unités d'une
session. Le noyau §H reste agnostique de la tâche : chaque banc n'ajoute qu'un
adaptateur mince (outils + prompt), comme §A pour ARC ; interdiction de
benchmaxing inchangée — aucune adaptation à un défi particulier.

- Preuves : fixées par la spécification à écrire ; rejeu déterministe pour les
  tests (garde A2.3 : aucun appel réseau externe depuis les tests).

**Spécification écrite le 2026-09-01** : `docs/SPEC_BANCS.md` (§S1–§S7), scores
de référence consignés (§S5.4). Le banc a se découpe en unités d'une session
(§S7) :

- **U29a1 `[x]`** — spécification S1+ + environnement Entrepôt :
  `src/avo/bancs/skillexec/{entrepot,generation,score}.py`, preuves unitaires de
  §S6.4 (générateur, transitions, score, bruit). Sans adaptateur ni CLI.
  **Livré et vérifié le 2026-09-01** : 26 unitaires verts
  (`tests/unit/test_banc_entrepot.py`), balayage « mots du banc hors
  `src/avo/bancs/` » vide, campagne complète verte (lint, mypy strict
  103 fichiers, 534 unitaires, 145 intégration, 4 E2E, build). L'intégration et
  l'E2E du banc appartiennent à U29a2 (§S7), qui branche l'adaptateur.
- **U29a2 `[x]`** — adaptateur harnais + CLI `banc` (§S6) : boucle complète en
  rejeu, cassette, intégration + E2E, premier relevé live (3 seeds, horizons 10
  et 25) au journal. **Livré et vérifié le 2026-09-01** :
  `src/avo/bancs/skillexec/adaptateur.py` (contrat `Environnement`, outils
  `action` avec `prediction`, contexte de tâche en message système — §H15.8
  amendé pour que le mode `state` honore le message système du contexte monté),
  sous-commande CLI `banc` générique (dispatch sous `avo.bancs`), 18 unitaires +
  8 unitaires de résolution, intégration en rejeu HTTP réel, cassette E2E
  `e2e_banc_entrepot.jsonl` + scénario CLI réelle, campagne complète verte
  (lint, mypy strict 111 fichiers, 562 unitaires, 148 intégration, 5 E2E,
  build). Relevé live consigné au journal (2026-09-01, suites 14–15) ; il a désigné
  et fait livrer deux corrections génériques : coupure de connexion typée
  `TransportError` (§H4.4) et normalisation de la syntaxe d'appel de fonction
  dans la résolution d'action (§H15.8).
- **U29a3 `[x]`** — environnement Dépôt logiciel (§S4, détail exécutable écrit
  d'abord), preuves unitaires, score §S4.4. **Livré et vérifié le 2026-09-01** :
  détail exécutable de §S4.1–§S4.6 écrit et committé avant le code (cycle des
  demandes, générateur nominal, validité des actions, `merge` cassant sur CI
  rouge, résolution B.1, obligations et divergence) ;
  `src/avo/bancs/skillexec/depot.py` (générateur seedé, transitions
  commit/create_pr/merge/fix_ci/wait, résolution au relevé), 30 unitaires
  (`tests/unit/test_banc_depot.py` : déterminisme, cycle nominal, chaque
  validité/refus, partie parfaite score 1,0 et résolution 1,0, `wait` dû en
  divergence, bruit C.3), balayage « mots du banc hors `src/avo/bancs/` » vide,
  campagne complète verte (lint, mypy strict 112 fichiers, 592 unitaires,
  148 intégration, 5 E2E, build). Le branchement adaptateur+CLI du dépôt
  appartient à U29a4 (§S7, point tranché à la clôture).
- **U29a4 `[~]`** — branchement du Dépôt logiciel à l'adaptateur et à la CLI
  (§S6), puis bruit et récupération d'état en campagne de banc, relevés
  multi-seeds, alimentation du déclencheur U25.
  **Livré et vérifié le 2026-09-01** : adaptateur des deux environnements (base
  commune de boucle, contexte de tâche §S4.2/§S4.5, cinq outils `action`,
  numéro de PR de `merge` en texte à l'erreur nommée), dispatch CLI
  `--env depot`, résolution B.1 au relevé ; 18 unitaires, intégration en rejeu
  HTTP réel (résolution exacte), cassette E2E `e2e_banc_depot.jsonl` + scénario
  CLI réel, campagne complète verte (lint, mypy strict, 610 unitaires,
  149 intégration, 6 E2E, build). Relevés live consignés (journal, suite 18) :
  dépôt h10 seeds 1–3 bruit 0 (0,60 / 0,80 / 0,60), premier point bruit 5 sur
  les deux environnements.
  **Livré et vérifié le 2026-09-02 (suite 19)** : condition 3 « récupération
  d'état » sur les deux environnements — spécification d'abord (§S3.8, §S4.7,
  §S5.5), dérive unique seedée à génération, application réelle au pas porteur,
  alerte non structurée `--- ALERTE EXTERNE ---`, événement forcé testant la
  lecture de l'alerte, mesure `pas_de_recuperation`/`recupere` au relevé, CLI
  `--derive` ; 14 unitaires, intégration en rejeu HTTP (récupération 0),
  cassettes E2E régénérées, campagne complète verte (lint, mypy strict,
  624 unitaires, 151 intégration, 6 E2E, build). Relevés live consignés
  (journal, suite 19) : dérive h10 seeds 1–3 sur les deux environnements, six
  épisodes récupérés en 0–3 pas.
  **Reste à livrer** : campagne de banc systématique — bruit aux niveaux de
  référence (0/5/20/50) et horizons 25+ multi-seeds (3 seeds minimum par point,
  §S5.4) sur les deux environnements, dérive aux horizons 25+, alimentation du
  déclencheur U25 avec ces séries.

## Lot H — La méthode dans la structure

Source : instruction du responsable (2026-08-31, session interactive). Les règles de
méthode qui améliorent un agent quand elles lui sont IMPOSÉES — chercher
l'information avant d'agir, énoncer ce qu'on va faire, prouver avant de conclure,
persister ce qu'on a appris — ne doivent pas vivre seulement dans le prompt du
harnais : le prompt conseille, la structure impose. Le harnais les impose donc comme
GARDES à l'intérieur des phases P→I→E→B existantes — jamais comme de nouvelles
phases : les publications donnent déjà le squelette (AVO : `Vary(Pₜ) = Agent(Pₜ, K,
f)`, la base de connaissances K est une entrée de première classe ; VISTA :
prédiction avant action, changements observés après, GUIDE/WORKING ; SKILL.state :
Σ structuré). Ce lot MÉCANISE ces règles, il n'en invente aucune.

## U30 — Spécification H16 et gardes de méthode dans les phases `[x]`

`@spec` H16 — chapitre écrit et committé avant le code (2026-08-31), gardes
livrées et intégralement prouvées le 2026-09-01. H16 spécifie, générique et sans
indice de jeu :

1. **Garde documentaire, à l'entrée de Planning** : le harnais compose K — le
   contexte de tâche fourni (protocole de la tâche, documentation d'API donnée par
   le responsable) et les notes durables `GUIDE.md` du run — et exige, avant de
   déverrouiller les outils d'action, un artefact « ce que je sais / ce que
   j'ignore / comment je compte le découvrir » (`WORKING.md`, ou champ de Σ en mode
   `state`). C'est le réflexe « aller chercher les specs », mécanisé.
2. **Garde de prédiction** : une action n'est jouable qu'accompagnée de sa
   prédiction (VISTA). Sur le fil officiel, la prédiction part dans le champ
   `reasoning` mesuré en U22 — auditable dans le scorecard.
3. **Garde d'évaluation** : l'environnement tranche (H8.1, inchangé) ; le harnais
   présente prédit-contre-observé et exige la qualification confirmé/réfuté avant
   l'action suivante.
4. **Garde de persistance** : à chaque complétion de niveau, game over ou
   intervention du superviseur, la mise à jour de `GUIDE.md` est exigée avant de
   poursuivre — une connaissance non écrite est une connaissance perdue.

Contraintes : artefacts BORNÉS (le préremplissage domine le coût — H5, journal du
2026-08-27) ; aucune scénarisation du raisonnement (la structure exige des
artefacts, le modèle pense) ; valable dans les deux modes de contexte (H5/H15) ;
zéro indice de jeu (§A5, balayage exécutable inchangé).

- Preuves : unitaires (chaque garde : refus nommé quand l'artefact manque, passage
  quand il est là) ; intégration sur `cible` (partie jouée sous gardes, artefacts
  dans le workspace) ; E2E rejeu ; comparaison avant/après gardes sur `cible`
  (comportement observé du harnais — jamais un jeu officiel particulier).
- **Livré et intégralement vérifié le 2026-09-01.** Les quatre gardes dans
  `avo.loop.boucle` (verrou Planning→Implementation, verdict exigé, portage au
  mode `state` par lignes `PREDICTION:`/`VERDICT:` et champ `hypotheses` de Σ),
  paramètre `prediction` requis sur les outils d'action (`avo.arc.interface`)
  acheminé tronqué vers `reasoning` du fil (`avo.arc.client`), compteur
  d'écritures monotone des notes, `AVO_GARDES`/`AVO_GARDE_RETRIES` (`avo.config`),
  prompts v1.1. Correction liée : une action refusée par un outil ne relit plus
  l'issue précédente (comparaison d'identité dans `_jouer_action`). Preuves :
  17 unitaires boucle + 6 unitaires interface + compteur de notes ; intégration
  sur `cible` sous gardes (partie parfaite 76 actions, RHAE 100.00, WORKING/GUIDE
  présents, zéro événement de garde au nominal) et A/B avant/après gardes (mêmes
  issues, mêmes appels, artefacts en plus) ; cassettes E2E régénérées sous gardes
  (mêmes 228/241/76 échanges) et 4 E2E verts sur pile fraîche ; campagne complète
  verte (lint, mypy strict, 499 unitaires, 142 intégration, 4 E2E, build).
  Les preuves antérieures de la mécanique hors gardes sont épinglées
  `AVO_GARDES=false` (§H16.0.4).

## Lot I — Concours permanent

Source : instructions du responsable (2026-09-01, session interactive, journal
suites 9 et 11). La raison d'être de la boucle planifiée est de RÉUSSIR ARC Prize
avec le harnais — en deux temps : le harnais s'AFFINE d'abord sur les bancs
génériques U29 (jouer, observer, améliorer), puis, quand le déclencheur consigné
dans U25 est atteint (scores comparables aux modèles de taille similaire, ou
plateau), la campagne ARC se joue. L'interdiction de benchmaxing
(`CLAUDE_PROJECT.md`) s'applique sans exception ; le budget d'inférence est
illimité tant que le modèle est `qwen3.6:35b` et que l'inférence passe par le
gateway LLM du responsable.

## U31 — Boucle permanente de concours : jouer, observer, améliorer `[~]` **[LIVE]** (permanente)

`@spec` A7 (campagne), H (harnais général) ; mission et bornes :
`CLAUDE_PROJECT.md` (« Mission permanente », « Budget d'inférence »). Unité
PERMANENTE : elle ne passe jamais à `[x]`, et la boucle planifiée ne s'arrête pas
tant qu'elle est active (MASTER_PLAN §7). Chaque session planifiée, dans cet
ordre :

1. **Jouer** — sur la cible d'évaluation COURANTE :
   - tant que le déclencheur U25 n'est pas atteint, la cible est U29 : construire
     le prochain banc dans l'ordre a → b → c (spécification d'abord), puis faire
     jouer le harnais sur les bancs livrés et relever les scores ;
   - une fois le déclencheur constaté et consigné, la cible est la campagne ARC
     au périmètre U25 (`python -m avo resume <run_id>` ou ouverture), par
     tranches reprenables (A7, granularité jeu).
2. **Observer** : dépouiller les artefacts du run (rapport, scores, RHAE le cas
   échéant, incidents, interventions du superviseur, retries de patch, coûts) et
   consigner les mesures au journal — y compris la progression du score par banc,
   qui alimente le déclencheur U25.
3. **Améliorer ou corriger** : sur ces mesures uniquement, une amélioration
   GÉNÉRIQUE du harnais (boucle, prompts, outils, mémoire, superviseur) ou une
   correction de défaut — spécifiée, codée et prouvée dans la même session ;
   balayage « zéro indice de jeu » (§A5) avant tout commit de code ou de prompt.
   Pas de mesure fraîche qui désigne une amélioration : pas d'amélioration
   inventée.

- Preuves par itération : le run joué et réconcilié (scorecard fermé quand une
  campagne ARC se clôt), l'analyse et les scores consignés au journal, et pour
  toute modification du harnais ses preuves propres plus la campagne complète
  (`make check`).

**Itération du 2026-09-02 (suite 20, session interactive)** — deux améliorations
génériques désignées par la mesure de la suite 19, livrées et prouvées
(`make check` vert, cassettes régénérées) : H15.9 schéma de Σ déclaré par le
domaine (`f6a8619`, `7adb063`) et H15.10 archive des pas du mode `state`
(`cc1d6ac`).

**Itération du 2026-09-02 (suite 21, session planifiée)** — dépouillement des
`pas.jsonl` (le premier objet désigné par la suite 20) et correction générique
livrée : H16.1 révisé — refus de garde = pas blanc atomique (le patch du pas
refusé est annulé avec l'action) et `hypotheses` non vidable en cours de run
(vidage = `EtatInvalide`, protocole 1.3 énonce la règle). Preuves : 642
unitaires, 151 intégration, 6 E2E, cassettes régénérées. A/B live sous schéma
du domaine : toujours sans mesure complète — endpoint instable les deux
sessions (rafales de 500 du pont plus longues que l'échelle de relances,
défaut consigné au registre) ; les prochaines lignes de base live se relèvent
sous le code de la suite 21.
