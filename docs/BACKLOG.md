# Backlog

Statuts : `[ ]` non commencé · `[~]` en cours ou insuffisamment vérifié · `[x]` terminé et intégralement vérifié.

Ordre d'exécution et Definition of Done commune : `docs/MASTER_PLAN.md`. Chaque unité
cite ses chapitres de spécification (`docs/SPEC_HARNAIS.md` = H, `docs/SPEC_ARCAGI3.md`
= A) ; ses spécifications sont déjà écrites — une session la prenant code directement.
Les unités marquées **[LIVE]** ne sont jamais prises par le worker planifié
(MASTER_PLAN §3).

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
- Le format de fil est désormais **écrit** en A1.4 et implémenté des deux côtés ; il
  reste à confirmer par la sonde U22, qui corrigera client et rejeu ensemble.

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

## U20 — RHAE `[ ]`

`@spec` A6. Implémentation de la définition Tycho §3.1, baselines depuis
`/api/games` (live) ou `cible` (replay).

- Preuves : unitaires — tous les vecteurs A6.3, valeurs exactes en forme fermée.

## U21 — E2E : partie complète sur rejeu local `[ ]`

`@spec` A8.3 (+ H13.2). Scénarios E2E par la CLI réelle sur pile compose : victoire
3 niveaux avec RHAE exact attendu, et scénario échec (game over → RESET → victoire) ;
artefacts (report, lignée, métriques) vérifiés ; reprise `resume` couverte.

- Preuves : `make test-e2e` vert avec les deux scénarios ; vérification opérateur
  MASTER_PLAN §5 exécutée et consignée.

## U22 — Sonde de contrat API officielle `[ ]` **[LIVE]**

`@spec` A1.4, A2, A3.3. En session interactive : un scorecard explicitement étiqueté
sonde, RESET + quelques actions sur un jeu court, capture de l'épisode réel expurgé
→ fixture A3.3, confirmation/correction du format de fil (coordonnées A4.2 comprises)
dans le client ET arc-replay, journal détaillé. Publie un scorecard (accord du
responsable du 2026-08-27 pour l'usage de l'API ; périmètre minimal).

- Preuves : épisode réel rejoué vert par `make test-int` ; écarts constatés corrigés
  et testés ; scorecard référencé au journal.

## Lot F — Campagne

## U23 — Runner de campagne et rapport `[ ]`

`@spec` A7 (+ H13.2). `run-arc` multi-jeux, plafonds obligatoires en live, garde
d'accord A7.2, reprise sans rejouer les jeux terminés, `report.md` complet A7.3.

- Preuves : unitaires (config, plafonds, garde : live sans drapeau → refus) ;
  intégration/E2E : mini-campagne replay sur `cible`, rapport conforme, reprise
  après interruption simulée.

## U24 — Campagne pilote `[ ]` **[LIVE]**

`@spec` A7. En session interactive : périmètre serré (1–2 jeux courts, plafonds
stricts) consigné au journal avant lancement, endpoint réel + API réelle, scorecard
fermé, rapport committé sous `docs/rapports/`, enseignements (débits réels, coûts,
comportement du modèle) au journal.

- Preuves : rapport et scorecard référencés ; réconciliation compteurs locale/API
  exacte ; limites énoncées.

## U25 — Campagne étendue et rapport final `[ ]` **[LIVE]**

`@spec` A7. Périmètre arrêté avec le responsable au vu de U24 (jeux, plafonds,
budget temps/coût), exécution par tranches reprenables, rapport final comparatif aux
références (A7.3) committé, CHANGELOG et README mis à jour.

- Preuves : rapport final, scorecards, coûts mesurés ; écarts au périmètre nommés.
