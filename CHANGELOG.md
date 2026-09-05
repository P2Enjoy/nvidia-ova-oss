# CHANGELOG

## [Non publié]

### 2026-09-05 — U31 : le mode `state` annonce la forme d'appel des actions (prompts v1.10)

- Mesure (dépouillement des 25 jeux de la tranche 1) : 161 actions invalides
  pour 646 jouées (~20 % des appels de décision) — en mode `state`, aucun
  schéma d'outil n'atteignait le modèle, qui apprenait la forme d'appel en la
  violant.
- §H15.8 complété : la ligne « Actions disponibles » annonce les valeurs
  requises de chaque action, et un refus de résolution (nom inconnu, compte,
  type) se clôt par la forme complète attendue — le tout engendré des schémas
  déclarés au registre, jamais d'une liste codée.
- Preuves : 6 unitaires ajoutés (808 au total), cassettes E2E régénérées,
  campagne complète verte ; validation live sur le pire cas de la tranche 1 :
  actions invalides 25 → 4, actions valides 14 → 30 à budget identique
  (rapport `docs/rapports/u31-v110-tn36.md`).

### 2026-09-04/05 — U25 : campagne ARC officielle, tranche 1 TERMINÉE (25/25 jeux, rapport final agrégé)

- Les 25 jeux déclarés par `/api/games` ont tous été joués en live sous les
  plafonds du responsable (mode `state`, gardes actives, une invocation
  `run-arc` par jeu, un scorecard fermé par jeu), sur trois sessions
  planifiées chevauchées (suites 43 à 45).
- **Score global : RHAE 0,00 — aucun niveau complété (0/183).** Le plafond
  de temps (1 200 s/jeu) a lié sur les 25 jeux : ~25–30 s d'inférence par
  tour ≈ 37–46 tours, soit 10 à 57 actions par jeu, sous la baseline humaine
  du seul premier niveau de chaque jeu. Coûts agrégés : 1 027 appels,
  ~10,0 M tokens de prompt, ~0,5 M générés, ~8,0 h d'inférence.
- Rapports committés : un par jeu (`docs/rapports/u25-t1-<jeu>.md`) et le
  rapport final agrégé comparatif `docs/rapports/u25-t1-final.md` (A7.3).
- Incident nommé : `tu93-0768757b` joué en double par deux sessions
  chevauchées avant l'introduction du protocole anti-collision (marqueurs
  EN COURS dans le backlog) ; le doublon est conservé comme mesure
  (`u25-t1-tu93-bis.md`) et n'entre pas dans les agrégats.
- L'ordre du listing `/api/games` s'est révélé instable d'un jour à l'autre :
  la tranche fait foi par l'ensemble des jeux joués, consigné au backlog.
- U25 passe à `[x]` ; toute nouvelle campagne relève du cycle U31 et de son
  déclencheur.

### 2026-09-03 — U29c2 : banc c joué par la boucle complète — adaptateur, CLI `banc tau`, utilisateur simulé par second LLM, série de référence pass 8/10

- Adaptateur du banc τ (`src/avo/bancs/tau/adaptateur.py`) : huit outils de
  dialogue et de base (étiquette `action`, paramètre `prediction`), contexte
  de tâche portant la politique intégrale (§S18.2), schéma de Σ `service`
  (§S18.3), évaluation à la clôture et relevé écrit même sur incident (jamais
  de succès sur un épisode interrompu).
- Utilisateur simulé : `scripte` déterministe en replay, `llm` en live —
  réponses par un second LLM sur le même endpoint (appels séquentiels),
  premier message scripté pour garder les épisodes comparables (§S16.3).
- Dispatch CLI `banc tau --env detail` avec refus nommés de
  `--bruit`/`--derive`/`--executeur` (§S18.4).
- Preuves : 18 unitaires ajoutés, intégration en rejeu HTTP réel
  (`tests/integration/test_banc_tau_sur_rejeu.py`), cassette E2E
  `e2e_banc_tau.jsonl` à double génération vérifiée + scénario CLI réel,
  campagne complète verte. Série de référence live §S17.3 complète (seeds
  1–10, `detail`, h20) : **pass = 8/10**, détail au journal (suite 40).

