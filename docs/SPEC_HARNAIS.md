# Spécification du harnais AVO — noyau agent

Référence stable pour les commentaires `@spec` : `docs/SPEC_HARNAIS.md §Hn`.
Unités de backlog couvertes : U3–U15 (voir `docs/BACKLOG.md`).
Sources faisant foi : exports de `knowledge/` (papier AVO arXiv:2603.24517, billet NVIDIA
2026-08-21, page VISTA, papier Tycho arXiv:2607.28287). En cas d'écart entre cette
spécification et une source, la source fait foi et l'écart se consigne dans
`docs/INCONSISTENCY_REPORT.md`.

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
| `AVO_RUNS_DIR` | racine des artefacts | `runs/` |
| `ARC_API_KEY` | API ARC Prize (SPEC_ARCAGI3) | requis pour le live uniquement |
| `ARC_BASE_URL` | base API ARC | `https://three.arcprize.org` |

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

**H4.5 — Retries.** Uniquement `ServerError` et `TransportError` : **jusqu'à trois
nouvelles tentatives après l'échec initial**, soit quatre requêtes au plus, avec des
attentes de 1 s, 4 s et 16 s affectées d'un jitter de ±25 %. Jamais sur 4xx — un refus
d'authentification ou un dépassement de contexte se retenteraient à l'identique.
Chaque nouvelle tentative est journalisée (numéro, attente, motif).

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

**H8.3 — Bornes.** Deux bornes distinctes, car un niveau qui s'enlise et un jeu qui
s'éternise ne se diagnostiquent pas pareil : `AVO_ACTIONS_MAX_NIVEAU` et
`AVO_ACTIONS_MAX_JEU`. Généreuses par défaut, resserrées en campagne où elles sont
exigées (SPEC_ARCAGI3 §A7.1). Dépassement → arrêt propre du jeu, la borne franchie
étant nommée dans le rapport. Aucune temporisation arbitraire : on borne des actions,
jamais du temps d'horloge.

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
