# Spécification du harnais AVO — noyau agent

Référence stable pour les commentaires `@spec` : `docs/SPEC_HARNAIS.md §Hn`.
Unités de backlog couvertes : U3–U15, U26–U27, U30 (voir `docs/BACKLOG.md`).
Sources faisant foi : exports de `knowledge/` (papier AVO arXiv:2603.24517, billet NVIDIA
2026-08-21, page VISTA, papier Tycho arXiv:2607.28287, papier SKILL.state
arXiv:2608.26263 pour §H15). En cas d'écart entre cette spécification et une source, la
source fait foi et l'écart se consigne dans `docs/INCONSISTENCY_REPORT.md`.

Chaque exigence porte un identifiant stable `Hn.m` cité par les `@spec` du code.

---

## H1. Objet, fidélité et écarts assumés

**H1.1 — Objet.** Implémenter en open source l'architecture d'agent AVO : un agent LLM
autonome longue-durée avec boucle Planning → Implementation → Evaluation → Bug-Fixing,
mémoire persistante, lignée de solutions scorées et superviseur anti-stagnation
(papier AVO §3, fig. 1 et 2), piloté par le LLM servi par l'endpoint fourni, et
l'évaluer sur ARC-AGI-3 (ensemble public) en mode direct-interaction texte
(billet NVIDIA : grilles texte 64×64 exactes, actions sans description des règles).

**H1.2 — Ce que les sources n'établissent pas.** NVIDIA n'a publié ni le code du harnais
ni les détails de l'instanciation ARC (prompts, mapping lignée/score sur le jeu).
Toute décision comblant ces lacunes est marquée « décision » dans ce document, avec son
motif. Le résultat est « une implémentation fidèle aux mécanismes publiés », jamais
« le harnais NVIDIA ».

**H1.3 — Contraintes mesurées structurantes** (mesures du 2026-08-27,
`docs/JOURNAL.md`) :
1. le préremplissage domine le coût (~493 tok/s mesurés) → l'historique envoyé au
   modèle est strictement append-only (H5) ;
2. le plafond de contexte est par clé API, avec marge de 15 % côté proxy → budget
   utile ≈ plafond/1,15, `HTTP 413` traité en cas nominal (H5.4) ;
3. le modèle raisonne avant de répondre et le raisonnement consomme `num_predict` →
   politique de raisonnement explicite (H12).

## H2. Stack, arborescence, commandes

**H2.1 — Décision : Python ≥ 3.11, zéro dépendance d'exécution.** Le harnais n'utilise
que la bibliothèque standard (`urllib`, `http.server`, `json`, `subprocess`, `hashlib`,
`logging`). Motif : CLAUDE.md §19 (une fonction native suffit — HTTP/JSON sans
streaming), surface d'audit minimale, image Docker triviale.

**Une seule dépendance système** : `git`, employé par la lignée de solutions (§H9.3) qui crée un dépôt jetable par run. Ce n'est pas une dépendance Python : le harnais reste installable sans rien compiler, et les deux images l'embarquent.

**Outillage de développement : dans Docker, jamais sur l'hôte** (règle du responsable,
2026-08-27). `pytest`, `ruff` et `mypy` sont installés dans l'image de développement
(`Dockerfile`) et nulle part ailleurs ; aucune commande du dépôt n'installe quoi que ce
soit sur la machine de l'utilisateur.

**Décision : les tests sont écrits avec `unittest` (bibliothèque standard).** Ils
s'exécutent sous `pytest` dans le conteneur comme sous `python -m unittest` sans rien
installer. Motif : cohérence avec le principe « zéro dépendance » ci-dessus, et un dépôt
qui reste vérifiable même là où l'outillage optionnel est absent — mesuré le 2026-08-27
sur l'hôte de développement, dépourvu de `pip`, `ensurepip`, `pytest`, `ruff` et `mypy`.
Écrire les tests en `unittest` ne coûte rien et supprime cette dépendance ; `pytest`
reste l'exécuteur privilégié dans le conteneur pour ses rapports.

**H2.2 — Arborescence cible.**

```text
src/avo/            paquet applicatif
  config.py         H3
  llm/client.py     H4
  context/          H5 (transcript, budget, continuation)
  memory/           H6 (workspace, notes)
  tools/            H7 (registre, dispatch, outils)
  loop/             H8 (machine d'états P→I→E→B)
  lineage.py        H9
  supervisor.py     H10
  runlog.py         H11
  arc/              SPEC_ARCAGI3 (client, rendu, interface, rhae, campagne)
  cli.py            point d'entrée `python -m avo`
mocks/llm_replay/   enregistreur/rejoueur du vrai endpoint (H4.7)
mocks/arc_replay/   serveur local contrat-ARC (SPEC_ARCAGI3 §A3)
tests/unit|integration|e2e/
tests/fixtures/     fixtures déterministes (seed)
runs/               artefacts d'exécution (gitignoré)
```

**H2.3 — Commandes contractuelles** (Makefile, documentées dans `README.md`).
**Chaque cible s'exécute dans un conteneur jetable** monté sur le dépôt
(`docker run --rm -v $PWD:/app --user $(id -u):$(id -g) avo-dev …`) : `make image`
(construit l'image de développement ; `make install` en est l'alias, puisque rien ne
s'installe sur l'hôte), `make lint`, `make typecheck`, `make test-unit`,
`make test-int`, `make test-e2e`, `make check` (campagne complète), `make build`
(image de production), `make up`/`make down` (pile compose), `make seed` (régénère
`tests/fixtures/`), `make smoke-live` (H4.8, hors campagne), `make run-arc`
(SPEC_ARCAGI3 §A7), `make record-llm` et `make test-int-live` (H4.7, exigent
`.env`, hors campagne). Toute preuve de session utilise ces cibles.

- **Cible non encore livrée** : elle échoue en nommant l'unité qui la livrera, jamais
  un succès simulé (CLAUDE.md §18).
- **Garde Docker** : si le démon est injoignable, la cible dit pourquoi et donne le
  correctif (appartenance au groupe `docker`), au lieu d'un échec opaque.
- **Mode dégradé `AVO_NO_DOCKER=1`** : exécute les tests sur l'hôte avec la seule
  bibliothèque standard, sans rien installer. Il **annonce** que le lint est réduit à
  une compilation et que le typecheck n'est pas exécuté ; le bilan de `make check`
  répète cette mention. C'est un repli d'environnement contraint, jamais le mode
  nominal, et il ne vaut pas preuve de style ni de typage.

**H2.4 — Conteneurisation.** Deux objets distincts :

1. **Image de développement et de preuves** (`Dockerfile`, livrée en U3) : Python slim
   + `pytest`, `ruff`, `mypy`. Le code n'y est pas copié mais monté en volume, pour
   qu'une modification locale soit prouvable sans reconstruction. C'est le seul endroit
   où l'outillage est installé.
2. **Pile de services** (`docker-compose.yml`, livrée en U5) : services `llm-replay` et
   `arc-replay`, healthchecks HTTP, ports fixes documentés (défauts : 11435 pour
   llm-replay, 8765 pour arc-replay).