### 2026-09-03 — U29c1 : banc c, patron Sierra τ-Bench — base Détail outillée, scénario seedé, évaluateur d'état final (§S14–§S17)

- Spécification du banc c écrite et committée avant le code
  (`docs/SPEC_BANCS.md` §S14–§S19) : dialogue outil-agent-utilisateur, base
  SQLite outillée, politique métier donnée, intention seedée avec éligibilité,
  utilisateur simulé `scripte`/`llm`, évaluateur binaire sur l'état final,
  découpage U29c1/U29c2.
- `src/avo/bancs/tau/` : base Détail SQLite en mémoire seedée avec six outils
  et journal ordonné des événements (`domaine.py`), scénario — intention,
  éligibilité, état attendu, simulateur scripté déterministe (`scenario.py`),
  évaluateur des violations de politique et relevé (`score.py`).
- 26 preuves unitaires (`tests/unit/test_banc_tau.py`). L'adaptateur, la CLI,
  l'utilisateur `llm` et le premier relevé live arrivent avec U29c2.

### 2026-09-03 — U29b2 : banc b joué par la boucle complète — adaptateur, CLI `banc ctf`, exécution conteneurisée en live

- Adaptateur du banc CTF (`src/avo/bancs/ctf/adaptateur.py`) : outils `bash` et
  `soumettre` (étiquette `action`, paramètre `prediction` §H16.2), contexte de
  tâche §S12.2 (le cadre, jamais la famille ni la méthode), schéma de Σ `ctf`
  (§S12.3, cinq contenants transposés de la source), relevé `banc.json` écrit
  même sur incident.
- Dispatch CLI `banc ctf` (`--env <famille|aleatoire>`, `--executeur
  conteneur|processus`) : refus nommés de `--bruit`/`--derive` (§S8.3), de
  `processus` en mode live (§S10.3) et de `--executeur` sur le banc skillexec.
- Noyau, génériques et valables pour tout environnement : genre de champ de Σ
  `chaine` (§H15.9 — le scalaire textuel du papier, tel `working_dir`) ;
  résolution du champ `action` — un outil à UN paramètre requis reçoit le reste
  du texte verbatim, sans découpage (§H15.8) ; énoncé du terminal sans chemin
  d'hôte (§S10.1 — même observation quel que soit l'exécuteur).
- Preuves : 28 unitaires ajoutés (résolution verbatim, genre `chaine`,
  adaptateur et dispatch), intégration en rejeu HTTP réel
  (`tests/integration/test_banc_ctf_sur_rejeu.py`), cassette E2E
  `e2e_banc_ctf.jsonl` à double génération vérifiée et scénario CLI réel,
  campagne complète verte.

### 2026-09-03 — U29b1 : banc b, patron InterCode CTF — générateur, terminal confiné, relevé pass@1 (§S8–§S11)

- Spécification du banc b écrite et committée avant le code
  (`docs/SPEC_BANCS.md` §S8–§S13) : défis seedés en cinq familles solubles par
  construction (`fouille`, `encodage`, `archive`, `binaire`, `piste`),
  terminal bash confiné, pass@1 sur drapeau exact, découpage U29b1/U29b2.
- `src/avo/bancs/ctf/` : générateur de plans purs déterministes
  (`defis.py` — matérialisation séparée, métadonnées de recouvrement pour les
  preuves seules), environnement terminal (`terminal.py` — budget, capture,
  soumission incorrecte qui continue, refus de forme seuls `refusee`) avec
  deux exécuteurs (`processus` pour les preuves et le rejeu ; `conteneur`
  jetable, réseau coupé et ressources bornées, requis en live), relevé
  (`score.py`).
- 24 preuves unitaires (`tests/unit/test_banc_ctf.py`) : déterminisme,
  solvabilité canonique des cinq familles, exécution bash réelle, troncature
  et délai nommés, persistance fichiers sans persistance shell, capture,
  budget, relevé. L'adaptateur et la CLI arrivent avec U29b2.

