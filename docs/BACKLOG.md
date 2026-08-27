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

## U7 — Client d'inférence `[ ]`

`@spec` H4.1–H4.5. `LLMClient.chat` sur `/api/chat` (think, options, tools), parsing
`ChatResult`, erreurs typées, retries bornés avec jitter.

- Preuves : unitaires (parsing, classification d'erreurs, politique de retry) ;
  intégration contre `llm-replay` sur **cassettes enregistrées du vrai serveur** :
  nominal, tool_call, 401 fatal, 413 → `ContextOverflow` avec ses champs réels,
  500 → retries puis échec, latence < timeout. `make test-int-live` rejoue les mêmes
  scénarios contre l'endpoint réel pour détecter toute dérive du contrat.

## U8 — Comptabilité, journalisation, workspace de run `[ ]`

`@spec` H4.6, H6.1, H11 ; H4.8. `runlog` (logs JSON sans secret, id de run),
`manifest.json`, `metrics.jsonl`, transcripts JSONL par segment ; `TokenLedger`
(estimé vs réel) ; cible `make smoke-live` (jamais dans check).

- Preuves : unitaires (aucune fuite de secret dans les sorties — test qui greppe la
  clé dans les logs produits ; métriques cumulées correctes) ; intégration : un
  échange complet contre llm-replay produit un workspace conforme H6.1.

## Lot C — Contexte et mémoire

## U9 — Transcript append-only `[ ]`

`@spec` H5.1–H5.2. Structure immuable en tête, hash de préfixe, sérialisation,
estimation calibrée corrigée par `prompt_eval_count`.

- Preuves : unitaires — l'invariant : après N tours simulés, le hash du préfixe
  envoyé au tour k est préfixe de celui du tour k+1 ; toute API qui muterait la tête
  n'existe pas (test de surface du module).

## U10 — Budget et continuation en contexte frais `[ ]`

`@spec` H5.3–H5.4, H3.2. Déclenchement au seuil, état de continuation écrit par
l'agent, nouveau segment (système + continuation + notes + observation), `413` →
continuation immédiate + budget appris, double-413 → erreur fatale explicite.

- Preuves : unitaires (seuils, recalcul du budget) ; intégration contre llm-replay
  avec petit budget forcé : la continuation se produit, le contenu du segment frais
  est exactement celui spécifié, un 413 simulé est absorbé, deux → erreur.

## U11 — Notes persistantes `[ ]`

`@spec` H6.2, H7.3. `GUIDE.md`/`WORKING.md` dans le workspace, outils
`note_read`/`note_write` (limités à ces deux noms), injection en tête de segment
frais.

- Preuves : unitaires (lecture/écriture/refus d'un autre nom) ; intégration :
  après continuation (U10), les notes réapparaissent dans le prompt du segment frais.

## Lot D — Outils et boucle

## U12 — Registre d'outils et dispatch `[ ]`

`@spec` H7. Déclaration (nom, description, schéma), rendu vers `tools` API, routage
des `tool_calls`, messages `role: tool` append-only, erreurs d'outil renvoyées au
modèle, garde `AVO_TOOL_STEPS_MAX`.

- Preuves : unitaires (dispatch, arguments invalides → erreur textuelle, garde) ;
  intégration : scénario llm-replay à tool_calls multiples, transcript conforme.

## U13 — Boucle agent P→I→E→B `[ ]`

`@spec` H8, H12. Machine d'états événementielle, prompts par phase versionnés
(prédiction avant action, bilan après — contrat A5.1), exposition conditionnelle des
outils d'action, bornes d'actions, `think:false` par défaut (H12).

- Preuves : unitaires des transitions (événements scriptés : action jouée, niveau
  complété, game over, contradiction) ; intégration : boucle complète contre
  llm-replay scripté sur un environnement factice en mémoire (sans ARC), bornes
  respectées, transcript append-only préservé.

## U14 — Lignée et fonction de score `[ ]`

`@spec` H9. Dépôt git jetable sous `runs/<id>/lineage/`, politique « correct ∧ ≥
meilleur », `Scorer` branchable (scorer de test + scorer ARC H9.2), score dans le
message de commit.

- Preuves : unitaires (politique de commit : amélioration committée, régression
  refusée, égalité committée ; isolation — le `.git` de lignée n'est pas celui du
  projet, test qui le vérifie par chemin) ; intégration : trois progressions
  simulées → trois commits de lignée avec scores exacts.

## U15 — Superviseur `[ ]`

`@spec` H10. Déclencheurs mesurables (stall, cycles, bug-fixing en rafale), appel LLM
séparé, injection `[SUPERVISEUR]` append-only, cooldown, journalisation des motifs.

- Preuves : unitaires des détecteurs sur trajectoires synthétiques (positifs ET
  négatifs) ; intégration : scénario llm-replay en stagnation → une intervention,
  cooldown respecté, motif dans `metrics.jsonl`.

## Lot E — ARC-AGI-3

## U16 — Serveur de rejeu `arc-replay` et jeu `cible` `[ ]`

`@spec` A3 (+ A1 pour le contrat). Serveur stdlib au contrat A1.3/A2.1, moteur du jeu
`cible` (A3.2 : transitions, bordures, 3 clics → game over, RESET, baselines en forme
fermée, frame transitoire), mode épisodes (A3.3), intégration compose + healthcheck,
`make seed` (partie arc).

- Preuves : unitaires du moteur (déplacements, bordure, clics, game over, RESET,
  baseline par niveau) ; intégration HTTP réelle (partie gagnée à la main par
  requêtes, protocole A1.2 respecté action par action).

## U17 — Client API ARC `[ ]`

`@spec` A2 (+ A1.3–A1.5). `ArcClient` typé, `FrameResult`, historique typé A2.2
persisté, garde anti-publication A2.3, transport H4.5/H4.6.

- Preuves : unitaires (typage des frames, étiquetage, garde : hôte non-replay en
  mode replay → erreur) ; intégration contre arc-replay : partie complète, RESET,
  game over, épisode dévié → erreur explicite.

## U18 — Rendu texte, inspection, mémoire de frames `[ ]`

`@spec` A4. Rendu canonique 64×64 + ligne d'état, coordonnées (row,col) 0-basées,
mémoire de frames sans perte, `inspect`, `read_pixels`, `diff`.

- Preuves : unitaires à sorties attendues exactes sur fixtures (rendu, découpes avec
  marges d'index, diff borné) ; propriété : rendu ∘ parsing = identité sur toute
  grille fixture.

## U19 — Interface de tâche direct-interaction `[ ]`

`@spec` A5 (+ A1.2). Prompt de tâche minimal calqué VISTA (aucune règle de jeu nulle
part), outils `action1..6`/`reset` filtrés par la frame, comptage officiel + 
réconciliation A5.3, branchement complet sur la boucle U13 et le scorer U14.

- Preuves : unitaires (filtrage des actions déclarées, validation (row,col),
  comptage RESET conforme A1.2) ; intégration : l'agent (llm-replay scripté) joue des
  actions sur arc-replay via l'interface, l'historique typé et les compteurs sont
  exacts ; revue explicite « zéro indice de jeu » consignée.

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