La pile de développement est autonome : aucun service payant, aucun réseau externe,
aucune installation sur la machine hôte.

**Prérequis hôte, et eux seuls** : `git`, `docker` (démon joignable par l'utilisateur),
`make`. Python n'est requis sur l'hôte que pour le mode dégradé `AVO_NO_DOCKER=1`.

**Environnements à proxy TLS interceptant.** La construction de l'image de
développement installe l'outillage depuis PyPI en TLS ; derrière un proxy qui
intercepte le TLS avec sa propre autorité, cette étape échoue en
`CERTIFICATE_VERIFY_FAILED`. Mécanisme générique : tout certificat `*.crt` déposé
dans `certs/` (dossier du contexte de build, vide et versionné avec son seul
`README.md` ; les `*.crt` sont ignorés par git) est installé dans le magasin de
l'image de développement avant l'installation de l'outillage, et `pip` lit le
magasin système (`PIP_CERT`). L'image de production n'en reçoit aucun : elle ne
fait aucun appel TLS à la construction. Jamais de désactivation de vérification
TLS.

## H3. Configuration

**H3.1 — Variables.** Lues depuis l'environnement puis, à défaut, depuis `./.env`
(parseur minimal `CLE=valeur`, lignes `#` ignorées ; aucune valeur n'est journalisée) :

| Variable | Rôle | Défaut |
|---|---|---|
| `OLLAMA_HOST` | URL de base de l'endpoint | requis |
| `OLLAMA_API_KEY` | Bearer | requis |
| `OLLAMA_CONTEXT_LENGTH` | `options.num_ctx` demandé | requis |
| `AVO_MODEL` | nom du modèle | `qwen3.6:35b` |
| `AVO_THINK` | raisonnement natif (H12) | `false` |
| `AVO_NUM_PREDICT` | budget de sortie par appel | `4096` |
| `AVO_TEMPERATURE` | température | `0.7` |
| `AVO_TIMEOUT_S` | timeout par appel LLM | `900` |
| `AVO_CONTEXT_SOFT_RATIO` | seuil de continuation (H5.3) | `0.85` |
| `AVO_TOOL_STEPS_MAX` | garde du nombre d'appels d'outils par tour (H7.2) | `40` |
| `AVO_ACTIONS_MAX_NIVEAU` | borne d'actions d'environnement par niveau (H8.3) | `1000` |
| `AVO_ACTIONS_MAX_JEU` | borne d'actions d'environnement par jeu (H8.3) | `5000` |
| `AVO_SUP_STALL_ACTIONS` | actions sans progrès avant intervention du superviseur (H10.2) | `60` |
| `AVO_SUP_COOLDOWN` | actions minimales entre deux interventions (H10.3) | `30` |
| `AVO_RUNS_DIR` | racine des artefacts | `runs/` |
| `AVO_CONTEXT_MODE` | mode de contexte, `transcript` ou `state` (§H15.7) | `state` |
| `AVO_GARDES` | gardes de méthode dans les phases (§H16) | `true` |
| `AVO_GARDE_RETRIES` | redemandes d'une même garde par tour (§H16.0) | `2` |
| `ARC_API_KEY` | API ARC Prize (SPEC_ARCAGI3) | requis pour le live uniquement |
| `ARC_BASE_URL` | base API ARC | officielle en live, pile locale en rejeu |

**H3.2 — Budget utile.** `budget_prompt = floor(OLLAMA_CONTEXT_LENGTH / 1.15) −
AVO_NUM_PREDICT`. La marge 1,15 reproduit celle du proxy (mesurée) ; si un `413`
renvoie `max_context_tokens < OLLAMA_CONTEXT_LENGTH`, le budget est recalculé sur la
valeur apprise et l'événement journalisé.

**H3.3 — Validation.** Configuration invalide (URL malformée, entier non parseable,
variable requise absente pour le mode demandé) → erreur explicite au démarrage,
nommant la variable. Jamais de valeur par défaut silencieuse pour un secret.

**H3.4 — Modes.** `mode=replay` (défaut : services de rejeu locaux, aucun réseau externe, aucun
secret requis) et `mode=live` (endpoint réel + API ARC réelle ; exige les secrets).
Les tests et le worker n'utilisent que `replay`.

## H4. Client d'inférence

**H4.1 — Décision : surface native Ollama `/api/chat`.** Motif mesuré : contrôle du
raisonnement (`think`), `options.num_ctx`, champ `reasoning` séparé, compteurs
`prompt_eval_count`/`eval_count` exacts. Le client est derrière une interface
(`LLMClient.chat(messages, tools=None) -> ChatResult`) pour permettre un adaptateur
`/v1` ultérieur sans toucher la boucle.

**H4.2 — Requête.** POST `$OLLAMA_HOST/api/chat`, `Authorization: Bearer`, corps :
`model`, `messages`, `stream: false`, `think` (H12), `tools` (schémas H7),
`options: {num_ctx, num_predict, temperature}`. Timeout `AVO_TIMEOUT_S`.

**H4.3 — Réponse.** `ChatResult` typé : `content`, `reasoning` (peut être vide),
`tool_calls` (liste normalisée nom+arguments JSON), `done_reason`,
`prompt_eval_count`, `eval_count`, durées. Arguments d'outil non-JSON → erreur d'outil
renvoyée au modèle (H7.4), pas une exception fatale.

**Détail du contrat, mesuré le 2026-08-28 et contre-intuitif** : sur la surface
native, un appel d'outil arrive avec `done_reason: "stop"`, et non `"tool_calls"` —
cette dernière valeur appartient à la surface compatible OpenAI. La demande d'outil se
détecte donc sur la **présence de `message.tool_calls`**, jamais sur `done_reason`
(propriété `ChatResult.demande_outil`). Les arguments y sont déjà décodés en objet ;
la forme « chaîne JSON » reste gérée, les deux étant admises par l'API.

**H4.4 — Erreurs typées.** `AuthError` (401/403 — fatale, jamais retentée),
`ContextOverflow` (413 — porte `tokens_estimated` et `max_context_tokens` du corps ;
déclenche H5.4), `ServerError` (5xx), `TransportError` (réseau, timeout).

**H4.5 — Retries.** Uniquement `ServerError` et `TransportError` : **jusqu'à cinq
nouvelles tentatives après l'échec initial**, soit six requêtes au plus, avec des
attentes de 1 s, 4 s, 16 s, 45 s et 90 s affectées d'un jitter de ±25 %. Jamais sur
4xx — un refus d'authentification ou un dépassement de contexte se retenteraient à
l'identique. Chaque nouvelle tentative est journalisée (numéro, attente, motif).
Motif des deux paliers longs (mesuré le 2026-09-01, pilote `pilote-u24c`) : à
travers un pont qui coupe avant les premiers en-têtes, chaque tentative échouée
fait néanmoins avancer le cache de préfixe du serveur ; une politique patiente
transforme donc une panne transitoire de quelques minutes en simple retard, là où
trois retries (~21 s d'attente cumulée) clôturaient le jeu en échec nommé.

**H4.6 — Journalisation sans secret.** Ni clé, ni en-tête d'autorisation, ni URL avec
credentials dans les logs. Au niveau INFO : compteurs et durées ; le contenu complet
des échanges va dans le transcript du run (H11), fichier local uniquement.

**H4.7 — `llm-replay` : on développe contre le VRAI serveur, on rejoue ses réponses.**

Décision du responsable, 2026-08-27 : un endpoint d'inférence dédié est fourni ; il
n'est donc **pas** une dépendance « impossible à exécuter localement » et **ne se
simule pas** (CLAUDE.md §15). Aucun faux serveur Ollama n'est écrit : réimplémenter un
contrat que l'on peut mesurer revient à l'inventer, et garantit sa dérive.

Le dispositif est un **enregistreur/rejoueur** :

1. **Enregistrement** (`make record-llm`, exige `.env`) : le client H4 appelle le
   **vrai** endpoint ; chaque échange HTTP est capturé tel quel — requête envoyée,
   statut, en-têtes retenus, corps de réponse intégral, durées — dans une cassette
   `tests/fixtures/llm/cassettes/<nom>.jsonl`. La clé et l'hôte réel n'y figurent
   jamais (expurgés à l'écriture, vérifié par test).
2. **Rejeu** (défaut des tests, aucun secret, aucun réseau) : `llm-replay` sert les
   cassettes en appariant les requêtes sur une clé stable (méthode, chemin, modèle,
   empreinte des messages). Une requête qui ne correspond à aucune entrée rend une
   erreur explicite nommant l'écart — un test rouge lisible, jamais une réponse
   inventée.
3. **Détection de dérive** : `make test-int-live` rejoue les mêmes scénarios contre le
   serveur réel et compare au contrat enregistré. Un écart est un défaut à traiter,
   pas une cassette à réécrire en silence.
4. **Injection de fautes** : `llm-replay` sait rendre les erreurs que le serveur réel
   ne produit pas à la demande (500, latence, coupure). Les erreurs **réelles** —
   `401` sans clé ou avec clé invalide, `413` avec son corps de quota — sont
   enregistrées depuis le vrai serveur, où elles ont déjà été mesurées le 2026-08-27,
   et non fabriquées.

Le contrat servi en rejeu est donc toujours d'origine mesurée. Les tests unitaires,
eux, ne touchent ni cassette ni réseau.

**H4.8 — `make smoke-live`.** Vérification manuelle hors campagne : version, modèles,
une complétion courte, un tool-call. Exige `.env` ; jamais exécutée par les tests ni
par le worker.

## H5. Contexte : transcript append-only, budget, continuation

**H5.1 — Transcript append-only.** Structure `Transcript` immuable en tête : on ne
peut qu'ajouter des messages. Invariant vérifié par test : le hash du préfixe déjà
envoyé ne change jamais entre deux appels LLM du même segment. Motif : cache de
préfixe (H1.3.1). Le message système et l'ordre des messages sont figés au début d'un
segment.

**H5.2 — Comptabilité.** Estimation locale des tokens (chars/3,4, calibrée) corrigée
à chaque réponse par `prompt_eval_count` réel. L'estimation sert aux seuils, le réel
fait foi dans les métriques.

**H5.3 — Continuation en contexte frais** (mécanisme VISTA). Quand l'estimation dépasse
`AVO_CONTEXT_SOFT_RATIO × budget_prompt`, l'agent est invité à écrire un « état de
continuation » concis (dernier message du segment), puis un nouveau segment démarre :
système + état de continuation + notes (H6) + observation courante. L'ancien segment
reste dans les artefacts du run. Les notes et la mémoire de jeu survivent — seul le
contexte conversationnel est renouvelé.

**H5.4 — `413` = cas nominal.** Un `ContextOverflow` en cours de segment déclenche
immédiatement H5.3 (sans nouvel appel sur le segment plein) et met à jour le budget
appris (H3.2). Deux `413` consécutifs sur un segment frais → erreur fatale explicite
(configuration incohérente), jamais une boucle.

## H6. Espace de travail et notes persistantes

**H6.1 — Workspace par run.** `runs/<run_id>/` : `manifest.json` (config résolue sans
secret, version du code, horodatage), `transcripts/segment_NNN.jsonl`,
`notes/GUIDE.md`, `notes/WORKING.md`, `frames/` (SPEC_ARCAGI3), `lineage/` (H9),
`metrics.jsonl`, `report.md`. Reproductible et auto-porteur : le run se rejoue et
s'audite sans le dépôt.

**H6.2 — Notes (mécanisme VISTA, repris tel quel).** `GUIDE.md` : compréhension
durable, transverse aux niveaux. `WORKING.md` : brouillon du niveau courant.
Lisibles et inscriptibles par les outils `note_read` / `note_write` (H7.3).
Injectées en tête de chaque segment frais (H5.3).

## H7. Outils

**H7.1 — Registre.** Un outil = nom, description, schéma JSON des paramètres,
fonction. Le registre produit le tableau `tools` de l'appel LLM et route les
`tool_calls`. Les outils disponibles dépendent du mode de la boucle (jeu : actions
ARC + inspection + notes ; les outils d'action ne sont exposés qu'à l'état où agir
est permis).

Un groupe d'outils peut dépendre de l'état de l'environnement, et non seulement de
celui de la boucle : `synchroniser(étiquette, outils)` remplace en bloc les outils
portant une étiquette, sans toucher aux autres groupes. C'est ce qui permet à une
surface d'action de suivre ce que l'environnement déclare (SPEC_ARCAGI3 A5.2) ;
enregistrer un outil déjà présent reste une erreur, précisément pour qu'un
remplacement soit toujours explicite.

**H7.2 — Exécution.** Chaque `tool_call` est exécuté séquentiellement ; le résultat
(ou l'erreur) revient comme message `role: tool` append-only. Limite de garde :
`AVO_TOOL_STEPS_MAX` (défaut 40, valeur Tycho) appels d'outils par tour ; au-delà, le
tour est clos avec un message explicite.

**H7.3 — Outils génériques.** `note_read(name)`, `note_write(name, content)`
(uniquement `GUIDE`/`WORKING`), `inspect` et `read_pixels` (définis en SPEC_ARCAGI3
§A4 — mémoire visuelle sans perte, gratuite au score).

**H7.4 — Erreurs d'outil.** Toujours renvoyées au modèle sous forme de texte
diagnostiquable (`error: <type>: <détail>`), jamais avalées, jamais fatales pour le
run (sauf H5.4 double-413 et AuthError).

## H8. Boucle agent P→I→E→B

**H8.1 — États** (papier AVO fig. 2, instanciation ARC — décision H1.2) :

- **Planning** : relire évidence et notes, formuler/réviser hypothèses, choisir la
  prochaine action et **énoncer la prédiction** de son effet (exigence du prompt
  VISTA, reprise) ;
- **Implementation** : exécuter exactement une action d'environnement via l'outil
  d'action ;
- **Evaluation** : confronter frames observées et prédiction, énoncer tous les
  changements visibles, mettre à jour notes et score ;
- **Bug-Fixing** : sur prédiction contredite ou situation dégradée, réviser les
  hypothèses ; `RESET` si la tentative est condamnée ou plus coûteuse qu'un redémarrage.

La machine d'états est du code (transitions déterministes pilotées par les événements :
action jouée, niveau complété, game over, contradiction déclarée) ; le contenu des
phases est du prompt. Prompts par phase versionnés dans `src/avo/loop/prompts.py`,
courts, sans description des règles du jeu (contrainte direct-interaction).

**H8.2 — Un tour.** Observation courante (+ statut, actions disponibles) → phases
P→I→E (B conditionnelle) → le dernier frame retourné devient l'observation suivante.
Toute frame retournée entre dans la mémoire de frames (SPEC_ARCAGI3 §A4).

**H8.3 — Arrêts.** Trois causes d'arrêt, consultées entre deux tours et à la
clôture, dans cet ordre de priorité :

1. **État terminal de la tâche.** Le contrat `Environnement` (H8.2) porte
   `etat_terminal() -> str | None` : un motif explicite (par exemple « victoire »)
   quand l'environnement est dans un état où plus aucune action ne peut faire
   progresser la tâche, `None` sinon. C'est l'environnement qui tranche, jamais le
   texte du modèle (même principe qu'en H8.1). Dès que le motif est rendu, la boucle
   clôt SANS nouvel appel au modèle : tout tour joué après l'état terminal serait de
   l'inférence dépensée pour un score qui ne peut plus changer (mesuré, run
   opérateur U21 : 44 tours d'appels au modèle après la victoire). Ce motif prime
   les bornes et l'épuisement des tours — une tâche accomplie au dernier tour se
   clôt sur son motif terminal, jamais sur « tours_epuises ».
2. **Bornes d'actions.** Deux bornes distinctes, car un niveau qui s'enlise et un
   jeu qui s'éternise ne se diagnostiquent pas pareil : `AVO_ACTIONS_MAX_NIVEAU` et
   `AVO_ACTIONS_MAX_JEU`. Généreuses par défaut, resserrées en campagne où elles
   sont exigées (SPEC_ARCAGI3 §A7.1). Dépassement → arrêt propre du jeu, la borne
   franchie étant nommée dans le rapport. Aucune temporisation arbitraire : on borne
   des actions, jamais du temps d'horloge.
3. **Arrêt anticipé** (`arret_anticipe`, SPEC_ARCAGI3 §A7.4) : consulté entre deux
   tours seulement, après les deux causes précédentes — c'est ainsi que la campagne
   fait respecter ses budgets sans interrompre une opération en vol.

**H8.4 — Ce que la boucle porte en plus des phases.** Trois mécanismes livrés
ailleurs n'existent pour un run que si la boucle les appelle ; sans cela ils sont du
code mort et le rapport de campagne (SPEC_ARCAGI3 §A7.3) annonce structurellement
zéro sur des lignes qu'il est censé mesurer.

1. **Continuation** (H5.3, H5.4), par deux chemins qu'il ne faut pas confondre :
   - *préventif*, quand le seuil est atteint et que le segment répond encore : la
     boucle demande à l'agent d'écrire son état de continuation
     (`INVITATION_CONTINUATION`), et c'est **sa** réponse qui ouvre le segment frais.
     C'est le mécanisme VISTA, et le seul qui préserve ce que l'agent juge digne
     d'être retenu ;
   - *réactif*, sur `ContextOverflow` : le segment plein ne répond plus, donc **aucun
     appel n'y est fait** (H5.4). L'état de continuation est alors écrit par le
     harnais — phase, compteurs, dernière observation —, factuel et sans appel. La
     boucle rejoue ensuite l'appel une seule fois, sur le segment frais.

   Le segment clos est archivé dans `transcripts/`. Deux dépassements consécutifs
   lèvent (H5.4).
2. **Supervision** (H10). La boucle tient la trajectoire — action jouée, empreinte de
   frame, complétion, passage en Bug-Fixing — et, à la fin de chaque tour, demande au
   superviseur s'il doit intervenir. L'intervention est un appel LLM **séparé** dont
   le résultat est ajouté en fin d'historique. La boucle n'interprète pas le
   diagnostic : elle l'ajoute, et le tour suivant s'y confronte.
3. **Métriques** (H11.2). Quand un workspace est fourni, la boucle écrit une ligne par
   appel LLM (phase, tokens de prompt et de génération, durées, troncature), une par
   action jouée (jeu, niveau, index, événement) et une par événement (continuation,
   dépassement absorbé, intervention du superviseur, borne franchie).

4. **Lignée** (H9.2). Chaque complétion de niveau propose une version à la lignée :
   évidence = le bilan courant, notes = `GUIDE.md` et `WORKING.md`. La politique
   « correct ∧ ≥ meilleur » décide seule ; une version refusée n'est pas un incident.
   Une version committée est signalée au superviseur, dont le détecteur de stagnation
   compte les actions écoulées « sans complétion **ni** entrée de lignée » (H10.2) —
   sans ce branchement, la seconde moitié de sa condition serait toujours vraie.

Ces quatre branchements sont **optionnels par construction** : sans workspace, sans
superviseur et sans lignée, la boucle se comporte exactement comme avant, ce qui
préserve les preuves qui l'éprouvent sur un environnement factice.

## H9. Lignée et fonction de score

**H9.1 — Formalisme** (papier AVO §3.1) : `Vary(Pₜ) = Agent(Pₜ, K, f)` ; lignée
single-lineage de paires (xᵢ, f(xᵢ)) ; commit uniquement si correct **et** score ≥
meilleur score committé.

**H9.2 — Instanciation ARC (décision).** xᵢ = état de connaissance validé au moment
d'un progrès (contenu de `GUIDE.md` + `WORKING.md` + méta du run) ; f(xᵢ) = vecteur
(niveaux complétés, −actions cumulées) en ordre lexicographique — « correct » =
progression officielle constatée par l'environnement. Chaque complétion de niveau
produit donc un commit de lignée avec son score. Motif : sur ARC il n'y a pas de
kernel à committer ; l'artefact qui s'améliore de façon monotone et vérifiable est la
connaissance du jeu adossée à la progression officielle — fidèle au mécanisme
(versions validées scorées, jamais de régression committée) sinon au domaine.

**H9.3 — Implémentation.** `runs/<run_id>/lineage/` est un dépôt git **jetable et
dédié**, initialisé par le run (`git init`), un commit par version validée, score dans
le message. Interdiction absolue de toucher au dépôt projet (CLAUDE.md §13) — vérifié
par test (le répertoire de lignée contient son propre `.git`).

**H9.4 — `Scorer` branchable.** Interface `score(evidence) -> tuple` + `is_valid`.
Implémentations : scorer ARC (H9.2) et scorer de test déterministe pour les tests de
la boucle.

## H10. Superviseur

**H10.1 — Rôle** (papier AVO §3.3) : détecter stagnation et cycles improductifs,
puis intervention conditionnelle qui redirige l'agent principal. Le superviseur ne
joue jamais d'action (séparation à la Tycho : seul l'acteur agit).

**H10.2 — Déclencheurs (code, mesurables, configurables).**
`AVO_SUP_STALL_ACTIONS` (défaut 60) actions sans complétion de niveau **et** sans
nouvelle entrée de lignée ; ou motif d'actions répétées (fenêtre de 12 actions dont
≥ 8 identiques sans changement de frame) ; ou volume de `Bug-Fixing` anormal
(> 5 entrées consécutives).

**H10.3 — Intervention.** Appel LLM séparé (contexte propre : résumé de trajectoire,
notes, dernières frames rendues en texte) qui produit un diagnostic et 2–3 directions
alternatives ; le résultat est injecté dans le transcript principal comme message
utilisateur balisé `[SUPERVISEUR]` (append-only, H5.1 respecté). Fréquence bornée :
au plus une intervention par `AVO_SUP_COOLDOWN` actions (défaut 30). Chaque
déclenchement et son motif sont journalisés dans `metrics.jsonl`.

## H11. Observabilité

**H11.1 — Logs.** `logging` stdlib, format JSON une-ligne, niveaux, identifiant de
run corrélant tout ; jamais de secret (H4.6).

**H11.2 — Métriques par run** (`metrics.jsonl`) : par appel LLM (tokens prompt/éval,
durées, retries), par action (jeu, niveau, index, latence), par événement
(continuation, 413, intervention superviseur, commit de lignée). Totaux dans
`report.md`.

**H11.3 — Transcripts.** Chaque segment intégral en JSONL (messages exacts envoyés et
reçus). C'est la preuve d'exécution et l'entrée du rejeu.

## H12. Politique de raisonnement

**H12.1 — Décision : `think: false` par défaut**, raisonnement explicite dans le
contenu (à la VISTA : « fuzzy reasoning » en langage libre, suffisant d'après leurs
résultats). Motifs mesurés : le raisonnement natif consomme `num_predict` avant tout
contenu, et son texte n'est pas réinjectable dans l'historique append-only sans
gonfler le préremplissage. `AVO_THINK=true` reste disponible (comparaison en
campagne) ; dans ce cas `AVO_NUM_PREDICT ≥ 8192` est imposé par la config.

## H13. Erreurs et reprise

**H13.1 —** Toute erreur non typée remonte, arrête le run proprement (artefacts
flushés, raison dans `report.md`) — jamais de `try/except` silencieux (CLAUDE.md §18).

**H13.2 — Reprise de run.** `python -m avo resume <run_id>` : reconstruit l'état
depuis le workspace (notes, dernière observation, compteurs) et repart sur un segment
frais. En campagne, la reprise réutilise le même scorecard tant qu'il est ouvert
(SPEC_ARCAGI3 §A7).

## H14. Plan de tests du noyau

**H14.1 — Unitaires** (par unité de backlog, cas nominal + limites + erreurs) :
config (H3 : parsing, validation, budget), client (H4 : erreurs typées, retries,
parsing), transcript (H5 : invariant append-only par hash, seuils, continuation),
notes (H6), registre d'outils (H7 : dispatch, erreurs, garde), machine d'états (H8 :
transitions sur événements scriptés), lignée (H9 : politique de commit, isolation
git), superviseur (H10 : déclencheurs sur trajectoires synthétiques), scorer (H9.4).

**H14.2 — Intégration** (contre `llm-replay`, cassettes enregistrées sur le vrai
serveur) : boucle complète, tool_calls, 401 et 413 **réels** rejoués, 500 et latence
injectés, continuation réelle sous petit budget. Variante `test-int-live` contre le
serveur réel pour détecter toute dérive du contrat.

**H14.3 — E2E** : voir SPEC_ARCAGI3 §A8 (partie de jeu complète sur rejeu local, par
la CLI réelle, artefacts vérifiés).

**H14.4 — Adaptation §16 CLAUDE.md.** Le produit n'a pas d'interface graphique : la
« vérification visuelle » s'entend comme l'exécution réelle des commandes CLI dans la
peau de l'opérateur (terminal, `make …`), l'observation des sorties, et la lecture
des artefacts produits (`report.md`, rendus de grilles). Documenté aussi dans
`docs/MASTER_PLAN.md` ; s'il gagne un jour une UI, §16 s'applique en entier.

## H15. État d'exécution structuré (SKILL.state) — mode `state`

Chapitre couvrant U26 (runtime `avo.context.etat`) et U27 (branchement dans la
boucle). Source : papier SKILL.state, arXiv:2608.26263, §3 (contrat), §5.7
(taxonomie d'erreurs), §7 (limites) — export intégral dans
`knowledge/arxiv-2608.26263-skill-state-long-horizon-agent-skills.md`.

**H15.0 — Statut : les deux modes sont livrés, `state` est le défaut.** Les deux
modes coexistent, exclusifs pour un même segment (H15.7) ; aucun ne remplace
l'autre. Le départage s'est fait par la mesure, jamais sur le papier : A/B sur
rejeu (U27, `docs/rapports/ab_mode_contexte.md`) puis A/B en conditions réelles
(U28, `docs/rapports/ab-u28-state.md` — à budget de temps égal, 33 actions contre
6 et ~15× moins de tokens de prompt par action, prompt borné O(1) constaté). Sur
ces mesures, le responsable a arrêté `state` comme mode par défaut (décision du
2026-09-01, journal suite 9) ; `transcript` (H5) reste activable par
`AVO_CONTEXT_MODE=transcript`, notamment là où le cache de préfixe rend
l'append-only avantageux (contrainte mesurée du 2026-08-27 suite 2).

**H15.1 — Contrat d'exécution d'un pas.** En mode `state`, chaque pas est défini par
`(P, Σₜ, Oₜ)` (papier §3, éq. 2) : la spécification procédurale (le prompt système,
fixe), l'état d'exécution structuré courant, et la dernière observation reçue de
l'environnement — jamais l'historique des observations, actions ou raisonnements
passés. Le modèle produit `(Rₜ, ΔΣₜ, aₜ)` (éq. 3) : un raisonnement en texte libre
`Rₜ`, un patch d'état `ΔΣₜ` et une action `aₜ`, sous la forme d'un bloc ```` ```json
```` unique portant exactement deux clés, `state_patch` (objet) et `action`
(chaîne) — le format de l'annexe A.4 du papier, repris tel quel. `Rₜ` n'est **jamais**
réinjecté dans un prompt suivant : une fois le patch validé et appliqué, il est
définitivement jeté (§H15.1, papier §3.2). C'est ce qui borne la taille de prompt en
`O(1)` par tour et la consommation cumulée en `O(T)` plutôt qu'en `O(T²)` (papier §3.3) —
propriété que H5 n'a pas : son budget croît avec le nombre de segments.

**H15.2 — Opérateur `⊕` : fusion avec suppression par `null`.**
`Σₜ₊₁ = Σₜ ⊕ ΔΣₜ` (éq. 4). Une clé absente du patch **laisse le champ correspondant
inchangé** — c'est la propriété qui évite l'écrasement accidentel, mode d'erreur
dominant mesuré par le papier (68 %, §5.7, « premature state overwrite/deletion »).
Une clé présente avec une valeur non nulle **remplace** le champ. Une clé présente
avec la valeur `null` réinitialise le champ à son défaut du schéma plutôt que de le
retirer de Σ : le schéma ARC v1 (H15.6) déclare quatre champs **toujours présents**,
donc Σ reste en permanence conforme à son schéma — aucun état intermédiaire
partiellement peuplé n'existe. C'est un raffinement assumé de la sémantique générale
du papier (qui autorise la disparition d'une clé) pour un schéma à champs fixes ; le
point est écrit ici pour qu'un lecteur du papier ne s'attende pas à une clé absente
de Σ après un `null`.

**H15.3 — Propriété du schéma et de la validation : au runtime, jamais au modèle.**
Le schéma de Σ est possédé et fait autorité côté runtime (papier §7, dernier
paragraphe : « schema ownership and validation reside in the deterministic runtime
rather than the model »). Chaque champ du patch est validé structurellement — type,
forme, valeurs admissibles — avant fusion ; un patch qui échoue à la validation
**n'atteint jamais Σ**, qui reste donc toujours dans un état valide. L'erreur nomme
le champ fautif, jamais un rejet générique (CLAUDE.md §18) : c'est la classe
« Schema Comprehension / Type Coercion » de la taxonomie (20 %, §5.7).

**H15.4 — Rollback-retry borné.** Deux façons dont un pas peut échouer avant
d'atteindre Σ, chacune couverte par la taxonomie du papier (§5.7) :

- le texte du modèle ne contient pas de bloc JSON à deux clés interprétable (bloc
  absent, JSON syntaxiquement invalide, clés manquantes ou en trop, types incorrects
  au niveau du bloc) — classe « JSON Syntax/Formatting Slips » (12 %) ;
- le bloc est syntaxiquement valide mais `state_patch` échoue à la validation du
  schéma (H15.3) — classes 68 % et 20 % ci-dessus.

Dans les deux cas, Σ n'est pas modifié et l'échec est compté sur un budget borné de
tentatives pour le pas courant (`RETRIES_MAX = 3`, valeur du module — même principe
que les deux `413` consécutifs de H5.4 : jamais une boucle infinie). Le budget épuisé
sans patch valide est une erreur fatale explicite qui arrête le run proprement
(H13.1), jamais un `try/except` silencieux ni un état par défaut trompeur. Chaque
tentative refusée est comptée en événement (H11.2, au même titre qu'une continuation
ou un `413` absorbé) et lue par les détecteurs du superviseur (H15.7).

**H15.5 — Persistance et reprise.** Σ est sérialisé dans le workspace du run
(`runs/<run_id>/state/etat.json`, aux côtés de `notes/` et `transcripts/` — H6.1) après
chaque pas validé. La sérialisation est un aller-retour à l'identique : relire Σ
sérialisé rend un état égal à celui qui l'a produit, structure imbriquée comprise.
La reprise d'un run en mode `state` (H13.2) recharge Σ depuis ce fichier plutôt que
de le réinitialiser — contrairement au transcript, qui repart sur un segment frais,
Σ n'a pas de notion de segment à rouvrir.

**H15.6 — Schéma ARC v1 de Σ.** Quatre champs, tous obligatoires et toujours
présents (H15.2), fixés par cette unité :

| Champ | Type | Rôle |
|---|---|---|
| `position` | `{"x": int, "y": int}` ou `null` | Position courante crue de l'agent dans la grille, si identifiée. |
| `essai` | entier ≥ 1 | Numéro de la tentative courante sur le niveau (incrémenté par le modèle à chaque `RESET` volontaire qu'il décide). |
| `hypotheses` | liste de chaînes | Hypothèses testées, formulées librement, qui survivent à un pas qui ne les mentionne pas. |
| `objets` | liste de `{"id": str, "description": str, …}` | Objets identifiés dans la grille ; clés au-delà de `id`/`description` libres et non validées. |

Le schéma est volontairement minimal — quatre champs génériques à toute grille
ARC-AGI-3, pas un par jeu (une constante ou une heuristique propre à un jeu
violerait l'interdiction de benchmaxing, `CLAUDE_PROJECT.md`). Une clé de patch hors
de ces quatre est refusée (H15.3) : le schéma n'est pas extensible à la volée par le
modèle, seul le runtime le fait évoluer (schéma v2 hypothétique, hors périmètre).

**H15.7 — Articulation avec les autres chapitres.**

- **H5 (mode exclusif par segment).** Un segment est soit en mode `transcript`
  (H5, historique complet renvoyé), soit en mode `state` (Σ + observation courante
  seuls) — jamais les deux à la fois. `AVO_CONTEXT_MODE` (U27) fixe le mode pour tout
  le run, défaut `state` (décision du responsable du 2026-09-01 sur l'A/B réel de
  U28, §H15.0) ; `transcript` reste activable explicitement.
- **H6.2 (notes).** `GUIDE.md`/`WORKING.md` restent la mémoire durable **trans-niveaux** ;
  Σ est l'état opérationnel du niveau courant. Les notes ne sont pas remplacées par
  Σ : un `RESET` de niveau réinitialise Σ (H15.6) mais pas les notes.
- **H10 (superviseur).** Les détecteurs de stagnation (H10.2) lisent aussi les
  tentatives de patch refusées (H15.4) comme un signal d'enlisement, au même titre
  que les actions répétées ou le volume de Bug-Fixing anormal.
- **H12 (raisonnement).** `Rₜ` jeté après projection (H15.1) est la même politique
  que H12.1 pour le raisonnement natif désactivé (`think: false`) : dans les deux
  cas, un texte de raisonnement existe le temps du tour et n'est jamais réinjecté.
  Le mode `state` généralise ce principe à la réponse entière, pas seulement au
  raisonnement natif.
- **Limite « statistique suffisante » (papier §7).** Le mode `state` suppose que
  tout ce qui compte pour la suite peut être projeté dans Σ au moment où c'est
  observé ; ce n'est pas toujours vrai (le papier cite explicitement l'information
  dont la pertinence n'est reconnue qu'après coup). Décision : l'archivage sans
  perte des frames (SPEC_ARCAGI3 §A4, `inspect`/`read_pixels`, gratuit au score)
  reste inchangé et disponible dans les deux modes — c'est le filet qui permet de
  retrouver une information non projetée dans Σ au moment où sa pertinence apparaît,
  sans dépendre de l'historique conversationnel pour cela.

**H15.8 — Un pas = un tour (précision d'implémentation, U27).** H15.1–H15.7
laissent un point ouvert pour le branchement dans la boucle : la correspondance
entre « un pas » (papier) et le découpage P→I→E→B de §H8.1. Décision, tranchée à
l'implémentation faute d'indication contraire du papier ou de la spécification :
**un pas du mode `state` correspond à un tour entier de la boucle, pas à une phase.**
Motif : forcer une sortie `(state_patch, action)` à chacun des 3-4 appels d'un
tour classique obligerait les phases Planning/Evaluation/Bug-Fixing — qui ne
jouent aucune action — à produire un champ `action` sans objet, ce que le contrat
à deux clés (§H15.1) ne permet pas de représenter proprement. La machine d'états
de §H8.1 (phases, transitions) reste donc de la seule responsabilité du mode
`transcript` ; le mode `state` ne l'utilise pas.

Conséquences, toutes de la seule responsabilité de la boucle (`avo.loop.boucle`),
le module `avo.context.etat` restant inchangé et pur :

- **Un appel LLM par tour.** Le message système reste `P` (`prompts.SYSTEME`,
  inchangé) ; le message utilisateur compose Σ sérialisé (§H15.5), les notes
  (§H6.2, mêmes qu'une continuation), l'observation courante et les actions
  disponibles, et une invite de protocole (nouvelle constante `prompts.PROTOCOLE_ETAT`,
  générique, décrivant uniquement le format du bloc JSON et le schéma de Σ —
  aucune règle de jeu, §A5.1). Aucun outil n'est déclaré à cet appel (`tools=None`) :
  le contrat SKILL.state ne passe pas par l'appel de fonctions, seulement par le
  texte (§H15.1).
- **Rollback-retry (§H15.4) tient le tour, pas le run.** Sur `PatchMalforme` ou
  `EtatInvalide`, le harnais retente le MÊME appel (mêmes Σ et observation), avec
  le message d'erreur nommé ajouté à l'invite pour que le modèle se corrige.
  `CompteurRetries` est réinitialisé à chaque tour. Le budget épuisé lève une
  erreur fatale explicite qui arrête le run (§H13.1) — jamais un état par défaut.
- **Résolution générique de l'action.** Le champ `action` du pas est une chaîne
  `"<nom_outil>"` ou `"<nom_outil> v1,v2,…"` pour un outil dont le schéma déclare
  des paramètres requis (par exemple un clic à coordonnées) : les valeurs sont
  lues dans l'ORDRE des paramètres requis déclarés par le schéma de l'outil, et
  coercées selon leur type JSON déclaré (entier, nombre, chaîne) — jamais un nom
  d'action ni un nombre de paramètres codé en dur, pour rester valable sur
  n'importe quel jeu (interdiction de benchmaxing, `CLAUDE_PROJECT.md`). Le jeton
  de nom est NORMALISÉ avant la recherche : la ponctuation traînante (virgule,
  point, point-virgule, deux-points) en est retirée — bruit de format des modèles
  open-weight, mesuré en conditions réelles (run `ab-u28-state`, 2026-09-01 : un
  tour perdu sur « action1, ») et cohérent avec la taxonomie d'erreurs de
  SKILL.state ; la normalisation ne touche que la ponctuation de bord du jeton,
  jamais les valeurs ni le sens. Le nom
  résolu est exécuté par le registre comme n'importe quel outil d'action
  (§H8.1 : « c'est le registre qui l'exécute ») ; un nom inconnu ou des valeurs en
  nombre incorrect produisent l'erreur d'outil habituelle (§H7.4), jamais fatale.
- **Détection d'événement inchangée.** Niveau complété et partie perdue restent
  décidés par l'environnement, jamais par le texte (§H8.1, principe repris tel
  quel). La contradiction reste lue dans le texte du pas (même heuristique qu'en
  mode `transcript`) : le texte d'un pas contient le raisonnement `Rₜ` avant le
  bloc JSON, seul endroit où une contradiction peut s'énoncer en mode `state`.
- **Bug-Fixing est implicite.** Il n'existe pas d'appel séparé : une contradiction
  ou un game-over n'ouvrent pas une phase à part, ils apparaissent dans
  l'observation du pas suivant, et c'est au `ΔΣ` de ce pas suivant de porter la
  révision. C'est une différence assumée avec le mode `transcript`, à départager
  par la mesure (U27 : A/B sur rejeu ; U28 : A/B en réel), pas sur le papier.
- **Persistance (§H15.5).** Σ est écrit dans `runs/<run_id>/state/etat.json` après
  chaque tour réussi (`Workspace.ecrire_etat`). La reprise au niveau où l'existant
  la supporte réellement est **par jeu**, pas par tour (§A7.4 : un jeu entamé est
  entièrement rejoué) — ce qui vaut identiquement pour le transcript du mode
  `transcript`, dont aucun segment archivé n'est aujourd'hui rechargé non plus. Un
  `BoucleAgent` construit sur un workspace qui porte déjà un `etat.json` le
  recharge plutôt que de repartir de `Etat.initial()`, ce qui couvre le cas où
  l'appelant le fournit délibérément.
- **`413` en mode `state` (§H15.7, H8.4.1).** Sans historique à raccourcir, la
  continuation de §H5.3 est sans objet. Un `ContextOverflow` est compté
  (`bilan.depassements`, métrique `depassement`) puis propagé tel quel : c'est une
  erreur fatale explicite (§H13.1), jamais une absorption silencieuse.

## H16. Gardes de méthode dans les phases — la structure impose ce que le prompt conseille

Chapitre couvrant U30. Source : instruction du responsable (2026-08-31, journal
suite 3) et les publications de `knowledge/` — AVO met la base de connaissances K
dans la signature `Vary(Pₜ) = Agent(Pₜ, K, f)` (§H9.1) ; VISTA exige la prédiction
avant l'action, les changements observés après, et les notes GUIDE/WORKING ;
SKILL.state porte l'état structuré Σ. Ce chapitre MÉCANISE ces règles à l'intérieur
des phases P→I→E→B existantes (§H8.1) ; il n'invente aucune règle et ne crée aucune
phase.

**H16.0 — Statut et principes.**

1. **Le prompt conseille, la structure impose.** Un modèle sous charge dérive de
   ses consignes, pas de ses contraintes. Chaque garde exige un ARTEFACT à un point
   précis de la boucle et refuse d'avancer tant qu'il manque — elle n'exige jamais
   un raisonnement scénarisé : la structure demande l'artefact, le modèle pense.
2. **Aucune garde n'est fatale pour le run.** Un refus de garde est nommé, compté
   (H11.2) et borné ; l'épuisement du budget de redemandes clôt le tour sans action
   ou applique l'issue prudente écrite ici — jamais une exception qui arrête le
   run, jamais un succès simulé.
3. **Génériques.** Aucune garde ne mentionne un jeu, un objet ou une règle
   d'environnement (§A5.1, balayage « zéro indice de jeu » inchangé). Les gardes
   valent pour les deux modes de contexte (H5 `transcript` et H15 `state`) ; quand
   un mode ne porte pas la surface nécessaire, le présent chapitre le dit et nomme
   l'équivalent.
4. **Débrayables et mesurables.** `AVO_GARDES` (H3.1, défaut `true`) active les
   quatre gardes ensemble ; `false` restitue exactement le comportement antérieur.
   C'est ce qui permet la comparaison avant/après sur le jeu `cible` (A/B, même
   principe que §H15.0 : le départage se fait par la mesure). `AVO_GARDE_RETRIES`
   (défaut `2`) borne les redemandes d'une même garde dans un même tour.
5. **Artefacts bornés.** Le préremplissage domine le coût (H1.3.1) : les invites
   de garde sont des constantes courtes de `prompts.py` (versionnées, VERSION
   incrémentée) ; une prédiction transmise au fil est tronquée à
   `PREDICTION_MAX_CARACTERES = 2000` caractères (constante du module, sous la
   limite mesurée de 16 Ko du champ `reasoning`, §A1.4).

**H16.1 — Garde documentaire, à l'entrée de Planning.** Le réflexe « chercher
l'information avant d'agir », mécanisé : les outils d'action ne se déverrouillent
jamais sur un `WORKING.md` vide.

- **Composition de K.** Le premier Planning d'un run reçoit, en plus de
  l'observation : le contexte de tâche fourni (le message système, et toute
  documentation de protocole que le responsable fournit au harnais), les notes
  durables (`GUIDE.md`, injectées par H6.2) et la demande d'artefact : écrire dans
  `WORKING.md` « ce que je sais / ce que j'ignore / comment je compte le
  découvrir ». La demande est une constante générique (`prompts.GARDE_DOCUMENTAIRE`).
- **Invariant (mode `transcript`).** La transition Planning → Implementation est
  refusée tant que `WORKING.md` est vide : à la place d'Implementation, la boucle
  redemande l'artefact (invite nommée), au plus `AVO_GARDE_RETRIES` fois par tour ;
  budget épuisé → le tour est clos sans action (même chemin que « tour sans
  action », §H8.2), l'événement est compté, le tour suivant redemande. La garde se
  réarme d'elle-même chaque fois que `WORKING.md` redevient vide (l'interface de
  tâche peut le vider à un changement de niveau : le brouillon du niveau suivant
  se recompose alors avant d'agir).
- **Mode `state`.** L'artefact est le champ `hypotheses` de Σ (§H15.6) : tant
  qu'il est vide, l'action du pas est retenue (non jouée, donc gratuite) et le pas
  suivant reçoit l'erreur nommée par le mécanisme d'erreur d'action existant
  (§H15.8). `hypotheses` survivant aux niveaux, la garde ne mord en pratique qu'à
  l'ouverture du run — c'est voulu : Σ est trans-tour, pas trans-note.

**H16.2 — Garde de prédiction.** Une action n'est jouable qu'accompagnée de sa
prédiction (VISTA) ; sur le fil officiel, la prédiction part dans le champ
`reasoning` mesuré en U22 — auditable dans le scorecard.

- **Mode `transcript`.** Chaque outil d'action (§A5.2) porte un paramètre REQUIS
  `prediction` (chaîne non vide) : l'effet attendu de l'action, en une ou deux
  phrases. Un appel sans prédiction est une erreur d'outil nommée (§H7.4), rendue
  au modèle qui se corrige — l'action n'est PAS jouée, rien n'est dépensé au
  score. Le paramètre est retiré des arguments avant de jouer la commande ; sa
  description est générique (« ce que tu attends de cette action ») et ne décrit
  aucun effet réel (§A5.1).
- **Mode `state`.** Le pas doit contenir, AVANT le bloc JSON, une ligne
  `PREDICTION: …` (une seule ligne). Absente → l'action est retenue et le pas
  suivant reçoit l'erreur nommée (mécanisme §H15.8, aucune action dépensée). La
  ligne est extraite par le harnais avant que le reste de `Rₜ` ne soit jeté
  (§H15.1) : la prédiction est le seul fragment de `Rₜ` qui survit au tour, et
  seulement jusqu'à l'évaluation du tour suivant.
- **Fil officiel.** La prédiction (tronquée, H16.0.5) est envoyée dans
  `reasoning` des commandes `ACTION1`–`ACTION7` (§A1.4 ; `RESET` n'en porte pas
  sur le fil mesuré). En rejeu, `arc-replay` l'accepte sans en faire un critère
  d'appariement d'épisode (les épisodes enregistrés n'en portent pas).
- La boucle CONSERVE la prédiction du tour courant pour la garde d'évaluation.

**H16.3 — Garde d'évaluation.** L'environnement tranche les faits (H8.1,
inchangé) ; le harnais présente prédit-contre-observé et exige la qualification
avant l'action suivante.

- **Mode `transcript`.** L'invite d'Evaluation cite la prédiction conservée
  (« Tu avais prédit : “…” ») avec l'observation, et exige une ligne
  `VERDICT: confirmee` ou `VERDICT: contredite` (accents et casse tolérés).
  Réponse sans verdict → redemande nommée, au plus `AVO_GARDE_RETRIES` fois ;
  budget épuisé → issue prudente : la prédiction est réputée CONTREDITE (une
  prédiction non qualifiée n'est pas confirmée), l'événement `garde_forcee` est
  compté. Quand la garde est active, le verdict REMPLACE l'heuristique de
  sous-chaîne (« contredit ») de la boucle pour l'événement CONTRADICTION ;
  niveau complété et game over restent tranchés par l'environnement, jamais par
  le verdict.
- **Mode `state`.** Le pas suivant une action présente prédit-contre-observé dans
  son invite et exige la ligne `VERDICT: …` avant le bloc JSON, extraite comme la
  prédiction (H16.2). Absente → l'action du pas est retenue et l'erreur nommée
  revient au pas suivant ; au-delà du budget par tour, l'issue prudente
  s'applique comme en mode `transcript`. Le premier pas d'un run, sans prédiction
  antérieure, n'exige pas de verdict.

**H16.4 — Garde de persistance.** Une connaissance non écrite est une connaissance
perdue : à chaque complétion de niveau, game over ou intervention du superviseur,
la mise à jour de `GUIDE.md` est exigée avant de poursuivre.

- **Mode `transcript`.** L'événement arme la garde ; l'invite qui suit (Evaluation
  ou Bug-Fixing, où les outils de notes sont exposés) porte la demande nommée
  (`prompts.GARDE_PERSISTANCE`). Les outils d'action restent verrouillés — la
  prochaine Implementation est refusée et redemandée, comme en H16.1 — tant
  qu'aucun `note_write` sur `GUIDE` n'a eu lieu depuis l'événement (compteur
  d'écritures monotone porté par `Notes`, jamais une comparaison de contenu : une
  réécriture à l'identique est une confirmation explicite et satisfait la garde).
  Budget de redemandes épuisé → tour clos sans action, compté, tour suivant
  redemande.
- **Mode `state`.** Satisfaite par construction : Σ est persisté après chaque pas
  validé (§H15.5, `Workspace.ecrire_etat`) et le contrat du mode (§H15.8,
  `tools=None`) ne porte aucune surface d'écriture de notes. La garde ne
  s'applique que là où une surface d'écriture existe.

**H16.5 — Observabilité et preuves.** Chaque décision de garde écrit un événement
`garde` dans `metrics.jsonl` (H11.2) : `garde` ∈ {documentaire, prediction,
evaluation, persistance}, `issue` ∈ {satisfaite_apres_redemande, redemandee,
tour_clos, forcee} — le chemin nominal (artefact présent du premier coup) n'écrit
rien, pour ne pas noyer les métriques. Le bilan de run compte les redemandes
totales. Preuves exigées (U30) : unitaires par garde (refus nommé quand l'artefact
manque, passage quand il est là, budget épuisé → issue écrite ici), intégration
sur `cible` (partie jouée sous gardes, artefacts dans le workspace), E2E rejeu
(cassettes régénérées sous gardes), et comparaison avant/après gardes sur `cible`
(`AVO_GARDES=false` contre `true`, comportement observé du harnais — jamais un jeu
officiel particulier).