### 2026-09-03 — U31 : l'amorce documentaire ouvre le message du pas tant que le champ de connaissances est vide (§H16.0.7, prompts v1.9)

- Mesuré (série live bruit 50 h25, sous protocole v1.8) : la phrase finale du
  protocole — dans le message système — perd contre une observation
  volumineuse : 5 runs sur 6 à bruit 50 perdaient leur premier pas sur la
  garde documentaire, contre 0 sur 3 à bruit 0 (dépôt seul, gradient : 0/6 à
  bruit 0, 0/3 à bruit 20, 2/3 à bruit 50).
- §H16.0.7 complété : tant que « hypotheses » de Σ est vide — la condition
  exacte de la garde §H16.1 —, le message du pas s'ouvre sur un rappel d'une
  ligne de l'exigence ; il disparaît dès la première hypothèse écrite, et
  l'erreur nommée d'un pas refusé garde la primauté en tête (§H16.0.6).
  Prompts v1.9, 2 unitaires, cassettes E2E régénérées.

### 2026-09-03 — U31 : l'exigence documentaire clôt le protocole du mode `state` (§H16.0.7, prompts v1.8)

- Mesuré (série live bruit 20 h25) : le premier pas était refusé par la garde
  documentaire chaque fois que la première observation ne laissait aucune
  incertitude réelle (2/2 runs d'un environnement, 0/3 de l'autre) — le patch
  t01 suivait à la lettre la consigne finale de parcimonie et omettait
  l'hypothèse exigée trois phrases plus tôt.
- §H16.0.7 complété : l'exigence documentaire est la phrase FINALE du
  protocole, énoncée comme la seule exception à la parcimonie. Prompts v1.8,
  test unitaire de position finale, cassettes E2E régénérées.

### 2026-09-03 — U31 : le patch annulé d'une action refusée est rappelé verbatim au pas suivant (§H15.8)

- Mesuré (série live h25 bruit 20, dépôt s2-v2, cascade de 9 invalides) : le
  modèle rejoue une action refusée en corrigeant Σ dans le même pas, et
  l'annulation atomique (§H15.8, suite 24) jette la correction avec l'action —
  la boucle qu'elle devait casser se ré-enseigne (8 refus « occupée »).
- §H15.8 (point tranché) : l'annulation reste — Σ n'enregistre jamais l'effet
  d'une action non exécutée — mais le prompt du pas suivant rappelle le patch
  annulé verbatim (action nommée, JSON tel quel) avec l'instruction générique de
  réinscrire ce qui y décrit la situation indépendamment de l'action refusée.
  C'est le modèle qui décide de ce qui survit, jamais le harnais. Rappel borné,
  omis sur patch vide, présent au seul pas qui suit le refus. Prompts v1.7.
- Preuves : 4 unitaires dédiés (rappel verbatim au pas suivant, omission sur
  patch vide, non-survie au-delà d'un pas, remplacement par un nouveau refus) ;
  cassettes E2E inchangées et vertes — le rappel n'apparaît sur aucun chemin
  nominal.

### 2026-09-02 — U31 : la garde d'évaluation lit la qualification réellement exprimée (§H16.3 : trois issues dont « caduque ») et le dépôt lit la notation `PR_k` (§S4.2)

- Mesuré (série live h25 bruit 20, 5 runs complets) : 18 refus de verdict dont
  17 portaient une qualification EXPLICITE refusée par la lecture stricte —
  8 « non applicable » (l'événement suivant avait rendu la prédiction sans
  objet), 6 verdicts en milieu de ligne ou en prose, 1 faute de frappe ; et
  3 des 5 invalides du dépôt s2 sont des `merge` en notation `pr_3`/`PR_5`
  (tiret bas), forme imposée par les clés JSON de Σ et par les noms d'objets de
  l'environnement lui-même (`branche_4`).
- §H16.3 (point tranché) : trois issues de qualification — `confirmee`,
  `contredite` (famille `infirm*` incluse), `caduque` (famille `caduc*`,
  « non applicable », « n/a ») ; le jeton se lit où qu'il soit dans la réponse ;
  deux familles contradictoires = qualification ambiguë, redemandée. `caduque`
  ne déclenche pas Bug-Fixing et se compte à part (`issue: "caduque"`, §H16.5).
  Prompts v1.6 : les trois valeurs annoncées d'emblée.
- §S4.2 (tranché étendu) : le séparateur tiret bas après le préfixe `PR` se lit
  (`PR_5`, `pr_3`) ; `pr:3` reste invalide nommée.

### 2026-09-02 — U31 : le protocole du mode `state` annonce d'emblée l'exigence documentaire et l'enseignement d'un refus (§H16.0.7)

- Mesuré (série live entrepôt h25 bruit 5, seeds 1–3) : 3 runs sur 3 perdent
  leur premier pas sur la garde documentaire — l'exigence « hypotheses non vide
  avant d'agir » n'était annoncée que par le message de refus ; et 17 actions
  invalides sur deux runs répètent des refus jamais répercutés dans Σ (un même
  couple patch+action refusé trois fois ; un fait démenti par un refus
  ré-affirmé six tours plus tard).
- Le protocole engendré (§H15.9) énonce désormais les deux règles : « tant que
  « hypotheses » est vide, aucune action n'est jouée — ta première réponse
  écrit au moins une hypothèse » ; « un refus te renseigne : il nomme le point
  sur lequel Σ est faux — le patch du pas suivant corrige Σ d'après ce
  message ». Prompts v1.5, aucun terme d'environnement.
- Preuves : 2 unitaires dédiés (`test_etat_schema`), suite unitaire complète
  verte (693), cassettes E2E régénérées, 6 E2E verts.

### 2026-09-02 — U31 : la résolution du dépôt instruite — le moteur lit sa propre notation de PR (§S4.2) et « cle=valeur » est normalisé (§H15.8)

- Mesuré (série live dépôt h25 bruit 5, seeds 1–2) : les 9 actions invalides des
  deux runs sont TOUTES des `merge` joués au bon événement sur la bonne PR,
  refusés sur la seule notation du numéro — le modèle recopie la notation que
  l'environnement affiche (« PR #3 », « PR 5 ») ou emploie la syntaxe d'argument
  nommé (« pr=2 »). La résolution basse du dépôt (0–0,4) n'était ni un `merge`
  prématuré ni une `ci_verte` manquée.
- Moteur du dépôt (§S4.2, point tranché) : `merge` lit désormais la notation que
  l'environnement émet lui-même — entier nu, « #k », préfixe « PR » à casse
  indifférente avec ou sans espace ni croisillon ; toute autre forme reste une
  action invalide nommée qui consomme l'événement.
- Noyau (§H15.8) : quatrième bruit de format normalisé — une valeur
  « cle=valeur » dont « cle » est exactement le paramètre requis que sa position
  destine se lit comme « valeur » ; toute autre égalité reste une valeur.
- Preuves : 3 unitaires de résolution + 2 unitaires du moteur (5 formes lues,
  3 restant invalides nommées), suites concernées vertes.

### 2026-09-02 — U31 : la redemande de garde du mode `state` énonce la forme complète attendue (§H16.0.6)

- Mesuré (journal, suite 24) : quand un pas devait porter les deux lignes
  `VERDICT:` puis `PREDICTION:`, la redemande ne nommait que la ligne absente —
  le modèle produisait celle-là et perdait l'autre (quatre redemandes alternées
  sur un même tour, 2 à 9 par run). Le message de refus des gardes du mode
  `state` se clôt désormais TOUJOURS par la forme complète de la réponse
  attendue (ligne `VERDICT:` quand une prédiction attend sa qualification, avec
  ses deux seules valeurs reconnues, ligne `PREDICTION:`, bloc JSON), les
  manques restant nommés en tête (`prompts.forme_pas_attendue`, prompts v1.4).
- Preuves : 2 unitaires dédiés (`test_gardes`), suite gardes 20/20, lint, mypy.

### 2026-09-02 — U32 : limitation de concurrence des requêtes LLM par endpoint (§H4.9)

- Le harnais impose lui-même le plafond de requêtes simultanées que tolère le
  port public de l'endpoint (instruction du responsable : 3) : jetons de
  fichiers par endpoint (`avo.llm.concurrence`), un jeton tenu par tentative
  HTTP, l'excédent PATIENTE (scrutation avec jitter, bornée par `AVO_TIMEOUT_S`)
  au lieu d'échouer en rafales de 500 ; jeton d'un occupant mort repris après
  péremption. Actif en mode live uniquement ; `AVO_LLM_MAX_CONCURRENT=0`
  désactive, `AVO_LLM_SLOTS_DIR` pointe un chemin partagé pour coordonner
  plusieurs processus ou sessions d'un même hôte.
- `HTTP 429` devient `RateLimited`, retentée comme une panne serveur en
  honorant `Retry-After` quand il dépasse le palier §H4.5 — prêt pour une file
  d'attente côté serveur ; la garantie entre machines isolées reste côté
  serveur (nommé hors périmètre en U32).
- Preuves : 20 unitaires (`test_llm_concurrence`), 1 intégration (jeton tenu
  pendant la requête HTTP réelle contre le rejeu), campagne complète.

### 2026-09-02 — U31 : action refusée par l'environnement = patch annulé (§H15.8, drapeau `refusee`)

- L'issue d'une action peut désormais déclarer `refusee` (faux par défaut,
  contrat §H8.2) : vrai quand l'environnement a refusé l'action — elle n'a
  rien exécuté. En mode `state`, le `state_patch` du même pas est alors ANNULÉ :
  Σ et le workspace reviennent à l'avant-pas, la ligne d'archive porte le patch
  annulé avec `patch_annule: true` (§H15.10), et le pas suivant lit le refus
  dans l'issue rappelée. Un environnement qui ne déclare pas le drapeau se
  comporte comme avant ; l'adaptateur du banc expose `refusee = not valide`
  (§S6.1), le fil ARC ne refuse jamais (`IssueArc.refusee = False`).
- Motif mesuré (journal suite 24, h25 bruit 0 entrepot seeds 1–3) : 21 des
  22 actions refusées de la série portaient un patch inscrivant dans Σ l'effet
  attendu d'une action qui n'a pas eu lieu — chaque faux fait causant l'erreur
  suivante (cascades de 9 à 11 invalides, scores 0,48 et 0,52 contre 0,96 pour
  le run sans cascade). Même principe que le pas blanc des gardes (§H16.1).
- Le protocole engendré énonce la règle ; cassettes E2E régénérées
  (`make seed-e2e`, double génération vérifiée), pile relancée.
- Preuves : 664 unitaires (6 nouveaux : annulation, conservation sur action
  acceptée, environnement sans drapeau inchangé, protocole, adaptateur
  entrepôt valide/invalide), 152 intégration, 6 E2E, lint, mypy strict, build.

### 2026-09-02 — U31 : le vidage d'« hypotheses » se conserve au lieu d'invalider le patch (H16.1 révisé)

- Un patch qui vide le champ commun `hypotheses` alors qu'il est non vide
  (liste vide ou `null`) n'est plus un `EtatInvalide` à rollback-retry : le
  champ est conservé, le reste du patch s'applique, l'action du pas joue, et
  la ligne d'archive du pas porte `hypotheses_conservees: true` (§H15.10).
- Motif mesuré (ligne de base h25 bruit 0, code suite 21+22) : traité en
  retry, le vidage a tué en `RetriesEpuises` un run dont toutes les actions
  étaient correctes (s1) et coûté 12 relances sur un autre (s2, 11 vidages) —
  dans un mode sans mémoire, la relance n'enseigne rien d'un tour à l'autre.
- Preuves : unitaires du runtime (conservation par liste vide et par `null`,
  reste du patch appliqué), intégration en HTTP réel (action jouée, Σ
  conservé, archive), lint, mypy strict.

### 2026-09-02 — U29a4 : client streamé livré (`stream: true`, cassettes régénérées, lecture partagée des deux formes)

- La requête `/api/chat` part désormais en `stream: true` (§H4.2) : les
  en-têtes arrivent au premier fragment et la limite de 40 s du pont 443 ne
  s'applique plus à la durée de génération. Cadrage HTTP uniquement — le
  transport lit toujours le corps jusqu'au bout, l'interface `LLMClient.chat`
  et la boucle sont inchangées.
- Cassettes régénérées par les commandes du dépôt (§H4.7) : `make seed-e2e`
  (double génération vérifiée) et `make record-llm` sur le vrai endpoint — les
  corps 2xx de conversation y sont désormais du NDJSON servi tel quel, les
  erreurs 401/413 sont inchangées, aucun secret.
- L'assemblage des fragments est extrait en `fusionner_fragments` (§H4.3,
  une seule implémentation) et le module cassette sait lire une conversation
  enregistrée sous les deux formes (`enveloppe_conversation`,
  `premiere_conversation`) : six décors de test dédupliqués, rejeu comparé
  sur les octets servis, détection de dérive live étendue aux corps streamés.
- Preuves : 657 unitaires (6 nouveaux sur la lecture des deux formes),
  151 intégration, 6 E2E sur pile relancée, lint, mypy strict ;
  enregistrement live du contrat réussi en streaming (7 échanges).

### 2026-09-02 — U29a4 : corps `/api/chat` assemblé en deux formes, préalable du client streamé (H4.2/H4.3)

- Le client assemble désormais un corps 2xx en `ChatResult` sous DEUX formes :
  objet JSON unique (réponse non streamée) ou lignes NDJSON (réponse streamée) —
  `content`/`reasoning` concaténés, `tool_calls` collectés, compteurs du fragment
  final. Un flux sans fragment final ou tronqué est une `TransportError` retentée ;
  un fragment portant `error` est une `ServerError` retentée.
- Motif mesuré (campagne de banc h25, 2026-09-02) : le pont 443 coupe à 40 s
  avant premiers en-têtes ; en `stream: false` toute génération dépassant 40 s
  meurt en 500 et ses relances butent au même mur (reproduit quatre fois au pas
  de dérive du Dépôt logiciel). La bascule `stream: true` (§H4.2 amendé) suit,
  avec régénération des cassettes.
- Preuves : 9 unitaires d'assemblage (fragments, formes uniques, troncatures,
  erreur en cours de flux, retry), lint, mypy strict.

### 2026-09-02 — U31 : refus de garde = pas blanc atomique, `hypotheses` non vidable (H16.1)

- Mode `state` : quand une garde retient l'action d'un pas, le `state_patch` du
  même pas est ANNULÉ avec elle — Σ et le workspace reviennent à l'état d'avant
  le pas. Motif mesuré (`pas.jsonl`, journal suite 21) : le patch d'un pas
  retenu porte l'effet attendu d'une action jamais jouée ; l'acquérir faisait
  mentir Σ et coûtait les pas suivants (un `wait` indu puis une action
  invalide sur le seul run archivé).
- Le champ commun `hypotheses` ne se vide plus en cours de run : liste vide ou
  `null` sur un champ non vide est un `EtatInvalide` nommé (retry immédiat de
  §H15.4, gratuit en événements) ; l'ouverture (vide → vide) reste permise.
  Motif mesuré : le modèle « nettoyait » ses hypothèses caduques par `[]`, ce
  qui réarmait la garde documentaire — jusqu'à 11 refus sur 25 appels d'un run.
- Le protocole engendré énonce la règle (« remplace une hypothèse périmée par
  sa révision ») — prompts 1.3, cassettes E2E régénérées.
- Preuves : 642 unitaires (dont vidage refusé, remplacement permis, annulation
  du patch sous refus), 151 intégration, 6 E2E, lint, mypy.

### 2026-09-02 — U31 : le schéma de Σ est déclaré par le domaine (H15.9)

- Le noyau ne possède plus la liste des champs de Σ : il possède les GENRES
  (`position`, `entier_positif`, `liste_chaines`, `liste_objets`,
  `dictionnaire`), leur validation, l'opérateur ⊕ et la persistance ; chaque
  domaine déclare son schéma une fois (`SchemaEtat`, papier SKILL.state §3.1),
  porté par `Contexte.schema_etat`. `arc-v1` reste le défaut sans déclaration.
- Genre `dictionnaire` fusionné clé par clé avec retrait sur `null` — l'opérateur
  du papier (§3.2, exemple B.3) : le modèle n'a plus à réémettre l'objet entier.
- Le protocole du pas est engendré depuis le schéma (`prompts.protocole_etat`,
  prompts 1.2) ; Σ persisté se relit sous son schéma ; le relevé `banc.json`
  porte `schema_etat`.
- Banc a : schémas `banc-entrepot-v1` (`inventaire`, `en_attente`) et
  `banc-depot-v1` (`branches`, `prs`) déclarés par l'adaptateur (§S6.5). Motif
  mesuré (journal, suite 20) : sous le schéma ARC imposé, le modèle n'avait
  aucun champ où tenir « tel article sur telle étagère ».
- Preuves : 12 unitaires (`test_etat_schema.py`), intégration (Σ du banc sous son
  schéma), cassettes E2E régénérées (ARC `state` et banc), campagne complète.

### 2026-09-02 — U29a4 : dérive d'état et mesure de récupération (condition 3)

- Le banc a porte la condition 3 de la source (Experiment 3, « state
  recovery ») : `python -m avo banc skillexec … --derive` place UNE dérive
  d'état externe dans l'épisode — Entrepôt : un opérateur externe déplace un
  article (§S3.8) ; Dépôt : un commit direct casse la CI d'une branche prête à
  fusionner (§S4.7) — signalée par une alerte non structurée sous
  `--- ALERTE EXTERNE ---`, seul canal qui dise la vérité au pas porteur.
- Le relevé `banc.json` mesure la récupération (§S5.5) : `derive_evenement`,
  `pas_de_recuperation` (0 = récupération immédiate, null = jamais récupéré),
  `recupere` ; la CLI l'annonce en fin d'épisode.
- Les contextes de tâche nomment le canal d'alerte (§S6.2) ; les cassettes E2E
  du banc sont régénérées en conséquence (double génération vérifiée).
- Preuves : 14 unitaires (génération, application réelle, divergence, mesure),
  intégration en rejeu HTTP (politique parfaite lisant l'alerte, récupération
  0), campagne complète verte. Premiers relevés live consignés au journal
  (6 épisodes h10, deux environnements, tous récupérés en 0 à 3 pas).

### 2026-09-01 — U29a4 : le Dépôt logiciel branché à l'adaptateur et à la CLI (§S6)

- L'adaptateur du banc a joue désormais les DEUX environnements :
  `python -m avo banc skillexec --env depot …` monte la boucle complète sous
  gardes sur le Dépôt logiciel, avec son contexte de tâche (protocole §S4.2 et
  §S4.5 donné à l'agent) et ses cinq outils étiquetés `action`
  (`commit`, `create_pr`, `merge`, `fix_ci`, `wait`). Mécanique de boucle
  factorisée en base commune : composition de l'observation, issue et motif de
  fin identiques dans les deux environnements, par construction.
- Le relevé `banc.json` porte l'environnement joué et, pour le dépôt, la
  résolution B.1 (`resolution`, `demandes_resolues`, `demandes_jugees`), relevé
  d'incident compris.
- Le numéro de PR de `merge` arrive en texte : « 3 » et « #3 » se lisent, un
  numéro imprenable est une action invalide NOMMÉE qui consomme l'événement
  (§S4.6), jamais une erreur obscure avant l'environnement.
- Preuves : 18 unitaires (`tests/unit/test_banc_adaptateur_depot.py`),
  intégration en rejeu HTTP réel à deux passes avec résolution exacte
  (`tests/integration/test_banc_depot_sur_rejeu.py`), cassette E2E seedée
  `e2e_banc_depot.jsonl` (double génération comparée ; la cassette Entrepôt
  régénérée est identique octet pour octet — la refactorisation ne change pas
  la boucle) et scénario CLI réel sur pile compose. Campagne complète verte
  (lint, mypy strict, 610 unitaires, 149 intégration, 6 E2E, build).
- Premiers relevés live du dépôt consignés au journal (h10, seeds 1–3, bruit 0
  et premier point bruit 5).

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
