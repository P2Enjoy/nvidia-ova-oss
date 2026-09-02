# Journal du projet

Trace chronologique des décisions et investigations significatives. La dernière entrée dit toujours où reprendre.

---

## 2026-08-27 — Étude des sources, import dans `knowledge/`, préparation du travail sur le harnais AVO

**Contexte.** Session interactive demandée par le responsable, sur la branche désignée `claude/avo-harness-implementation-ufsb43`. Mission énoncée : (1) lire et exporter dans `knowledge/` (markdown + images) les quatre sources qui définissent l'objet du dépôt ; (2) se préparer à implémenter le harnais AVO d'après la spécification du papier et à l'évaluer sur des benchmarks via un endpoint compatible OpenAI dont l'URL et la clé API seront fournies ultérieurement. Aucun code à écrire à ce stade.

**Problème.** Le dépôt était la base « software factory » vierge (un seul commit) : aucun contenu projet, la finalité n'existait que dans l'énoncé de mission. Une décision non persistée étant une décision perdue, tout ce qui a été appris et décidé ici est écrit dans le dépôt.

**Observations (étude des sources).**

- **AVO** (arXiv:2603.24517, NVIDIA) est la spécification à implémenter : un opérateur de variation agentique pour la recherche évolutionnaire, `Vary(Pₜ) = Agent(Pₜ, K, f)`. Boucle interne Planning → Implementation → Evaluation → Bug-Fixing ; agent de codage généraliste avec outils (édition de code, shell, navigation fichiers, consultation de documentation), mémoire persistante par historique de conversation ; lignée single-lineage où chaque version validée (correcte ET au moins aussi bonne que le meilleur score committé) devient un commit git avec son score ; **superviseur** séparé qui détecte stagnation/cycles improductifs et redirige la recherche (intervention conditionnelle). Le papier démontre AVO sur l'optimisation de kernels d'attention B200 ; l'architecture est explicitement indépendante du domaine.
- **Blog NVIDIA (2026-08-21)** : la même architecture appliquée à ARC-AGI-3 fait 100.00 RHAE (25 jeux publics, 183 niveaux, 6 624 actions, Claude Opus 5). Configuration décisive pour nous : interface de tâche réimplémentée **selon les principes direct-interaction de VISTA**, mais en **texte seul** — chaque observation est la grille 64×64 exacte, aucune image envoyée au modèle ; actions disponibles fournies sans description des règles ni du but. AVO est annoncé multi-modèles (démonstrations Opus 5 et GPT-5.6 Sol).
- **VISTA** (MIT) : harnais minimaliste sans synthèse de programme — perception (PNG 512×512 ou grille texte), raisonnement en langage libre, mémoire visuelle sans perte (`inspect`, `read_pixels`), notes `GUIDE.md`/`WORKING.md`, continuation en contexte frais à l'approche de la limite de contexte. Le prompt agent complet est dans l'export. Résultats par jeu et par niveau exportés (Opus 5.0 : 100.00 RHAE, 7 542 actions).
- **Tycho** (NIMI) : l'approche concurrente par modèles du monde programmatiques (que NVIDIA n'a pas retenue). Précieux pour nous : formalisation propre d'ARC-AGI-3 (machines de Moore rendues, protocole de score, **définition exacte de RHAE** : eₗ = min(115, 100·(hₗ/aₗ)²) si complété, pondération wₗ = ℓ, plafonnement par la complétion), comparaison de quatre politiques d'orchestration, surface d'outils et extraits de prompts, diagnostics et coûts d'inférence.

**Décisions.**

1. `knowledge/` est le dossier de référence : quatre exports markdown autoporteurs, images sous `knowledge/images/<source>/`, PDF d'origine sous `knowledge/pdf/`, index `knowledge/README.md` avec provenance et synthèse. Les exports sont des instantanés en lecture seule.
2. Figures des PDF extraites par recadrage ancré sur les légendes (script reproductible en session) ; les valeurs numériques des graphiques à barres du papier AVO ont été reconstruites en tableaux sous les figures, vérifiées contre les pourcentages annoncés dans le texte.
3. Les vidéos `.mp4` de la page VISTA ne sont pas mises en miroir (la demande porte sur markdown + images) ; l'export garde des liens absolus vers le site.
4. Documentation projet initialisée (README réécrit, CHANGELOG, BACKLOG, DAT embryonnaire, CLAUDE_PROJECT.md) ; le plan de travail vit dans `docs/BACKLOG.md`, pas dans la mémoire de session.
5. Aucune ligne de code du harnais avant la spécification écrite et committée (unité U2), conformément à `CLAUDE.md` §5.

**Vérifications réalisées.** Les 4 URL ont répondu 200 et les contenus téléchargés correspondent (titres, auteurs, chiffres croisés entre sources : les actions AVO/VISTA/Tycho citées par le blog concordent avec les exports). Tous les liens d'images relatifs des markdown de `knowledge/` résolvent vers un fichier existant (vérification scriptée). Les recadrages de figures ont été inspectés visuellement (fig. 1–2 AVO, fig. 1 et 12 Tycho lisibles et complets).

**En attente du responsable (bloquant pour la suite).**

- URL de l'endpoint compatible OpenAI, clé API, **nom du modèle** à utiliser.
- Confirmation du périmètre « common benchmarks » : ARC-AGI-3 est le benchmark central des sources (nécessite l'API ARC Prize pour un scorecard officiel) ; préciser s'il faut d'autres benchmarks (par ex. SWE-bench-like, optimisation de code) et lesquels sont accessibles depuis cet environnement.

**Où reprendre.** Unité U2 du backlog : rédiger la spécification complète du harnais (architecture, contrat de configuration par variables d'environnement, interface de tâche, protocole d'évaluation, plan de tests) dans `docs/`, la committer, PUIS seulement commencer le code (U3+), une fois l'endpoint fourni.

---

## 2026-08-27 (suite) — Test de l'endpoint d'inférence : serveur sain, mais injoignable depuis cet environnement (sortie limitée au port 443)

> **Résolu le 2026-08-27 (suite 2).** Le blocage décrit ci-dessous était propre à l'environnement d'exécution d'alors (sortie TLS limitée au port 443), pas au serveur. Depuis l'environnement de travail actuel, l'endpoint est joignable et a été testé de bout en bout : voir l'entrée suivante, qui fait foi. Les options de déblocage listées plus bas sont sans objet.

**Contexte.** Le responsable a fourni les valeurs `OLLAMA_HOST` (URL https avec port non standard), `OLLAMA_API_KEY` et `OLLAMA_CONTEXT_LENGTH=114688`, avec pour consigne : « before anything, test this endpoint works ». Les valeurs sont conservées hors dépôt (`.env` local, ignoré par git ; vérifié par `git check-ignore`).

**Problème.** Toute connexion TLS vers l'endpoint échoue depuis cet environnement : le tunnel CONNECT du proxy s'établit, le ClientHello part, aucun octet TLS ne revient, reset après ~6 s. Identique avec/sans SNI, en TLS 1.2 forcé, sur 3 tentatives espacées.

**Hypothèses testées et observations (toutes mesurées ce jour).**

1. *Proxy de l'environnement en panne ?* Non : `https://arxiv.org` répond 200 en 0,37 s ; statut du proxy sain.
2. *Serveur en panne pour tout le monde ?* Non : depuis 5 points de mesure externes (check-host.net : BG, DE ×2, IL, US), le port TCP de l'endpoint accepte la connexion en 0,06–0,48 s ; en HTTPS complet depuis 4 nœuds externes (ES, FI, IT, TR), le handshake TLS aboutit et le serveur répond `404` sur `/` ; en HTTP clair il répond `400` (comportement classique d'un port TLS). **Le service est donc debout et sert TLS au public.** Des nœuds hébergés en datacenter (Hetzner, Miami) passent : pas de filtrage anti-datacenter côté serveur.
3. *Filtrage IP côté serveur contre notre IP de sortie ?* Non prouvé et devenu inutile comme explication : voir 4.
4. *Politique de sortie de l'environnement ?* **Oui — cause établie.** Test discriminant : `www.cloudflare.com:443` → handshake TLS 1.3 complet ; `blog.cloudflare.com:2053` (port HTTPS alternatif officiel de Cloudflare, joignable publiquement) → même échec silencieux que l'endpoint ; `1.1.1.1:853` (DoT) → idem. **La sortie réseau de cet environnement n'autorise le TLS que vers le port 443.** Tout port non standard est bloqué, quel que soit l'hôte.
5. *Et le port 443 de l'hôte de l'endpoint ?* Fermé pour tout le monde (timeout depuis 4 nœuds externes) : il n'est simplement pas exposé/redirigé sur la box.

**Conclusion.** Le serveur d'inférence fonctionne, la clé n'a pas pu être testée (aucun octet applicatif échangé), et le blocage est structurel : l'endpoint écoute sur un port non-443 alors que l'environnement ne sort qu'en 443. Aucune modification du serveur du responsable n'a été tentée.

**Options de déblocage (nécessite une action humaine), au choix :**

1. Exposer le même reverse-proxy TLS sur le **port externe 443** de la box (redirection 443 → service TLS existant) et utiliser `OLLAMA_HOST=https://<hôte>` sans port ;
2. Mettre l'endpoint derrière un tunnel type **Cloudflare Tunnel** (hostname public en 443, IP du domicile masquée) ;
3. Vérifier dans les réglages de l'environnement Claude (claude.ai → environnements, politique réseau) si un niveau d'accès autorisant les ports non standard existe.

Pour référence si un filtrage IP apparaissait ensuite : IP de sortie observée `160.79.106.137`, dans la plage de sortie publiée par Anthropic `160.79.104.0/21` (docs.claude.com/en/api/ip-addresses).

**Vérifications réalisées.** Toutes les mesures ci-dessus exécutées ce jour depuis l'environnement (curl, openssl s_client via proxy, check-host.net) ; rapport externe permanent : check-host.net/check-report/49080edck800.

**Où reprendre.** Dès que l'endpoint est joignable en 443 : rejouer le test (version serveur, liste des modèles `/v1/models` et `/api/tags`, complétion `/v1/chat/completions`, `/api/show` pour la fenêtre de contexte), consigner les résultats ici, puis enchaîner sur U2 (spécification du harnais).

---

## 2026-08-27 (suite 2) — Endpoint joignable et validé de bout en bout ; trois contraintes mesurées qui dimensionnent le harnais

**Contexte.** Le responsable a re-fourni les trois valeurs (`OLLAMA_HOST`, `OLLAMA_API_KEY`, `OLLAMA_CONTEXT_LENGTH=224000`, cette dernière relevée depuis les 114688 de l'entrée précédente) avec la même consigne : « before anything, test this endpoint works ». Test rejoué depuis l'environnement de travail courant, conformément au « Où reprendre » de l'entrée précédente.

**Problème posé.** L'entrée précédente concluait à un serveur sain mais injoignable, la clé n'ayant jamais pu être éprouvée. Il fallait donc établir (1) si le blocage subsistait, (2) si la clé est valide et le contrôle d'accès réel, (3) si la fenêtre de contexte annoncée est effectivement exploitable.

**Observations.**

1. *Joignabilité.* Résolution DNS en IPv6, TCP ouvert sur le port de l'endpoint, handshake TLS en 19 ms, `404` sur `/` (pas de route racine). Le blocage de l'entrée précédente était **propre à l'environnement d'exécution d'alors**, dont la sortie n'autorisait le TLS que vers le port 443 ; il ne concernait ni le serveur ni la configuration du responsable.
2. *Authentification réellement appliquée côté serveur.* `401 {"error":"clé API manquante"}` sans en-tête ; `401` avec une clé délibérément invalide ; `200` avec la clé fournie. Le contrôle n'est donc pas une simple façade : il a été vérifié par la négative, sur `/api/version` et `/v1/models`.
3. *Surfaces et version.* Ollama **0.32.14**. Les deux surfaces annoncées répondent : native (`/api/version`, `/api/tags`, `/api/show`, `/api/ps`, `/api/chat`) et compatible OpenAI (`/v1/models`, `/v1/chat/completions`). Devant Ollama, un reverse-proxy **Caddy** (HTTP/2, HSTS, `alt-svc` h3) qui porte l'authentification et les quotas.
4. *Modèles servis.* Deux, et **un seul utilisable comme modèle de raisonnement** : `qwen3.6:35b` (architecture `qwen35moe`, 36,0 B de paramètres, quantisation Q4_K_M, 23,9 Go, contexte natif 262 144, capacités déclarées `completion`, `tools`, `thinking`, `vision` ; défauts du Modelfile : `temperature 1`, `top_p 0.95`, `top_k 20`, `presence_penalty 1.5`, `min_p 0`). Le second, `all-minilm:latest`, est un modèle d'embeddings (BERT 23 M, contexte 512, dimension 384) : hors périmètre du harnais, éventuellement utile à une mémoire vectorielle.
5. *Inférence.* Complétion simple aboutie (`/v1/chat/completions`, 6,6 s). **Tool calling fonctionnel** : `finish_reason: tool_calls` et arguments JSON bien formés sur un outil de type shell — prérequis dur pour la boucle AVO, donc vérifié explicitement.
6. *Fenêtre de contexte réellement chargée.* Une requête avec `num_ctx=224000` a provoqué un rechargement du modèle (17,1 s) puis répondu ; `/api/ps` confirme `context_length: 224000`, 26,56 Go **intégralement en VRAM**, aucun débordement CPU.
7. *Plafond par clé.* Une requête volumineuse est refusée en **HTTP 413** par le proxy avec un corps explicite : `{"tokens_estimated":248803,"tokens_with_margin":286124,"max_context_tokens":229376}`. Le plafond par clé vaut donc **229 376 tokens = 224 × 1024** — la valeur « 224000 » communiquée est en réalité **224 Ki tokens**. Le proxy applique de plus une **marge de 15 %** à sa propre estimation avant comparaison (286124 / 248803 = 1,15).
8. *Contexte long réellement exploitable.* Test aiguille-dans-botte-de-foin accepté à **201 287 tokens** de prompt réel (mesure `prompt_eval_count` du serveur), aiguille placée aux deux tiers et **correctement restituée**. Préremplissage : **493 tokens/s**, soit **6 min 48 s** pour ce seul prompt, contre une génération rapide derrière.

**Conséquences pour la conception (à trancher en U2).**

1. *Le coût dominant est le préremplissage, pas la génération.* À 493 tok/s, un harnais qui réémet l'historique complet à chaque tour paierait plusieurs minutes par action ; l'ordre de grandeur d'ARC-AGI-3 dans les sources (6 624 à 7 542 actions) rend cette conception inexploitable en temps. L'historique devra donc être strictement **append-only** pour bénéficier du cache de préfixe d'Ollama, et toute réécriture en tête de contexte (résumé inséré avant l'historique, réordonnancement, injection système tardive) doit être considérée comme un défaut de performance, pas comme un détail.
2. *Le budget utile est ~199 000 tokens, pas 229 376.* Viser le plafond nominal fait échouer la requête en `413` à cause de la marge de 15 %. Le harnais doit budgéter sur environ **199 000 tokens**, et traiter le `413` comme un cas nominal : le corps renvoie `tokens_estimated`, directement exploitable pour un repli (compaction ou continuation en contexte frais, à la manière de VISTA).
3. *Modèle à raisonnement : le `reasoning` consomme le budget de sortie avant tout contenu.* Avec `max_tokens: 64`, la réponse observée est `content: ''` avec `finish_reason: length`, les 64 tokens étant partis dans le raisonnement (exposé séparément dans `message.reasoning`). Il faudra soit budgéter large, soit désactiver le raisonnement (`think: false` sur l'API native, utilisé ici avec succès).

**Décisions.**

1. L'endpoint est validé pour le développement et l'évaluation ; le modèle de travail est `qwen3.6:35b` (seul modèle de complétion servi).
2. Les trois valeurs vivent dans un `.env` local en `chmod 600`, confirmé couvert par `.gitignore` (`git check-ignore` exécuté avant écriture). Ni URL réelle, ni clé, ni adresse d'infrastructure dans les fichiers committés.
3. Les mentions de blocage devenues fausses sont retirées de `README.md` et `docs/BACKLOG.md` dans le même commit que cette entrée ; l'entrée précédente du journal est marquée résolue sur place plutôt que réécrite, la chronologie du journal restant un historique.

**Vérifications réalisées.** Tous les chiffres ci-dessus sont des mesures effectuées ce jour depuis l'environnement de travail (curl sur les deux surfaces, `/api/ps` pour le contexte chargé, `prompt_eval_count` et `prompt_eval_duration` du serveur pour le débit, corps du `413` pour le plafond). Aucune modification du serveur du responsable n'a été tentée. Non vérifiés à ce stade : la capacité `vision`, la surface `/v1/embeddings`, le comportement en concurrence (plusieurs requêtes simultanées) et la stabilité du débit à plus de 201 k tokens.

**Décision complémentaire — périmètre des benchmarks (tranchée, plus en attente).** La section « Autonomie de décision » ajoutée ce jour à `CLAUDE.md` §1 retire l'attente d'arbitrage comme motif de suspension : une mention « à confirmer par le responsable » est le constat d'un travail non fait, pas une instruction d'attendre. Ce point est donc tranché ici.

- *Retenu* : **ARC-AGI-3, ensemble public**, seul benchmark du périmètre initial.
- *Motif* : le dépôt permet de le déduire, il ne s'agit donc pas d'un choix de produit indéductible (`CLAUDE.md` §1, « Demande d'arbitrage », cas 3). Les quatre sources de `knowledge/` convergent sur ce benchmark : c'est celui du billet NVIDIA, celui sur lequel AVO est démontré à 100.00 RHAE, celui de la page VISTA, et celui que le papier Tycho formalise, définition de RHAE comprise. Les valeurs de comparaison sont déjà dans le dépôt (AVO 100.00/6 624 ; VISTA 100.00/7 542 ; Tycho 100.00/6 641), ce qui rend le résultat interprétable sans donnée externe supplémentaire.
- *Écarté* : les benchmarks d'optimisation de code du papier AVO (kernels d'attention B200), qui exigent un matériel dont le projet ne dispose pas ; et l'ajout de benchmarks de type SWE-bench, qu'aucune source du dépôt ne rattache à AVO et qui dilueraient la comparaison au lieu de l'étayer.
- *Réversibilité* : décision peu coûteuse à défaire, l'interface de tâche étant de toute façon spécifiée comme branchable en U2 ; un élargissement se réexamine en U6 au vu des premiers résultats.
- *Réserve, levée le jour même* : le scorecard **officiel** ARC-AGI-3 suppose un accès à l'API ARC Prize, qui relevait du cas 4 de la « Demande d'arbitrage » (autorité ou accès externes indispensables). L'arbitrage a été rendu et l'accès fourni : voir l'entrée suivante. L'évaluation passera donc par la voie officielle.

**Où reprendre.** Unité U2 : rédiger et committer la spécification du harnais, en y intégrant comme contraintes de conception les trois points mesurés ci-dessus (historique append-only pour le cache de préfixe, budget de ~199 k tokens avec gestion du `413`, politique de raisonnement) ainsi que le périmètre arrêté.

---

## 2026-08-27 (suite 3) — Accès ARC Prize fourni et vérifié ; « évaluer, c'est publier »

**Contexte.** L'arbitrage demandé sur l'accès externe (cas 4) a été rendu par le responsable, qui a fourni une clé d'API ARC Prize et demandé qu'elle soit consignée avec les autres valeurs hors dépôt.

**Vérification, en lecture seule.** `GET /api/games` sur l'API ARC-AGI-3 : `401` sans clé, `200` avec — le contrôle d'accès est réel et la clé est valide. **Aucun scorecard n'a été ouvert et aucune partie n'a été jouée** : la vérification s'est délibérément limitée au listing.

**Observations.** L'API expose **25 jeux et 183 niveaux**, ce qui recoupe exactement le billet NVIDIA. Chaque jeu porte ses `baseline_actions` humaines **par niveau** ; la somme des références humaines vaut 17 135 actions. Contrôle croisé avec l'export VISTA de `knowledge/` : pour `sc25`, le cumul reconstruit depuis l'API vaut `[36, 42, 74, 157, 300, 350]`, identique au tableau exporté. Les jeux portent des étiquettes de modalité d'entrée (`click`, `keyboard`, `keyboard_click`) dont l'interface de tâche devra tenir compte.

**Conséquences.**

1. **Le RHAE se calculera sur la donnée officielle** servie par l'API, et non sur les tables recopiées dans `knowledge/`, qui ne gardent qu'une valeur de contrôle.
2. **Évaluer, c'est publier.** Chaque partie officielle s'enregistre dans un scorecard rattaché au compte porteur de la clé ; il n'existe pas de mode officiel sans dépôt de résultat. Deux règles en découlent, écrites dans le backlog : les exécutions d'essai passent par un environnement local de rejeu déterministe et n'appellent jamais l'API, et la première campagne officielle requiert l'accord explicite du responsable, puisqu'elle engage son compte.
3. **Le volume interdit la campagne improvisée** : 183 niveaux, référence humaine de 17 135 actions, agents de référence autour de 7 000 actions, à multiplier par le coût de préremplissage mesuré sur l'endpoint. Le périmètre d'une campagne est un paramètre spécifié, jamais un défaut implicite.

**Où reprendre.** Le préalable à la planification du worker : `docs/MASTER_PLAN.md` (absent alors que le contrat du worker le lit), redécoupage du backlog en unités d'une session portant chacune du code, adaptation du contrat de worker à une pile Python sans interface, et commandes du dépôt dans le `README.md`. Ensuite seulement, la boucle planifiée peut être armée.

---

## 2026-08-27 (suite 4) — U2 close : spécification complète, plan directeur, backlog redécoupé en sessions

**Contexte.** Le responsable a demandé de spécifier toutes les unités et toutes les sessions maintenant, pour que la boucle planifiée puisse avancer seule jusqu'à sa fin. Constat partagé : le backlog en 6 unités ne portait pas la charge d'un harnais complet, et trois manques structurels bloquaient l'armement du worker (pas de `docs/MASTER_PLAN.md` alors que son contrat le lit ; unités trop grosses pour une session, dont une unité purement documentaire piégeuse au sens de son §4.2 bis ; contrat de preuves calibré pour une stack web absente de ce dépôt).

**Méthode.** Relecture intégrale des quatre exports de `knowledge/` avant rédaction (papier AVO : formalisme Vary/lignée/superviseur, anatomie d'un pas de variation ; billet NVIDIA : configuration ARC texte-seul, actions sans description ; VISTA : prompt exact, outils inspect/read_pixels, notes GUIDE/WORKING, continuation en contexte frais ; Tycho : formalisation Moore, protocole de score et définition RHAE §3.1, surface d'outils annexe A, garde-fous d'évaluation). Les contraintes mesurées du jour (préremplissage, plafond par clé, raisonnement) sont intégrées comme exigences.

**Livré (committé avec cette entrée).**

- `docs/SPEC_HARNAIS.md` (H1–H14) et `docs/SPEC_ARCAGI3.md` (A1–A8) : chaque exigence a un identifiant stable pour les `@spec`.
- `docs/MASTER_PLAN.md` : ordre d'exécution, DoD commune, règle [LIVE], campagne `make check` hors ligne, adaptation CLI de la vérification utilisateur, condition de fin de boucle.
- `docs/BACKLOG.md` : U1/U2 closes ; 23 unités de code U3–U25 (lots A–F), une session chacune, preuves nommées.
- `docs/DAT.md`, `README.md`, `CLAUDE_PROJECT.md`, `CHANGELOG.md` mis en cohérence.

**Décisions principales (motifs dans les spécifications).** Python ≥ 3.11 stdlib sans dépendance d'exécution (H2.1) ; surface Ollama native derrière interface remplaçable (H4.1) ; `think:false` par défaut (H12) ; historique append-only + continuation à la VISTA (H5) ; lignée = git jetable par run, politique « correct ∧ ≥ meilleur » (H9) ; instanciation ARC du couple solution/score = connaissance validée / (niveaux, −actions) — décision explicitement marquée, les sources ne publiant pas ce détail (H9.2) ; jeu synthétique `cible` spécifié en forme fermée pour des E2E à valeurs exactes (A3.2) ; garde anti-publication dans les tests et garde d'accord explicite pour toute campagne live (A2.3, A7.2).

**Hypothèse restante, nommée.** Le format de fil exact de l'API ARC (chemins, corps, x/y vs row/col) est déduit de l'export Tycho, pas mesuré — le mesurer publierait un scorecard. Il est traité comme contrat à confirmer par la sonde U22 [LIVE], qui corrigera client ET rejeu local dans le même chunk (A1.4).

**Où reprendre.** U3 (squelette Python et outillage), puis l'ordre du plan. Le worker planifié peut être armé : il lira MASTER_PLAN, prendra U3, et s'arrêtera de lui-même quand il ne restera que les unités [LIVE]. L'armement de la tâche planifiée reste un geste du responsable (dépense en son nom).

---

## 2026-08-27 (suite 5) — Session planifiée n° 1 : U3 livré et prouvé, chaîne d'outillage entièrement conteneurisée

**Contexte.** Première exécution de la tâche planifiée (`docs/CloudWorker.md`), lancée en session interactive. État Git initial : `main`, propre, rien à récupérer. Unité choisie selon §4.2 : **U3**, désignée par la dernière entrée du journal et première `[ ]` dans l'ordre du plan. Sa spécification existait (H2) : codée directement, sans la réécrire.

**Instruction du responsable reçue en cours de session.** « Le tout doit tourner dans un docker, n'installe rien sur la machine locale. » Elle arrive au bon moment : la mesure ci-dessous venait de montrer que l'outillage n'était de toute façon pas installable ici.

**Observations d'environnement (mesurées, pas supposées).**

1. **Docker inutilisable par l'agent — situation levée en cours de session (voir plus bas).** Le démon tournait (`docker` 29.7.2, compose v5.5.0) mais `docker info` rend `permission denied` sur `/var/run/docker.sock` : l'utilisateur `p2enjoy` n'appartient pas au groupe `docker` (groupes : p2enjoy adm cdrom sudo dip plugdev users lpadmin lxd). `sudo` exige une authentification interactive, `sg` n'existe pas, aucun socket rootless n'est actif, et configurer le rootless installerait des composants chez le responsable — ce que son instruction interdit. **Aucune voie sans privilège.**
2. **Outillage Python absent et non installable.** Python 3.14.4 présent, mais ni `pip`, ni `ensurepip`, ni `uv`, ni `pipx`, ni `pytest`/`ruff`/`mypy`. `python3 -m venv` échoue à amorcer pip.
3. **`make` n'est pas installé** sur l'hôte : le contrat de commandes n'y est donc pas exerçable du tout.

**Décisions (règle d'autonomie, motifs consignés dans les spécifications).**

1. **Toute la chaîne d'outillage vit dans une image Docker** (`Dockerfile`, U3) : pytest, ruff et mypy y sont installés, jamais sur l'hôte. Le `Makefile` lance un conteneur jetable sur le dépôt monté en volume, avec `--user $(id -u):$(id -g)` pour ne pas laisser de fichiers root sur le volume. Une garde nomme le correctif quand le démon est injoignable, au lieu d'un échec opaque. L'image de développement, initialement prévue en U5, est donc livrée par U3 ; U5 ne garde que la pile de services.
2. **Les tests sont écrits avec `unittest` (stdlib)**, exécutables sous pytest dans le conteneur comme sans rien installer. Motif : cohérent avec le principe « zéro dépendance » déjà acté, et supprime une dépendance qui rendait ce dépôt invérifiable sur cet hôte. Coût nul, les tests restant compatibles pytest.
3. **Mode dégradé `AVO_NO_DOCKER=1`**, qui exécute les tests sur l'hôte sans rien installer, **en annonçant** que le lint est réduit à une compilation et que le typecheck n'est pas exécuté. Le bilan de `make check` répète la mention. Il ne vaut pas preuve de style ni de typage — un vert ne doit jamais être lu comme une preuve non exécutée (CLAUDE.md §18).

**Livré.** Paquet `src/avo` sans dépendance d'exécution, sous-paquets du squelette H2.2, `python -m avo` avec `--version` et une aide qui déclare les sous-commandes du contrat ; une sous-commande spécifiée mais non livrée **refuse explicitement en nommant son unité de backlog**. `pyproject.toml`, `Dockerfile`, `.dockerignore`, `Makefile` Docker-first, `.gitignore` complété (`runs/`), squelette `tests/` et `mocks/`.

**Preuves exécutées.** Compilation de `src` et `tests` : OK. **7 tests unitaires verts**, dont une invocation réelle de `python -m avo --version` dans un processus séparé, la cohérence de version entre paquet et `pyproject.toml`, et le refus explicite de chaque commande non livrée. Vérification opérateur (MASTER_PLAN §5) des quatre commandes de la CLI : sorties observées conformes, codes de sortie 0/0/2/2.

**Déblocage en cours de session.** Le responsable a installé **Docker rootless** pendant la session (socket `/run/user/1000/docker.sock`, contexte `rootless`, serveur 29.7.2). Deux corrections mesurées ont suivi :

1. **En rootless, ne pas passer `--user`.** L'utilisateur de l'hôte est déjà mappé sur root dans le conteneur ; ajouter `--user $(id -u):$(id -g)` le prive de droits sur le volume monté (constaté : `Failed to initialize cache at /app/.ruff_cache: Permission denied`). Le Makefile détecte donc le mode rootless et n'ajoute `--user` qu'en mode classique, où il reste indispensable pour ne pas laisser de fichiers `root` dans le dépôt.
2. **`make` absent de l'hôte** : il est installé dans l'image, et le Makefile reçoit un mode « déjà en conteneur » (`AVO_IN_CONTAINER`, posé par l'image) qui appelle les outils directement au lieu de relancer un conteneur depuis un conteneur. La campagne complète s'exécute ainsi avec **Docker pour seul prérequis**. Les caches des outils sont dirigés vers `/tmp` du conteneur : le dépôt monté n'en reçoit aucun.

**Preuves exécutées, dans le conteneur.** `ruff check` : aucune anomalie (un dépassement de 105 colonnes trouvé et corrigé au passage) ; `ruff format --check` : 14 fichiers déjà formatés ; `mypy` en mode **strict** : 14 fichiers, aucune anomalie ; `pytest` : **7 tests verts**. Vérification opérateur refaite dans le conteneur. Contrôle final : aucun cache ni fichier `root` laissé dans le dépôt. **U3 est donc `[x]`** — toutes ses preuves ont réellement tourné.

**Où reprendre.** U4 (serveur mock-llm), dans l'ordre du plan. Le mode dégradé `AVO_NO_DOCKER=1` reste documenté pour un environnement sans Docker, mais il n'est plus le chemin de cet hôte.

---

## 2026-08-27 (suite 6) — Décision remplacée : on ne simule pas l'endpoint, on l'enregistre et on le rejoue

**Objection du responsable, et elle est fondée.** « Si je te donne un serveur dédié pour développer contre le réel, pourquoi veux-tu faire un mock ? » La spécification H4.7 prévoyait un serveur `mock-llm` reproduisant le contrat Ollama. C'était une erreur de conception : `CLAUDE.md` §15 réserve les mocks aux dépendances **impossibles à exécuter localement**, et l'endpoint fourni n'en est pas une. Réimplémenter un contrat que l'on peut mesurer revient à l'inventer, et garantit sa dérive — le défaut classique du mock, que le papier Tycho documente d'ailleurs pour ses propres verificateurs.

**Décision remplacée (H4.7 réécrit).** Plus aucun faux serveur Ollama. Le dispositif est un **enregistreur/rejoueur** :

1. `make record-llm` appelle le **vrai** endpoint et capture chaque échange HTTP tel quel dans une cassette, expurgée de la clé et de l'hôte ;
2. les tests rejouent ces cassettes hors ligne, sans secret ; une requête sans correspondance rend une erreur explicite nommant l'écart, jamais une réponse inventée ;
3. `make test-int-live` rejoue les mêmes scénarios contre le serveur réel : un écart est un défaut à traiter, pas une cassette à réécrire en silence ;
4. seules les fautes que le serveur ne produit pas à la demande (500, latence, coupure) sont injectées. Les erreurs **réelles** — 401 sans clé et avec clé invalide, 413 avec son corps de quota — sont enregistrées depuis le vrai serveur, où elles ont déjà été mesurées (entrée « suite 2 »).

Le contrat servi en rejeu est donc toujours d'origine mesurée. Le composant est renommé `llm-replay`, par symétrie avec `arc-replay`.

**Pourquoi `arc-replay` reste, lui, un serveur local.** La différence n'est pas de principe mais d'effet de bord : chaque partie jouée via l'API ARC **publie un scorecard** sur le compte du responsable. C'est exactement le cas « impossible à exécuter localement » de `CLAUDE.md` §15 — on ne peut pas s'entraîner gratuitement dessus. Son contrat est néanmoins lui aussi ancré sur du réel : la sonde U22 enregistre un épisode authentique qui sert de référence (A3.3), et le jeu synthétique `cible` n'imite aucun jeu officiel, c'est une fixture pour éprouver la mécanique du harnais.

**Portée.** H4.7 réécrit ; H2.3 gagne `make record-llm` et `make test-int-live` ; U4 réécrite dans le backlog (avec la nuance : le code et les tests de rejeu sont livrables sans `.env`, seule la capture initiale des cassettes est [LIVE]) ; U7, README, DAT, MASTER_PLAN et Makefile mis en cohérence.

**Où reprendre.** U4, dans sa nouvelle définition. Le cron horaire est armé (job `9347a105`, à :07) : cette correction est committée avant sa première itération, pour qu'il ne construise pas ce qui vient d'être écarté.

---

## 2026-08-27 (suite 7) — Session planifiée n° 2 : U4 livré et prouvé, contrat de l'endpoint enregistré

**Unité.** U4 — `llm-replay`, désignée par le journal et première `[ ]` du plan. Spécification existante (H4.7) : lue, puis code directement, sans la réécrire.

**Environnement.** Docker rootless opérationnel (serveur 29.7.2), image `avo-dev` présente. Pas de fichier compose : c'est l'objet de U5, non livrée — état attendu du plan, pas un échec de démarrage. `make` toujours absent de l'hôte ; toutes les preuves passent par le conteneur.

**Livré.** Trois modules sous `mocks/llm_replay/` : `cassette` (format JSONL, clé d'appariement = méthode + chemin + nature d'authentification + empreinte SHA-256 du corps canonisé, expurgation, corps volumineux non stockés), `server` (rejeu strict des échanges enregistrés, erreur explicite nommant l'écart sur requête inconnue, injection de fautes 500/latence/coupure par route de pilotage hors contrat), `record` (exécution des sept scénarios contre le vrai serveur). Cibles `make record-llm`, `make test-int-live` et `make seed` implémentées ; `mocks/` rendu importable par pytest, ruff, mypy et l'image.

**Contrat réellement enregistré** (`tests/fixtures/llm/cassettes/contrat_endpoint.jsonl`, 7 échanges, 5,6 Ko) : 401 sans clé, 200 sur version, 200 sur tags, 200 conversation simple, 200 conversation **avec appel d'outil bien formé**, 401 avec clé invalide, 413 avec son corps de quota (`max_context_tokens = 229376`). La requête de dépassement pèse 1,98 Mo : elle n'est pas stockée, seule son empreinte l'est — la cassette reste à 5,6 Ko.

**Décisions de conception.**

1. **Aucun analyseur de `.env` n'est écrit.** Docker passe le fichier au conteneur (`--env-file`), donc aucun secret ne transite par du code du dépôt et la configuration centralisée reste l'affaire de U6.
2. **Le corps de requête volumineux n'est pas persisté**, son empreinte suffisant à l'appariement. Motif : garder le dépôt léger sans perdre la capacité d'apparier exactement.
3. **Le test de dérive vit sous `tests/live/`**, jamais ramassé par `make check`. Il compare statut et **forme** de la réponse, en ignorant les champs légitimement volatils d'un modèle non déterministe (contenu généré, durées, compteurs).

**Preuves exécutées, toutes en conteneur.** ruff `check` et `format` : aucune anomalie ; mypy **strict** : 24 fichiers, aucune anomalie ; **31 tests verts** — 19 unitaires (dont l'expurgation vérifiée en cherchant un secret dans le fichier écrit, et l'appariement insensible à l'ordre des clés JSON) et 12 d'intégration HTTP réels sur port éphémère, dont le **rejeu des sept échanges enregistrés**, la présence de `max_context_tokens` dont dépendent H3.2 et H5.4, et l'appel d'outil dont dépend H8. `make test-int-live` : vert contre le serveur réel, **aucune dérive**.

**Observation utile pour la suite.** Le rejeu live des mêmes scénarios a pris 3,3 s contre 17 s à l'enregistrement : le cache de préfixe d'Ollama a servi les conversations identiques quasi instantanément. C'est la confirmation empirique du choix d'historique append-only (H1.3.1).

**Où reprendre.** U5 — pile compose des services (`llm-replay` en service, healthcheck, image de production, `make up/down/build`).

---

## 2026-08-28 — Session planifiée n° 3 : U5 livré, pile de services debout et éprouvée

**Unité.** U5 — pile compose des services, désignée par le journal et première `[ ]`. Spécification existante (H2.4) : lue, puis code directement.

**Livré.** `Dockerfile` **multi-étages** séparant deux objets qui n'ont pas la même vocation : `avo` (production, 176 Mo — le paquet seul, aucune dépendance d'exécution, aucun outillage de test) et `avo-dev` (320 Mo — y ajoute `make`, `pytest`, `ruff`, `mypy`, seul endroit où l'outillage est installé). `docker-compose.yml` : service `llm-replay` sur le port 11435, dépôt monté en volume, healthcheck HTTP sur un nouveau point `/_health` (hors contrat Ollama, préfixé comme `/_fault`, indépendant des cassettes). Cibles `build`, `up`, `down`, `ps`, `logs`, `smoke-pile`, refusées depuis l'intérieur d'un conteneur avec un message qui explique pourquoi (elles pilotent Docker). Script de fumée `scripts/smoke_pile.sh`.

**Décision : aucun secret dans la pile.** `OLLAMA_API_KEY` n'est délibérément pas injectée dans compose. Sans elle, le rejoueur accepte n'importe quel jeton porteur comme authentification valide et ne distingue que l'absence d'en-tête — ce qui suffit à démontrer le refus sans clé et le succès avec clé. La pile se lance donc sur une machine vierge, sans `.env`.

**Défaut trouvé et corrigé pendant l'unité.** Le healthcheck passait (exécuté dans le conteneur) alors que l'hôte n'obtenait rien : le rejoueur écoutait sur `127.0.0.1` **du conteneur**, adresse que le port publié n'atteint pas — Docker redirige vers l'interface du conteneur, pas vers sa boucle locale. L'interface d'écoute est désormais un paramètre explicite : `127.0.0.1` par défaut, pour ne rien exposer par accident, et `0.0.0.0` passé explicitement par la pile, avec le motif écrit dans le code et dans compose. C'est exactement le genre de défaut qu'un healthcheck interne seul n'aurait jamais révélé : seule la fumée depuis l'hôte l'a vu.

**Preuves exécutées.** `make build` (image de production construite). Pile démarrée, service `healthy`. Fumée depuis l'hôte : **6 contrôles verts** — healthcheck `healthy`, `/_health` 200, `/api/version` 401 sans clé et 200 avec, `/api/tags` 200, et le corps rejoué identique à ce que le vrai serveur avait répondu. Cycle `up → down → up` rejoué pour prouver que la pile se relève. Campagne complète en conteneur : ruff, `ruff format`, mypy strict (24 fichiers), **32 tests verts** (19 unitaires, 13 d'intégration dont le nouveau contrôle du point de santé).

**Un attendu faux, corrigé.** La fumée a d'abord échoué sur la comparaison du corps rejoué : le rejoueur re-sérialise en JSON canonique, sans espace après le deux-points, alors que mon attendu en portait un. C'est l'attendu qui était faux, pas le produit — corrigé avec la raison écrite dans le script.

**Où reprendre.** U6 — configuration `avo.config` (lecture d'environnement et de `.env`, validation nommée, modes replay/live, budget de contexte dérivé du plafond par clé).

---

## 2026-08-28 (suite) — Session planifiée n° 4 : U6 livré, configuration validée et sans fuite

**Unité.** U6 — configuration `avo.config`, désignée par le journal et première `[ ]`. Spécification existante (H3) : lue, puis code directement. Pile démarrée et saine avant le travail, seed vérifié (7 échanges).

**Livré.** `src/avo/config.py` : analyse d'un `.env` minimal (commentaires, lignes vides, guillemets encadrants, préfixe `export`, et **ligne ininterprétable → erreur nommant le numéro de ligne** plutôt qu'ignorée silencieusement) ; précédence environnement puis fichier ; validation nommée de chaque variable — entier strictement positif, réel borné, booléen aux formes usuelles, URL http(s) avec hôte et slash final retiré ; modes rejeu et live ; budget `floor(contexte / 1,15) − num_predict` ; plafond appris depuis un `413`.

**Décisions.**

1. **En mode rejeu, aucun secret n'est requis** : la configuration pointe la pile locale, avec un jeton explicitement nommé « rejeu-sans-secret » et une fenêtre par défaut. En mode live, l'absence d'un secret est une erreur nommée — jamais une valeur par défaut, conformément à H3.3.
2. **Le plafond appris n'abaisse que.** Un `413` renvoyant un `max_context_tokens` supérieur à la fenêtre configurée ne l'élargit pas : une réponse d'erreur ne doit pas pouvoir relever silencieusement une limite que l'exploitant a choisie plus étroite.
3. **Un objet `Config` peut atterrir dans un journal.** `resume()` et `repr()` masquent les deux clés ; c'est vérifié par test et par exécution réelle.

**Observation relevée en vérifiant sur la configuration réelle.** `OLLAMA_CONTEXT_LENGTH` vaut désormais 262144 — le contexte natif du modèle — alors que le plafond mesuré de la clé est 229376. Le budget dérivé vaut donc 223855 tokens, au-dessus des 195361 réellement exploitables : un prompt proche de ce budget déclencherait un `413`. Ce n'est pas un défaut du module, c'est exactement le cas que le plafond appris rattrape (H3.2), au prix d'un aller-retour perdu. Poser 229376 dans la configuration l'éviterait ; la décision appartient au responsable, le harnais fonctionne dans les deux cas.

**Preuves exécutées, toutes en conteneur.** ruff `check` et `format`, mypy **strict** : aucune anomalie. **60 tests verts** — 47 unitaires dont **28 pour la configuration** (analyse du fichier, précédence des sources, chaque variable requise manquante nommée une par une, entier et booléen et URL invalides, valeur exacte du budget, plafond appris dans les deux sens, masquage des secrets), et 13 d'intégration. Vérification opérateur dans le conteneur sur les deux modes : la clé réelle n'apparaît ni dans le résumé ni dans la représentation.

**Un test qui a pris mon propre calcul en défaut.** Le littéral attendu du budget était faux — j'avais écrit 195407 là où `floor(229376 / 1,15) − 4096` vaut 195361. L'assertion par formule passait, l'assertion en clair a rougi. Le littéral est corrigé et commenté, pour que le contrat reste lisible sans recalcul.

**Où reprendre.** U7 — client d'inférence : `LLMClient.chat` sur `/api/chat`, erreurs typées, retries bornés, éprouvé contre les cassettes enregistrées.

---

## 2026-08-28 (suite 2) — Session planifiée n° 5 : U7 livré, client d'inférence éprouvé sur le contrat réel

**Unité.** U7 — client d'inférence. Pile démarrée et saine, seed vérifié avant le travail.

**Préalable traité dans la session.** En relisant H12.1 pour écrire le client, j'ai constaté que la configuration livrée par U6 n'imposait pas le plancher `AVO_NUM_PREDICT ≥ 8192` lorsque `AVO_THINK=true`, alors que la spécification l'exige explicitement. Défaut étranger à l'unité, donc **consigné dans `docs/INCONSISTENCY_REPORT.md`** ; mais traité en préalable dans la même session (§4.2, second cas), le client consommant précisément ces deux réglages : livrer un client qui les honore par-dessus une configuration qui ne les contraint pas aurait laissé le défaut se manifester à l'exécution. Règle implémentée, testée, et entrée du registre refermée.

**Livré.** `src/avo/llm/client.py` : construction du corps `/api/chat` avec surcharges typées, `ChatResult` normalisé (contenu, raisonnement, appels d'outils, compteurs, durées converties en millisecondes), erreurs typées — `AuthError` fatale, `ContextOverflow` portant `tokens_estimated` et `max_context_tokens` du corps réel, `ServerError`, `TransportError`, `ProtocolError` — et retries bornés avec jitter. Transport, attente et aléa sont injectables : la politique de retry s'éprouve sans réseau ni attente réelle.

**Décision structurante : l'enregistreur construit ses corps avec le client.** U4 avait écrit ses corps à la main, faute de client à ce moment. C'était une divergence en germe : une simple différence de sérialisation — `0` contre `0.0` sur la température — aurait suffi à ce qu'aucune cassette ne s'apparie jamais au client. H4.7 prévoyait d'ailleurs que « le client H4 appelle le vrai endpoint ». L'enregistreur passe donc par `construire_corps`, et le contrat a été **réenregistré** sur cette base. La cassette porte désormais exactement ce que le client émet, ce que le test d'intégration prouve : s'il y avait divergence, l'appariement échouerait au lieu de l'absorber.

**Détail du contrat découvert, contre-intuitif, et désormais spécifié.** Sur la surface **native**, un appel d'outil revient avec `done_reason: "stop"` — et non `"tool_calls"`, qui est une convention de la surface compatible OpenAI. Mon test attendait la seconde valeur et a rougi ; c'est l'attendu qui était faux. La détection se fait sur la **présence de `message.tool_calls`**, encodée dans la propriété `demande_outil` et inscrite en H4.3. Sans cela, la boucle agent de U13 aurait ignoré tous les appels d'outils. Les arguments arrivent par ailleurs déjà décodés en objet ; la forme « chaîne JSON » reste gérée, les deux étant admises.

**Spécification clarifiée.** H4.5 disait « 3 tentatives » tout en listant trois délais : formulation ambiguë. Elle énonce désormais « jusqu'à trois nouvelles tentatives après l'échec initial, soit quatre requêtes au plus », ce que le code implémente et qu'un test vérifie en comptant les appels.

**Preuves exécutées, toutes en conteneur.** ruff `check` et `format`, mypy **strict** sur 29 fichiers : aucune anomalie. **94 tests verts** — 74 unitaires (dont 27 pour le client : construction du corps, normalisation, arguments d'outil invalides qui ne lèvent pas d'exception, classification de chaque statut, non-retry sur 4xx, épuisement des tentatives, bornes du jitter, absence de secret dans les journaux) et 20 d'intégration (dont 7 du client contre le rejeu du contrat réel, y compris la chaîne complète `413` réel → plafond appris → budget réduit). `make test-int-live` : vert, **aucune dérive**. Vérification opérateur à travers la pile : le client obtient le vrai appel d'outil `run_shell {"command": "ls /tmp"}`.

**Où reprendre.** U8 — comptabilité, journalisation et workspace de run : logs JSON sans secret, `manifest.json`, `metrics.jsonl`, transcripts par segment, `TokenLedger`, et la cible `make smoke-live`.

---

## 2026-08-28 (suite 3) — Session planifiée n° 6 : U8 livré, journalisation, workspace et comptabilité

**Unité.** U8 — comptabilité, journalisation, workspace de run. Pile démarrée et saine, seed vérifié, registre sans entrée ouverte.

**Livré.** `avo.runlog` : journalisation JSON d'une ligne, niveaux, `run_id` corrélant toutes les lignes. `avo.memory.workspace` : arborescence H6.1 complète, manifeste portant la configuration résolue **sans secret** et la version du harnais, `metrics.jsonl`, transcripts numérotés par segment, `report.md`. `avo.context.tokens` : estimation locale et `TokenLedger` qui se recalibre sur le compte réel du serveur. Le client gagne les deux lectures `version()` et `modeles()` dont la fumée a besoin, et `make smoke-live` devient réelle.

**Décision : la garantie « aucun secret » ne repose pas sur la discipline des appelants.** Un filtre installé sur le journal remplace toute valeur sensible — dans le message, dans les arguments de formatage et dans les champs supplémentaires, y compris imbriqués dans des dictionnaires ou des listes — juste avant écriture. Même un `logger.info(cle)` maladroit ne peut donc pas faire fuiter la clé. Les valeurs de moins de huit caractères sont exclues du masquage : masquer « ok » rendrait les journaux illisibles sans rien protéger d'utile.

**Décision : la calibration ne se fait que sur des compteurs exploitables.** Un serveur qui ne rendrait pas `prompt_eval_count` ne doit pas dérégler l'estimation ; l'échange est alors compté sans recalibrer. L'estimation sert aux seuils, le réel fait foi dans les métriques (§H5.2).

**Correction d'attribution.** La sous-commande `resume`, que U3 avait rattachée à U8, revient à U13 : elle reconstruit l'état depuis le workspace **et** repart sur un segment frais, ce qui suppose la boucle agent et pas seulement le workspace. L'aide de la CLI le dit désormais correctement.

**Preuves exécutées, toutes en conteneur.** ruff `check` et `format`, mypy **strict** sur 37 fichiers : aucune anomalie. **137 tests verts** — 109 unitaires (dont 35 pour cette unité) et 28 d'intégration. La preuve qui compte : un échange complet contre le rejeu du contrat réel produit un workspace conforme, et la clé est cherchée dans **tous** les fichiers que le run a produits, pas seulement dans ceux qu'on soupçonne. `make smoke-live` : **tout vert** contre le serveur réel — version 0.32.14, complétion `'OK-AVO'`, appel d'outil `run_shell({'command': 'ls /tmp'})`.

**Observation : un modèle est apparu sur le serveur.** La fumée liste désormais `qwen3.8:27b`, `all-minilm:latest` et `qwen3.6:35b` ; les sessions précédentes n'en voyaient que deux. Le harnais n'est pas affecté — la configuration nomme explicitement son modèle et vaut toujours `qwen3.6:35b` — mais le fait mérite d'être su : un modèle plus récent est disponible, et le choix de celui que la campagne emploiera appartient au responsable. Aucune décision prise à sa place ; le seul effet mesurable serait sur les résultats d'évaluation, pas sur le code.

**Où reprendre.** U9 — transcript append-only : structure immuable en tête, empreinte de préfixe vérifiée par test, estimation corrigée par le compte réel.

---

## 2026-08-28 (suite 4) — Session planifiée n° 7 : U9 livré, transcript append-only

**Unité.** U9 — transcript append-only. Pile saine, seed vérifié, registre sans entrée ouverte.

**Livré.** `avo.context.transcript` : `Message` et `Transcript` gelés (`frozen`, `slots`), message système figé à l'ouverture du segment, empreintes `empreinte()` et `empreinte_prefixe(n)`, gardes `prolonge()` et `verifier_prolonge()` qui lève `PrefixeRompu`, sérialisation vers la forme attendue par le client, et résumé journalisable sans contenu.

**Décision : structure fonctionnelle plutôt qu'append-only par convention.** `ajouter` rend un **nouveau** transcript partageant le préfixe ; l'instance existante n'est jamais modifiée. Motif : la spécification demande que « toute API qui muterait la tête n'existe pas ». Une classe mutable dont on promet de n'appeler qu'`append` repose sur la discipline des appelants ; une structure gelée rend la garantie vérifiable — et le test de surface, qui échoue si l'une des méthodes de mutation listées apparaît un jour sur le type, transforme cette garantie en filet permanent contre une régression future.

**Pourquoi cet invariant compte, en une mesure.** Le préremplissage domine le coût : 493 tokens/s mesurés le 2026-08-27. Le 2026-08-28, le rejeu live des mêmes scénarios a pris 3,3 s contre 17 s à l'enregistrement, le serveur ayant servi les préfixes identiques depuis son cache. Un historique dont la tête change invalide ce cache et fait repayer le contexte entier à chaque tour. `PrefixeRompu` est donc levée plutôt qu'absorbée : un préfixe rompu ne se voit pas dans les résultats, seulement dans la facture de temps — le signaler tôt est la seule protection.

**Preuves exécutées, toutes en conteneur.** ruff, `ruff format`, mypy **strict** sur 40 fichiers : aucune anomalie. **164 tests verts** — 131 unitaires (dont 22 pour cette unité : dix tours enchaînés avec vérification de chaque préfixe, détection d'une tête réécrite, d'un message inséré au milieu, d'un système modifié, gel des champs, et le test de surface du module) et 33 d'intégration (dont 5 nouveaux qui tiennent l'invariant sur l'échange réellement enregistré et vérifient qu'après calibration l'estimation colle au compte rendu par le serveur, à un token près).

**Où reprendre.** U10 — budget et continuation en contexte frais : déclenchement au seuil, état de continuation écrit par l'agent, nouveau segment, `413` absorbé en cas nominal et double-413 fatal.

---

## 2026-08-28 (suite 5) — Session planifiée n° 8 : U10 livré, budget et continuation

**Unité.** U10 — budget et continuation en contexte frais. Pile saine, seed vérifié, registre sans entrée ouverte.

**Livré.** `avo.context.contexte` réunit les deux mécanismes que la spécification distingue. Le **préventif** : le seuil dérive du budget (`ratio × budget_prompt`), l'estimation suit la calibration du registre, et `continuer()` ouvre un segment frais composé **exactement** de système + état de continuation + notes + observation, l'ancien segment étant archivé et non effacé. Le **curatif** : `absorber_depassement()` traite le `413` en cas nominal, apprend le plafond réel que le serveur annonce, et compte les dépassements **consécutifs** ; au second, `BudgetIncoherent` est levée avec les valeurs en cause et les variables à vérifier.

**Décision : ce sont les dépassements consécutifs qui condamnent, pas leur nombre total.** Un échange abouti remet la série à zéro. Motif : un premier `413` déclenche une continuation, qui peut parfaitement suffire ; c'est le second, survenant sur le segment frais que cette continuation vient de créer, qui prouve qu'aucune continuation ne peut plus aider. Compter les dépassements absolus ferait abandonner un run parfaitement viable après deux incidents espacés d'une heure.

**Décision : l'historique reprend les appels d'outils demandés.** `enregistrer_reponse` réécrit les `tool_calls` dans le message assistant. Sans cela, un tour suivant présenterait au modèle une conversation dont il ne reconnaîtrait pas ses propres actes.

**Preuves exécutées, toutes en conteneur.** ruff, `ruff format`, mypy **strict** sur 43 fichiers. **191 tests verts** — 152 unitaires (dont 21 pour cette unité : valeur exacte du budget et du seuil, franchissement, effet de la calibration sur le seuil, composition et ordre du segment frais, archivage, progression du numéro de segment, absorption, apprentissage du plafond, remise à zéro par un échange abouti, fatalité au second consécutif) et 39 d'intégration (dont 6 nouveaux). Ces derniers n'emploient **aucun `413` simulé** : ils rejouent celui que le vrai serveur a rendu, avec son corps de quota authentique — le cycle complet « petit budget forcé → seuil franchi → continuation → segment frais utilisable » est éprouvé de bout en bout.

**Un attendu faux, corrigé.** J'attendais six messages dans le segment frais après un échange ; il y en a cinq. Le client n'écrit pas dans le transcript — c'est la boucle agent qui reliera les deux en U13. L'attendu est corrigé et commenté ; le produit était juste.

**Où reprendre.** U11 — notes persistantes : `GUIDE.md` et `WORKING.md` dans le workspace, outils de lecture et d'écriture limités à ces deux noms, et injection en tête de segment frais.

---

## 2026-08-28 (suite 6) — Session planifiée n° 9 : U11 livré, notes persistantes ; lot C terminé

**Unité.** U11 — notes persistantes. Pile saine, seed vérifié, registre sans entrée ouverte.

**Livré.** `avo.memory.notes` : `GUIDE.md` et `WORKING.md` dans `runs/<id>/notes/`, aux rôles distincts repris de VISTA — compréhension durable transverse aux niveaux d'un côté, brouillon du niveau courant de l'autre. Validation stricte des deux seuls noms, avec tolérance de casse et d'extension mais refus de tout chemin d'évasion. Bloc `pour_segment_frais()` injecté par la continuation. Surface d'outil `note_read` / `note_write` et leurs schémas.

**Décision : deux noms, pas trois.** La contrainte est délibérée et écrite dans le module. Un espace de notes libre se transforme en système de fichiers parallèle dont plus rien ne garantit la relecture ; deux emplacements aux rôles nommés obligent l'agent à trancher ce qui est durable et ce qui est jetable.

**Décision : une note vide est annoncée, pas omise.** Le bloc injecté écrit « (vide) » sous le titre d'une note jamais renseignée. Son absence est une information : l'agent saura qu'il n'a rien consigné, là où une omission lui laisserait croire que la section n'existe pas.

**Décision : le domaine lève, la surface d'outil convertit.** `Notes.lire` lève sur un nom invalide ; `note_read` rend `error: …` en texte. C'est la séparation qu'impose §H7.4 : une erreur d'outil doit revenir au modèle pour qu'il se corrige, jamais interrompre le run.

**Deux défauts trouvés et corrigés.** `H6.2` renvoyait à un chapitre `H7.5` qui n'existe pas — H7 s'arrête à H7.4 ; le renvoi pointe désormais vers H7.3 et H5.3. Et `Workspace.metrique` acceptait qu'un champ de métrique remplisse son horodatage par accident : le paramètre est réservé aux mots-clés, et l'appelant imbrique désormais ses compteurs sous une clé plutôt que de les éparpiller. Le second défaut a été révélé par le typage strict, pas par un test — il n'aurait produit qu'une métrique silencieusement fausse.

**Preuves exécutées, toutes en conteneur.** ruff, `ruff format`, mypy **strict** sur 46 fichiers. **217 tests verts** — 172 unitaires (dont 20 pour cette unité : deux noms seulement, refus des chemins d'évasion, révision intégrale, note vide annoncée, surface d'outil qui ne lève pas) et 45 d'intégration (dont 6 nouveaux). La promesse centrale est vérifiée sur la chaîne réelle : après continuation, le contenu noté réapparaît dans le segment frais **et** l'ancienne observation en a disparu ; une note révisée est bien celle qui revient ; et aucun contenu de note n'atterrit dans les métriques.

**Lot C terminé** (U9, U10, U11). Le harnais dispose désormais d'un historique inviolable, d'un budget qui se défend, et d'une mémoire qui survit.

**Où reprendre.** U12 — registre d'outils et dispatch : déclaration, rendu vers le tableau `tools`, routage des `tool_calls`, messages `role: tool` append-only, erreurs rendues au modèle, garde `AVO_TOOL_STEPS_MAX`.

---

## 2026-08-28 (suite 7) — Session planifiée n° 10 : U12 livré, registre d'outils

**Unité.** U12 — registre d'outils et dispatch. Pile saine, seed vérifié, registre d'incohérences sans entrée ouverte.

**Défaut corrigé en préalable.** `AVO_TOOL_STEPS_MAX`, que H7.2 nomme explicitement comme garde du nombre d'appels par tour, était absente du tableau des variables H3.1 et de `avo.config`. Défaut du chapitre même que cette unité implémente, donc traité directement plutôt que consigné : variable ajoutée à la configuration, au tableau H3.1 et au README.

**Livré.** `avo.tools.registre` : un outil se déclare par un nom, une description, un schéma de paramètres, une fonction et des étiquettes. `schemas()` filtre par étiquette — c'est ainsi que les outils d'action resteront invisibles hors de l'état où agir est permis (§H7.1). Le routage exécute et rend le résultat ; l'exécution séquentielle ajoute un message `role: tool` par appel, en append-only ; la garde clôt le tour par un message explicite au lieu de tronquer en silence, et son compteur est cumulable entre deux lots puisqu'elle vaut pour le tour et non pour un lot.

**Décision : rien de ce que fait un outil n'interrompt le run.** Nom inconnu, argument obligatoire absent, type incorrect, énumération non respectée, argument inconnu, arguments JSON invalides, fonction qui lève — tout revient au modèle sous la forme `error: <type>: <détail>`, pour qu'il se corrige au tour suivant. Les seules exceptions sont celles que la spécification nomme, et aucune ne concerne les outils.

**Décision : validation minimale, mais réelle.** Champs requis, types, énumérations. Pas de validateur JSON Schema complet, qui exigerait une dépendance d'exécution que le harnais s'interdit (§H2.1). Ce niveau suffit à rendre au modèle un diagnostic exploitable plutôt qu'une trace Python.

**Un test qui a rattrapé une divergence naissante.** Le test vérifiant que le registre expose au modèle exactement le schéma enregistré a rougi : j'avais retapé la description de l'outil au lieu de réutiliser celle de la cassette, et un fragment manquait. Le correctif ne consiste pas à recopier la bonne chaîne mais à **construire l'outil depuis le schéma enregistré** via `outil_depuis_schema` — la duplication qui a causé la dérive disparaît. C'est le même raisonnement qu'en U7, où l'enregistreur avait été rebranché sur le constructeur de corps du client.

**Preuves exécutées, toutes en conteneur.** ruff, `ruff format`, mypy **strict** sur 49 fichiers. **245 tests verts** — 195 unitaires (dont 23 pour cette unité) et 50 d'intégration (dont 5 nouveaux). Ces derniers routent **l'appel d'outil réellement demandé par le vrai modèle**, rejoué depuis la cassette, jusqu'à un vrai outil de notes ; un appel fautif inséré au milieu d'une série n'empêche pas les suivants d'aboutir, et la garde configurée s'applique bien à l'exécution.

**Où reprendre.** U13 — boucle agent P→I→E→B : machine d'états événementielle, prompts par phase, exposition conditionnelle des outils d'action, bornes d'actions, `think:false` par défaut.

---

## 2026-08-28 (suite 8) — Session planifiée n° 11 : U13 livré, la boucle agent tourne

**Unité.** U13 — boucle agent P→I→E→B. Pile saine, seed vérifié, registre sans entrée ouverte.

**Livré.** `avo.loop.etats` : table de transitions **close**, tout couple absent levant `TransitionInterdite` en nommant les événements admis — un état de repli silencieux produirait un run qui tourne sans avancer. `avo.loop.prompts` : textes versionnés et courts, puisqu'ils sont réémis à chaque tour. `avo.loop.boucle` : contrat `Environnement` minimal, outils filtrés par phase, bornes par niveau et par jeu.

**Décision : la machine est du code, le contenu des phases est du prompt.** Une transition qui dépendrait de l'interprétation d'un texte libre serait irreproductible, et un run ne pourrait plus être rejoué. Seule la contradiction est déclarée par le modèle ; niveau complété et partie perdue sont des faits rendus par l'environnement — les faire dépendre de ce que le modèle en dit rendrait le score manipulable par le texte.

**Décision : les outils d'action ne sont exposés qu'à la phase Implementation.** Hors de cet état, le modèle ne peut pas dépenser une action par mégarde. C'est exactement l'usage prévu par le filtrage par étiquettes livré en U12.

**Défaut de conception trouvé par la preuve.** Le test d'intégration a montré que le compteur d'actions montait sans que la fonction de l'outil ne s'exécute : la boucle appelait l'environnement **directement**, court-circuitant le registre, alors que §H8.1 exige d'agir « via l'outil d'action ». L'outil d'action n'était donc qu'une déclaration décorative. L'action passe désormais par le registre — son résultat devient un message `role: tool` comme pour tout autre outil — et l'environnement conserve l'issue typée que la boucle relit, restant l'autorité sur ce qui s'est produit. Sans ce test, le défaut n'aurait été visible qu'en campagne, sous forme d'actions qui ne se produisent pas.

**Défaut de spécification corrigé.** `AVO_ACTIONS_MAX`, nommée par H8.3, était absente de la configuration ; et H8.3 décrivait une borne « par niveau et par jeu » sans les distinguer. Elles sont désormais deux, car un niveau qui s'enlise et un jeu qui s'éternise ne se diagnostiquent pas pareil.

**Deux défauts de mon propre échafaudage de test.** Les deux passes du montage — capture des corps émis, puis service par le rejeu — employaient des `tours_max` différents, et le motif de réponses figeait la dernière au lieu de cycler, si bien qu'aucune action n'était plus jouée et que la borne n'était jamais atteinte. Corrigés tous deux ; c'est le prix d'un test qui fait réellement tourner la boucle en HTTP plutôt que de simuler ses appels.

**Preuves exécutées, toutes en conteneur.** ruff, `ruff format`, mypy **strict** sur 54 fichiers. **271 tests verts** — 213 unitaires (dont 18 pour cette unité, 94 sous-tests : cycle nominal, embranchements, table close et exhaustive, absence de cul-de-sac, et surtout **aucune règle de jeu dans les prompts**, vérifiée contre une liste de termes interdits) et 58 d'intégration (dont 8 nouveaux faisant tourner la boucle en HTTP réel contre le rejeu, sur un environnement factice en mémoire).

**Où reprendre.** U14 — lignée et fonction de score : dépôt git jetable sous `runs/<id>/lineage/`, politique « correct ∧ ≥ meilleur », `Scorer` branchable.

---

## 2026-08-28 (suite 9) — Session planifiée n° 12 : U14 livré, lignée de solutions isolée

**Unité.** U14 — lignée et fonction de score. Pile saine, seed vérifié, registre sans entrée ouverte.

**Livré.** `avo.lineage` : dépôt git **jetable et dédié** par run sous `runs/<id>/lineage/`, politique « correct ∧ ≥ meilleur » du papier AVO, `ScorerARC` lexicographique `(niveaux complétés, −actions cumulées)` et `ScorerConstant` déterministe pour éprouver la boucle. Chaque version validée est committée avec son score dans le message, et l'état de connaissance du moment — notes et méta — est ce qui est versionné.

**Décision : l'isolation ne repose pas sur le répertoire courant.** Toute commande git est lancée avec `--git-dir` et `--work-tree` explicites, si bien que git ne remonte jamais l'arborescence. Sans cela, un `git init` raté ferait committer dans le **dépôt du projet** : c'est le seul défaut de ce module qui serait vraiment grave, et c'est celui qui est éprouvé le plus directement — un test compare le `git status` du dépôt du projet avant et après trois propositions.

**Défaut trouvé par la preuve d'isolation.** Le test « sans dépôt dédié, toute commande est refusée » a rougi sur une `FileNotFoundError` au lieu de la garde attendue : j'écrivais les notes **avant** de vérifier l'isolation. Sur une lignée non isolée, rien ne doit être écrit nulle part, pas même un fichier de notes. La garde est désormais la première instruction de `proposer`.

**Une dépendance système assumée.** `git` est ajouté aux deux images. C'est la seule, et elle ne contredit pas le principe « zéro dépendance d'exécution » de H2.1, qui porte sur les paquets Python : le harnais reste installable sans rien compiler. H2.1 le dit désormais explicitement.

**Preuves exécutées, toutes en conteneur.** ruff, `ruff format`, mypy **strict** sur 57 fichiers. **297 tests verts** — 232 unitaires (dont 19 pour cette unité : amélioration, égalité et régression, refus d'une version incorrecte même très bien scorée, meilleur score non déplacé par un refus, isolation par chemin absolu du `--git-dir`, score exact dans le message) et 65 d'intégration (dont 7 nouveaux : la lignée ouverte là où elle vivra réellement, trois progressions donnant trois versions aux scores exacts, une régression intercalée refusée, un run sans progression ne committant rien, et le dépôt du projet vérifié intact).

**Où reprendre.** U15 — superviseur : détection de stagnation et de cycles improductifs, appel LLM séparé, injection `[SUPERVISEUR]` append-only, cooldown. Ce sera la dernière unité du lot D.

---

## 2026-08-28 (suite 10) — Session planifiée n° 13 : U15 livré, superviseur ; lot D terminé

**Unité.** U15 — superviseur. Pile saine, seed vérifié, registre sans entrée ouverte.

**Livré.** `avo.supervisor` : trois détecteurs et une intervention conditionnelle. Stagnation (actions sans complétion de niveau **ni** nouvelle entrée de lignée), cycle improductif (une même action répétée **et** frame inchangée sur une fenêtre de douze), rafale de Bug-Fixing. L'intervention est un **appel LLM séparé** dont le résultat est injecté en append dans l'historique de l'acteur sous la balise `[SUPERVISEUR]`, avec cooldown et journalisation du motif.

**Décision : les déclencheurs sont mesurés, jamais interprétés.** Des compteurs et des empreintes de frames, aucune appréciation portée sur du texte libre. Un déclencheur qui dépendrait de ce que le modèle raconte de lui-même serait précisément aveugle au moment où il tourne en rond — c'est-à-dire quand on en a besoin.

**Décision : la double condition du cycle.** Répéter une action qui produit des effets différents est une exploration légitime ; la répéter sans que rien ne bouge ne l'est pas. Les deux tests négatifs le fixent : une action répétée aux effets variés ne déclenche pas, et des actions variées sur une frame figée non plus.

**Décision : le superviseur ne reçoit pas l'historique de l'acteur.** Il en obtient un résumé factuel — dernières actions, empreintes de frames, notes, observation courante. Hériter du contexte, ce serait hériter de l'ornière dont il doit sortir l'acteur. Un test vérifie qu'une chaîne présente dans l'historique de l'acteur n'atteint jamais l'appel du superviseur.

**Décision : il n'a aucun outil.** Son seul pouvoir est d'écrire un message que l'acteur reste libre d'ignorer. Un superviseur qui agirait doublerait la politique et rendrait le score inattribuable — c'est la séparation reprise de Tycho, où seul l'acteur commet des actions.

**Défaut d'échafaudage, le même que la session précédente.** Ma passe de capture employait un motif littéral là où la passe réelle emploie le motif calculé : les corps différaient, aucun échange ne s'appariait. Les deux passes exécutent désormais **le même scénario**, décrit une seule fois. La leçon se répète : dès qu'un test rejoue des échanges enregistrés, tout ce qui entre dans le corps doit être produit par le même chemin dans les deux passes.

**Preuves exécutées, toutes en conteneur.** ruff, `ruff format`, mypy **strict** sur 60 fichiers. **324 tests verts** — 255 unitaires (dont 23 pour cette unité, avec un cas négatif pour chaque détecteur) et 69 d'intégration (dont 4 nouveaux passant par le vrai client et le vrai rejeu HTTP : intervention réelle, cooldown respecté, motif dans `metrics.jsonl` sans que la directive y figure).

**Lot D terminé** (U12 à U15). Le harnais possède désormais sa boucle complète : outils, machine d'états, lignée scorée, supervision.

**Où reprendre.** U16 — serveur de rejeu `arc-replay` et jeu synthétique `cible`, qui ouvre le lot E : l'interface ARC-AGI-3 proprement dite.

---

## 2026-08-28 (suite 11) — Session planifiée n° 14 : U16 livré, contrat ARC local et jeu `cible`

**Unité.** U16 — serveur de rejeu `arc-replay` et jeu synthétique `cible`, première du lot E. Pile saine, seed vérifié, registre sans entrée ouverte.

**Livré.** `mocks/arc_replay` : le moteur du jeu `cible` (grilles 64×64 bordées, cible 2×2 mobile par niveau, curseur, frames transitoires, RESET conforme au protocole, trois clics ratés perdant la tentative), un serveur stdlib exposant le contrat A1.3, le mode rejeu d'épisodes, le service compose sur 8765 avec healthcheck, la partie arc de `make seed` et l'extension de la fumée de pile.

**Décision : le format de fil est fixé et écrit.** A1.4 ne disait que « à confirmer par U22 ». Il décrit désormais précisément les routes, les corps et la réponse commune — c'est ce qu'implémentent le rejeu d'aujourd'hui et le client de U17. Sans contrat écrit, les deux côtés auraient divergé silencieusement ; avec lui, la sonde U22 aura quelque chose de précis à confirmer ou à corriger, des deux côtés dans le même changement.

**Ce que la forme fermée apporte.** La baseline d'un niveau vaut la distance de Manhattan initiale plus le clic : `[39, 19, 18]` pour les trois niveaux, calculées et non mesurées. Un test vérifie qu'une partie parfaite dépense **exactement** cette baseline — ce qui rendra le RHAE attendu vérifiable au chiffre près en U20, sans jouer.

**Assumé et écrit : ici, on simule.** Contrairement à `llm-replay`, ce service reproduit un contrat qui n'a pas été mesuré. C'est le cas prévu par CLAUDE.md §15 — chaque partie réelle publierait un scorecard — et le module le dit en tête. Le contrat reste ancré : la sonde U22 produira un épisode authentique qui fera référence, et le jeu `cible` n'imite aucun jeu officiel.

**Preuves exécutées, toutes en conteneur.** ruff, `ruff format`, mypy **strict** sur 66 fichiers. **359 tests verts** — 276 unitaires (dont 21 pour le moteur : quatre directions, bordure qui bloque sans cesser de compter l'action, frames transitoire et de décision distinctes, clic exigeant que les coordonnées soient celles du curseur, trois ratés perdant la tentative, RESET initial gratuit puis coûteux, compteur de niveau remis à zéro) et 83 d'intégration (dont 14 nouveaux en HTTP réel : listing avec baselines, cycle de scorecard, **partie gagnée à la main par requêtes** dépensant exactement la somme des baselines, perte, reprise, et rejeu d'épisode dont la déviation est dite explicitement). Fumée de pile étendue : **11 contrôles verts** sur les deux services.

**Où reprendre.** U17 — client API ARC : `ArcClient` typé, historique typé A2.2, garde anti-publication A2.3, éprouvé contre `arc-replay`.

---

## 2026-08-28 (suite 12) — Session planifiée n° 15 : U17 livré, client API ARC

**Unité.** U17 — client API ARC. Pile saine (les deux services), seed vérifié, registre sans entrée ouverte.

**Livré.** `avo.arc.client` : `FrameResult` typé, étiquetage de chaque frame selon son rôle réel, historique rattachant chaque action à la frame de décision d'où elle a été choisie et persisté par niveau dans `runs/<id>/frames/`, erreurs typées, et la garde anti-publication.

**Décision : la politique de transport est extraite et partagée.** A2.1 exige « les **mêmes** règles transport que H4.5/H4.6 ». Deux implémentations parallèles auraient fini par diverger sans que rien ne le signale ; `avo.transport` porte désormais les attentes, le jitter et la boucle de retry, et les deux clients l'emploient. Les 24 tests du client d'inférence sont passés inchangés après l'extraction — c'est ce qui rendait le refactoring sûr.

**Décision : la garde anti-publication est structurelle.** En mode rejeu, construire un client vers autre chose qu'un hôte local **lève**, à la construction. Ce n'est pas une consigne à respecter : c'est une impossibilité. Motif : jouer via l'API officielle enregistre un scorecard sur le compte du responsable, et un test qui l'atteindrait par accident publierait un résultat. Dans le même esprit, `ARC_BASE_URL` pointe maintenant la pile locale en mode rejeu, comme l'endpoint d'inférence depuis U6 — le mode ne peut plus atteindre un service qui publierait, même par défaut.

**Un attendu devenu faux à dessein.** Le test de U6 vérifiait que le défaut du mode rejeu était l'API officielle. Ce défaut a changé, pour la raison ci-dessus. Le test dit désormais la nouvelle règle et un test frère vérifie que le mode live, lui, vise bien l'API officielle. La documentation suit dans le même changement.

**Le typage des frames, et pourquoi il compte.** Une frame terminale n'est pas une frame de décision : `frame_de_decision` rend `None` sur une victoire ou une perte. Sans cette distinction, le harnais pourrait rattacher une action à une grille depuis laquelle il était impossible d'agir, et fabriquer une transition qui n'a jamais eu lieu — exactement ce que la définition 3 de Tycho cherche à empêcher.

**Preuves exécutées, toutes en conteneur.** ruff, `ruff format`, mypy **strict** sur 70 fichiers. **393 tests verts** — 299 unitaires (dont 22 pour cette unité) et 94 d'intégration (dont 11 nouveaux). Le plus important : **une partie complète menée par le client contre le serveur de U16**, en HTTP, dépensant exactement la somme des baselines. C'est la première fois que les deux côtés du contrat de fil se rencontrent ; s'ils divergeaient, ce test rougirait.

**Où reprendre.** U18 — rendu texte, inspection et mémoire de frames : rendu canonique 64×64, coordonnées (row, col), `inspect`, `read_pixels`, `diff`.

---

## 2026-08-28 (suite 13) — Session planifiée n° 16 : U18 livré, rendu texte et mémoire de frames

**Unité.** U18 — rendu texte, inspection, mémoire de frames. Pile saine, seed vérifié, registre sans entrée ouverte.

**Livré.** `avo.arc.rendu` : rendu canonique d'une grille 64×64, ligne d'état, et l'analyse inverse. `avo.arc.memoire` : conservation sans perte de toute frame reçue, `inspect` avec marges d'index, `read_pixels`, `diff` borné, et les schémas d'outil correspondants.

**Décision : le rendu n'ajoute aucune interprétation.** Pas de nom d'objet, pas de mise en évidence, pas de résumé — la grille exacte et rien d'autre, conformément à la configuration AVO du billet NVIDIA. Souffler « voici la cible » reviendrait à donner la réponse que l'agent doit inférer, et fausserait l'évaluation sans que rien ne l'indique dans les scores. Un test cherche explicitement les mots interdits dans le rendu d'une vraie grille.

**Décision : les marges d'index sont indispensables aux découpes.** Sans elles, l'agent voit un motif mais ne peut pas le rattacher aux coordonnées qu'il devra employer pour cliquer. Une découpe sans repères serait une information amputée de ce qui la rend actionnable.

**Décision : le `diff` est borné.** Au-delà de soixante-quatre cellules, le compte suffit et le reste est annoncé. Énumérer plusieurs milliers de cellules noierait l'information utile — et le budget de contexte avec, alors même que le préremplissage domine le coût.

**Décision : les outils annoncent leur gratuité.** Leurs descriptions disent qu'ils n'entrent pas dans le compte des actions. C'est vrai selon le protocole, et le taire priverait l'agent d'un levier : inspecter longuement avant d'agir ne coûte rien au score, seule l'action en coûte.

**Un comptage naïf de mon côté.** Le test bornant le `diff` comptait les flèches, en incluant celle de l'en-tête « tours 1 → 2 » : il annonçait 65 pour 64 cellules. Le code était juste ; le test compte désormais les cellules elles-mêmes, et vérifie en outre que le nombre d'omises est annoncé.

**Preuves exécutées, toutes en conteneur.** ruff, `ruff format`, mypy **strict** sur 74 fichiers. **435 tests verts** — 334 unitaires (dont 35 pour cette unité, avec la propriété **rendu ∘ analyse = identité** sur les grilles de chaque niveau et sur les seize couleurs) et 101 d'intégration (dont 7 nouveaux sur les frames que le serveur envoie réellement : le `diff` d'un déplacement voit exactement les deux cellules concernées, celle qu'on quitte et celle où l'on arrive, et `inspect` retrouve une frame cinq tours en arrière).

**Où reprendre.** U19 — interface de tâche direct-interaction : prompt de tâche minimal calqué sur VISTA, outils d'action filtrés par la frame, comptage officiel réconcilié, branchement complet sur la boucle et le scorer.

---

## 2026-08-28 (suite 14) — Session planifiée n° 17 : U19 livré, interface de tâche direct-interaction

**Unité.** U19 — interface de tâche direct-interaction. Pile saine (les deux services), seed vérifié (7 échanges dans la cassette, jeu cible à 3 niveaux, baselines [39, 19, 18]), registre d'incohérences sans entrée ouverte.

**Livré.** `avo.arc.interface` : `InterfaceArc` implémente le contrat `Environnement` de la boucle et relie enfin les quatre briques ARC déjà livrées — client, rendu, mémoire de frames, machine d'états. Un outil par commande **que la frame courante déclare**, `action6` validant (row, col) dans [0, 63], comptage officiel tenu localement et réconcilié, observation rendue depuis la seule frame de décision avec mention des transitoires conservées.

**Décision : le filtrage doit atteindre la surface réellement exposée.** Le registre d'outils de la boucle est construit une fois pour le run, alors que les commandes déclarées changent à chaque frame. Filtrer côté interface sans toucher au registre aurait laissé le modèle voir des commandes que l'environnement n'offre plus : il l'aurait appris par un message d'erreur, c'est-à-dire par un canal qui n'existe pas dans le jeu. `RegistreOutils.synchroniser` remplace en bloc les outils d'une étiquette ; l'interface l'appelle après chaque frame absorbée. `enregistrer` continue de refuser les doublons — un remplacement doit rester explicite. Preuve : après trois clics manqués, le tableau `tools` réellement émis à l'implémentation ne contient plus que `reset`.

**Décision : les descriptions d'outils sont muettes sur les effets.** « Joue la commande ACTION1. Coûte une action. » — le nom de la commande et son coût selon le protocole, rien de plus. Ce module est le dernier endroit où un indice pouvait entrer, et il aurait été le plus discret : une description utile (« déplace vers le haut ») aurait amélioré les scores sans qu'aucune ligne du rapport ne le signale. Ce qui est dit reste vrai du protocole, jamais du jeu.

**Décision : le serveur fait foi sur le comptage, l'écart reste visible.** C'est le compteur du serveur qui produit le score officiel ; le compteur local ne peut donc pas le contredire. Mais un écart signale soit un défaut de notre comptage, soit un protocole mal compris : il est journalisé, conservé dans le comptage et destiné au rapport. Aligner en silence aurait effacé la seule trace d'un bug de comptabilité.

**Revue explicite « zéro indice de jeu » — consignée.** Surfaces par lesquelles un texte atteint le modèle, et verdict de chacune :

1. `prompts.SYSTEME` — pose un jeu inconnu sur une grille de cellules colorées, dit explicitement que les objets, mécaniques et but ne sont pas donnés. La seule consigne d'objectif (« terminer chaque niveau en aussi peu d'actions que possible ») énonce la règle de score du protocole, pas une règle de jeu. **Conforme.**
2. `prompts.PLANNING`, `IMPLEMENTATION`, `EVALUATION`, `BUG_FIXING`, `BORNE_PROCHE` — méthode d'enquête et bornes de budget ; aucun contenu de jeu. **Conforme.**
3. `INVITATION_CONTINUATION` — reprise de contexte, aucun contenu de jeu. **Conforme.**
4. Noms d'outils `action1`…`action6`, `reset` — ce sont les noms du protocole. Les renommer en termes parlants serait précisément la fuite. **Conforme.**
5. `DESCRIPTIONS` — commande nommée, coût annoncé ; pour `action6`, les paramètres que le protocole exige. **Conforme.**
6. Rendu de l'observation — ligne d'état (niveau, score, actions, commandes déclarées) puis la grille d'entiers. Aucune étiquette, aucune mise en évidence, aucun résumé. Les couleurs du jeu de rejeu n'atteignent le modèle que comme des entiers. **Conforme.**
7. Mention des frames intermédiaires — un fait sur la mémoire, pas sur le jeu. **Conforme.**
8. Schémas `inspect`, `read_pixels`, `diff` — décrivent l'outil et sa gratuité au score. **Conforme.**
9. `note_read` / `note_write` — deux noms de notes, aucun contenu préchargé : ce que l'agent y lit, c'est ce qu'il y a écrit. **Conforme.**
10. Message du superviseur — parle de stagnation, de répétition et de budget ; jamais du jeu. **Conforme.**
11. Messages d'erreur d'outil — `ActionIndisponible` liste les commandes déclarées (des noms), `CoordonneesInvalides` rappelle les bornes de la grille, qui relèvent du protocole. **Conforme.**

Deux gardes exécutables remplacent la promesse : un balayage statique des constantes de tous ces modules, et un balayage du corps JSON de **toutes** les requêtes réellement émises pendant un run de quatre tours. Limite assumée : ce sont des listes de termes interdits, donc une preuve d'absence de *ces* indices, pas d'absence de tout indice ; la revue ci-dessus reste la garantie principale, et elle est à refaire à chaque texte ajouté.

**Une commodité manquante, ajoutée.** `HistoriqueFrames.ecrire` promettait `runs/<id>/frames/` depuis U17, mais le workspace n'exposait pas ce chemin. `Workspace.frames` complète la série `notes`/`transcripts` ; la promesse est désormais atteignable sans fabriquer la chaîne.

**Preuves exécutées, toutes en conteneur.** ruff, `ruff format`, mypy **strict** sur 77 fichiers. **476 tests verts** — 365 unitaires (dont 31 pour cette unité) et 111 d'intégration (dont 10 nouveaux, contre les deux rejeux en HTTP réel). Les plus significatifs : une partie parfaite conduite par l'interface dépensant exactement la somme des baselines **sans un seul écart de comptage** ; la perte de tentative qui réduit les commandes offertes jusque dans le tableau `tools` émis ; et un niveau complété par l'agent scripté, dont le bilan alimente réellement `ScorerARC` — le branchement va donc de la frame jusqu'au score de lignée.

**Où reprendre.** U20 — RHAE : `eₗ = min(115, 100·(hₗ/aₗ)²)`, poids `wₗ = ℓ`, plafond par complétion pondérée, baselines servies par `/api/games`, vérifié en forme fermée sur le jeu cible.

---

## 2026-08-28 (suite 15) — Session planifiée n° 18 : U20, contrat d'implémentation du RHAE

**Unité.** U20 — RHAE. Pile saine, seed vérifié (7 échanges, jeu cible 3 niveaux, baselines [39, 19, 18]), registre sans entrée ouverte.

**Pourquoi une spécification avant le code.** A6 fixait la formule et les vecteurs de test, pas le contrat d'implémentation : ni les refus, ni les cas limites, ni la manière de passer d'une partie réellement jouée aux entrées (hₗ, aₗ, cₗ). A6.4 les écrit, et deux points ont été tranchés avant d'écrire une ligne.

**Décision : la somme porte sur TOUS les niveaux du jeu, pas sur ceux atteints.** C'est la seule lecture qui donne un sens au second terme du `min`. Sur les seuls niveaux atteints, un agent qui termine le premier niveau d'un jeu qui en compte trois obtiendrait 100, à égalité avec un agent ayant tout fini : le plafond ne plafonnerait plus rien. Avec l'ensemble complet des niveaux — c'est-à-dire `len(baseline_actions)` — ce même agent obtient au mieux 100·(1/6) = 16,67.

**Décision : une action compte pour le niveau DEPUIS lequel elle a été jouée.** L'API renvoie l'action qui complète le niveau 1 avec `level = 2`. L'imputer au niveau 2 volerait une action au niveau 1 et en ajouterait une au suivant — les deux RHAE seraient faux, et de façon compensée, donc invisible sur le total des actions. Le niveau d'origine est celui de l'entrée précédente de l'historique typé. La première entrée est le `RESET` de création : gratuite (A1.2), elle n'est comptée nulle part.

**Décision : la complétion vient du score du serveur.** cₗ = 1 si et seulement si le score rendu par l'API atteint ℓ à un moment de la partie. Déduire la complétion de notre lecture des frames rendrait le score dépendant de notre interprétation ; c'est le serveur qui fait autorité, comme pour le comptage d'actions (A5.3).

**Décision : refuser plutôt que rendre zéro.** Une baseline nulle ou négative, un numéro de niveau hors bornes, un trou dans la suite des niveaux, une moyenne demandée sur zéro jeu : tous lèvent. Rendre 0 ferait passer un défaut de protocole pour une mauvaise performance de l'agent, et le rapport serait faux sans que rien ne le signale.

**Livré.** `avo.arc.rhae` : module pur, sans entrée-sortie ni réseau. Efficacité par niveau plafonnée à 115, pondération `wₗ = ℓ`, RHAE de jeu pris comme minimum de l'efficacité pondérée et du plafond par complétion, moyenne arithmétique sur le périmètre, et le pont `niveaux_joues` qui traduit un historique typé en entrées de la formule.

**Une tolérance ajoutée en écrivant les preuves.** Un numéro de niveau au-delà du dernier est accepté tant qu'aucune action ne lui est imputée : après la victoire du dernier niveau, l'API peut avancer son compteur à L+1, et refuser ce numéro rendrait une partie gagnée incalculable. Une ACTION imputée à L+1, en revanche, lève toujours.

**Preuves exécutées, toutes en conteneur.** ruff, `ruff format`, mypy **strict** sur 80 fichiers. **511 tests verts** — 396 unitaires (dont 31 pour cette unité) et 115 d'intégration (dont 4 nouveaux). La preuve centrale : contre le rejeu ARC en HTTP, une partie parfaite rend **exactement 100.00**, les baselines étant demandées à `/api/games` et non écrites en dur ; et une partie perdue, relancée, puis gagnée compte **43 actions** au niveau 1 — 44 si le RESET de création avait été facturé. Le total des actions du RHAE coïncide avec le comptage indépendant de l'interface, deux chemins qui ne partagent aucun compteur.

**Non couvert par cette unité.** Le RHAE n'a pas encore de surface CLI : il sera lu depuis `run-arc` et le rapport (U23). La vérification « dans la peau de l'utilisateur » de MASTER_PLAN §5 arrive donc avec U21 et U23.

**Décision : U23 passe avant U21.** A8.3 définit la preuve de U21 comme « depuis la CLI réelle […] l'agent complet joue le jeu `cible` de bout en bout […] `report.md` et la lignée existent ». La seule commande qui joue une partie est `run-arc`, et c'est U23 qui la livre : prise dans l'ordre des numéros, U21 n'aurait rien à exécuter. L'ordre du plan est donc inversé sur ces deux unités — le point est écrit ici et dans les deux unités du backlog, pour qu'une session qui ne lit que le backlog ne s'y reprenne pas. Aucun autre couple n'est concerné : U22, U24 et U25 sont [LIVE].

**Où reprendre.** U23 — runner de campagne et rapport : `run-arc` multi-jeux, plafonds obligatoires en live, garde d'accord A7.2, reprise sans rejouer les jeux terminés, `report.md` complet A7.3. U21 (E2E) suit immédiatement et s'appuie sur cette commande.

---

## 2026-08-28 (suite 16) — Session planifiée n° 19 : U23, contrat du runner de campagne

**Unité.** U23 — runner de campagne et rapport, désignée par l'entrée précédente. Pile saine, seed vérifié, registre sans entrée ouverte.

**Trois manques mesurés en lisant les spécifications.** A7.3 exige que `report.md` porte les coûts (tokens, durées, actions) et les événements (continuations, interventions du superviseur, 413). Or : `Workspace.metrique` n'est appelé par aucun producteur, `Superviseur` n'est référencé nulle part dans la boucle, et `Contexte.continuer` / `absorber_depassement` non plus. Les trois mécanismes existent, sont testés isolément, et ne servent à rien dans un run réel. Un rapport écrit par-dessus annoncerait « 0 continuation, 0 intervention » — ce qui est vrai et trompeur à la fois, puisque aucune ne *peut* survenir.

**Décision : ces trois branchements sont dans le périmètre de U23**, et non des corrections au passage. Ils ne sont pas des défauts étrangers rencontrés en chemin : ce sont les producteurs des chiffres que le livrable de l'unité doit contenir. Le contrat correspondant est écrit en H8.4, et les branchements y sont **optionnels par construction** — sans workspace ni superviseur, la boucle se comporte exactement comme avant, ce qui préserve les preuves existantes.

**Décision : la reprise est de granularité JEU.** Un jeu interrompu est rejoué depuis le début dans une partie neuve ; les jeux déjà terminés ne le sont jamais. Motif : reprendre une partie en cours supposerait de retrouver la frame courante, qu'aucune requête ne rend gratuitement — la redemander coûterait une action, et le score mêlerait deux tentatives, ce qui priverait le RHAE de sens. Les notes du run survivent, donc la connaissance acquise n'est pas perdue.

**Décision : les budgets de campagne ne contredisent pas H8.3.** H8.3 interdit de borner du temps d'horloge *dans* la boucle ; les budgets de temps et de tokens de A7.1 sont des conditions d'arrêt *de campagne*, évaluées entre deux tours, qui closent le jeu proprement et nomment leur motif. Le point est écrit en A7.4 pour qu'il ne soit pas relu comme une contradiction.

**Livré.** Les quatre branchements de H8.4 sur la boucle, puis `avo.arc.campagne` (plafonds, garde d'accord, état de reprise réécrit après chaque jeu, un client ARC et une lignée par jeu), `avo.arc.rapport` (les sept sections de A7.3) et les sous-commandes `run-arc` et `resume`. La table des commandes non livrées de la CLI est désormais vide.

**Le rapport est un invariant du runner, pas un devoir de l'appelant.** `executer_campagne` écrit `report.md` avant de rendre son résultat. Laisser cette écriture à la CLI aurait fait qu'une campagne lancée autrement — un test, un futur ordonnanceur — se terminerait sans laisser de compte rendu.

**Deux cibles du Makefile étaient fausses.** `make run-arc` lançait le conteneur sans réseau d'hôte : à l'intérieur, `127.0.0.1:8765` désigne le conteneur lui-même et rien ne répond. Les deux cibles partagent désormais le réseau de l'hôte et acceptent `ARGS`. `make resume RUN_ID=<id>` est ajoutée.

**Preuves exécutées, toutes en conteneur.** ruff, `ruff format`, mypy **strict** sur 85 fichiers. **550 tests verts** — 427 unitaires (dont 31 pour cette unité) et 123 d'intégration (dont 8 nouveaux). Les plus significatifs : une mini-campagne réelle contre les deux rejeux en HTTP dont on relit ensuite les artefacts sur disque — rapport, frames typées, dépôt de lignée isolé, transcript archivé, métriques ; deux preuves passant par `main()` ; et la reprise prouvée **par la négative**, avec un client d'inférence qui lève s'il est appelé — donc aucun jeu terminé n'est rejoué.

**Vérification opérateur (MASTER_PLAN §5), exécutée et observée.** Campagne lancée par la CLI réelle sur la pile de rejeu : sortie terminale conforme (`0/3 niveaux, 4 actions, RHAE 0.00`), `report.md` relu en entier — le tableau par niveau donne bien hₗ, aₗ, cₗ et wₗ, les coûts comptent 13 appels au modèle, et la section des limites dit que ce score n'est **pas comparable** aux références publiées. Les trois refus ont été vus au terminal : live sans accord, live sans budgets, reprise d'un run inexistant.

**Où reprendre.** U21 — E2E : partie complète sur rejeu local. Sa condition d'ordre est désormais satisfaite, `run-arc` étant livrée. Deux scénarios par la CLI réelle sur la pile compose : victoire 3 niveaux avec le RHAE exact attendu (100.00), et échec (game over → RESET → victoire) ; artefacts vérifiés. Le décor à monter : une cassette de campagne seedée, puisque `llm-replay` sert un répertoire fixe.

---

## 2026-08-30 — Session interactive : source SKILL.state ajoutée, lot G (U26–U29) au backlog

**Contexte.** Le responsable a fourni le PDF arXiv:2608.26263v1 « SKILL.state: Scalable Long-Horizon Agent Skills » (Google LLC / Purdue, 26 août 2026) avec pour consigne de l'ajouter aux autres sources et d'ajouter les unités de backlog détaillées correspondantes. Session sur la branche désignée `claude/avo-harness-implementation-ufsb43`.

**État Git constaté et rattrapé.** La branche de session précédente avait été fusionnée dans `main` puis supprimée ; `main` porte depuis les livraisons des sessions planifiées (U3–U20 et U23 closes). Deux commits de cette session, écrits avant ce constat, partaient de l'ancienne base — l'export SKILL.state (`dc1a4a5`, conservé tel quel) et un redécoupage de backlog devenu obsolète (`9f100e4`, remplacé). `origin/main` a été **fusionné** dans la branche (pas de réécriture d'historique, conformément aux règles du dépôt), les fichiers documentaires en conflit pris côté `main`, puis les ajouts ci-dessous posés sur cet état vrai.

**Étude de la source.** SKILL.state remplace l'historique conversationnel append-only par un état d'exécution structuré mutable : prompt de pas `(P, Σₜ, Oₜ)`, sortie `(Rₜ, ΔΣₜ, aₜ)`, raisonnement jeté après validation du patch, `Σₜ₊₁ = Σₜ ⊕ ΔΣₜ` (fusion, suppression par null), empreinte O(1) et coût cumulé O(T). Mesures marquantes : à budget de tokens égal, l'état structuré bat troncature/résumé/LLMLingua (0,94 contre 0,18–0,52, Warehouse T=100) ; récupération en 0 pas après dérive externe de l'état (contre 5–14 pas pour les runtimes à historique) ; taxonomie d'erreurs open-weight — 68 % d'écrasements/omissions de clés, 20 % de schéma, 12 % de JSON malformé — qui impose que le schéma et la validation appartiennent au runtime, avec rollback-retry. Limite énoncée par les auteurs : l'état n'est une statistique suffisante que si la pertinence d'une observation est reconnue quand elle survient.

**Tension identifiée avec H5, à départager par la mesure.** Le harnais a retenu le transcript append-only + continuation (H5) sur une contrainte mesurée de l'endpoint : préremplissage dominant, cache de préfixe (journal du 2026-08-27, suite 2). Le mode SKILL.state borne le prompt mais représmplit `(P, Σₜ, Oₜ)` à chaque tour — sur cet endpoint, l'avantage net n'est pas déductible sur le papier. Décision : livrer le mode en **alternative configurable** (`AVO_CONTEXT_MODE`, défaut `transcript` inchangé) et le départager par A/B, d'abord sur rejeu, puis en réel.

**Livré cette session.**

1. Export complet de la source dans `knowledge/` (texte intégral, figure d'architecture recadrée pleine largeur et inspectée, dix tableaux transcrits, prompts exacts des quatre runtimes, PDF sous `knowledge/pdf/`) ; index `knowledge/README.md` : cinquième ligne et point de synthèse n° 5 **reformulé après la fusion** pour présenter SKILL.state comme alternative mesurable, pas comme conception adoptée.
2. **Lot G ajouté au backlog** : U26 (chapitre H15 committé avant le code, puis runtime `avo.context.etat` — patch, validation par le runtime, rollback-retry, preuves calquées sur la taxonomie §5.7), U27 (mode `state` de la boucle derrière `AVO_CONTEXT_MODE`, défaut inchangé, A/B sur rejeu `cible` avec rapport comparatif), U28 [LIVE] (A/B du périmètre pilote en réel après U24, décision du mode par défaut avec le responsable), U29 (benchmarks InterCode CTF / τ-Bench / banc type SkillExecBench — **hors périmètre**, décision du 2026-08-27 inchangée, en attente d'arbitrage explicite).
3. `docs/MASTER_PLAN.md` : lot G au tableau, U28 dans la liste [LIVE], U29 exclu de l'ordre tant que l'arbitrage n'est pas rendu.
4. Mentions périmées corrigées au passage, toutes adjacentes aux fichiers touchés : `README.md` (« aucun code applicatif n'existe encore » et « U3 en tête » remplacés par l'état réel U3–U20+U23 livrés, prochaine unité U21 ; quatre → cinq sources), `CLAUDE_PROJECT.md` (« unités U1–U6 » → lots A à G ; terminologie SKILL.state).

**Vérifications réalisées.** Liens d'images de tous les exports `knowledge/` vérifiés par script (aucun manquant) ; figure du papier re-recadrée et inspectée ; chiffres du résumé recoupés avec les tableaux transcrits ; fusion relue (`git status` propre, aucun fichier de `main` régressé — les conflits documentaires ont tous été pris côté `main`). Aucun code exécutable modifié : la campagne de preuves n'était pas requise et n'a pas été lancée.

**En attente du responsable.** (1) Arbitrage U29 : élargir ou non le périmètre d'évaluation aux benchmarks du papier ; (2) après U28, décision du mode de contexte par défaut pour U25.

**Où reprendre.** Inchangé pour le worker : **U21** (E2E sur rejeu local), puis U26–U27 dans l'ordre. U22, U24, U25, U28 restent [LIVE] en session interactive.

---

## 2026-08-30 (suite) — Tout est fusionné sur `main` ; `main` devient la seule branche de travail

**Instruction du responsable.** « Merge rebase everything to main and work exclusively on main. » La branche de session `claude/avo-harness-implementation-ufsb43` (export SKILL.state, lot G, fusion de rattrapage) a été fusionnée dans `main` en avance rapide (`43eaa4a`) et poussée ; la branche est supprimée, tout son historique étant porté par `main`.

**Règle persistée.** `CLAUDE_PROJECT.md`, Conventions locales : toutes les sessions, planifiées comme interactives, travaillent et poussent exclusivement sur `main` ; aucune branche de travail ; conflits résolus sur place. La présente session poursuit sur `main`.

**Où reprendre.** Inchangé : U21 (E2E sur rejeu local), puis U26–U27 (lot G). U22/U24/U25/U28 [LIVE] en session interactive ; arbitrage U29 en attente.

---

## 2026-08-30 (suite 2) — Recette de joignabilité depuis la session interactive ; `.env.example` exhaustif

**Demande du responsable.** Vérifier que la session peut joindre l'endpoint LLM, puis documenter toutes les variables d'environnement dans un `.env` d'exemple.

**Joignabilité — mesures du jour, depuis CETTE session interactive.** Le `.env` local est présent et ignoré par git (revérifié). L'endpoint ne répond pas d'ici : reset TLS à ~6,2 s sur `/api/version`, avec et sans clé, et le proxy de session rapporte « tunnel vers le proxy de sortie fermé avant la fin de l'échange ». Contrôles discriminants rejoués : sortie 443 saine (`arxiv.org` 200 en 0,35 s), TLS vers un port non-443 public de référence (Cloudflare 2053) échoue à l'identique, et le serveur de l'endpoint accepte le TCP depuis 3 nœuds externes en 0,15–0,73 s. **Conclusion inchangée depuis le 2026-08-27 : la sortie réseau de cet environnement interactif n'autorise le TLS que vers le port 443 ; le serveur est sain, et l'environnement du worker planifié le joint (cassettes réelles enregistrées, `make test-int-live` vert).** Conséquence pratique : les unités [LIVE] (U22, U24, U25, U28) ne peuvent pas s'exécuter depuis cette session-ci en l'état ; elles exigent soit un environnement dont la sortie n'est pas limitée au 443 (celui du worker convient), soit l'exposition de l'endpoint sur 443. Aucune clé n'a transité par un service tiers pendant ces contrôles.

**`.env.example` ajouté à la racine, suivi par git** (`!.env.example` ajouté sous `.env.*` dans `.gitignore`, `git check-ignore` revérifié dans les deux sens). Il documente **les 20 variables** — les 17 de `avo.config`/H3.1 (endpoint, ARC, modèle et inférence, budgets de contexte/outils/actions, superviseur, artefacts) et les 3 d'outillage lues par make et les scripts (`AVO_NO_DOCKER`, `AVO_PORT_LLM_REPLAY`, `AVO_PORT_ARC_REPLAY`), chacune avec rôle, format, caractère requis/facultatif, défaut et exemple non sensible ; les requises en clair avec valeur factice, les facultatives commentées à leur défaut. Exhaustivité prouvée par script : extraction des noms depuis `config.py` + Makefile/scripts, différence vide dans les deux sens (20/20). Table du README complétée des sept variables applicatives qui y manquaient (`AVO_MODEL`, `AVO_THINK`, `AVO_NUM_PREDICT`, `AVO_TEMPERATURE`, `AVO_TIMEOUT_S`, `AVO_CONTEXT_SOFT_RATIO`, `AVO_RUNS_DIR`), de la note d'outillage et du renvoi vers `.env.example`.

**Où reprendre.** Inchangé : U21, puis U26–U27. [LIVE] : voir la contrainte d'environnement ci-dessus.

---

## 2026-08-30 (suite 3) — Pont HTTPS 443 déployé devant l'endpoint d'inférence, recetté de bout en bout

**Demande du responsable.** Déployer sur son compte Netlify un proxy HTTPS pour atteindre l'endpoint LLM sur le port 443, avec transmission des credentials par le client — aucun credential en dur.

**Livré.** `infra/llm-proxy/` : fonction edge Netlify (TypeScript, Deno) qui relaie les seules surfaces `/api/*` et `/v1/*` vers l'origine et répond `404` partout ailleurs, `502` explicite si l'origine est injoignable, `503` si la variable de site manque. Propriétés voulues : l'URL d'origine vit dans la variable de site Netlify `LLM_ORIGIN_URL` (posée via l'API, jamais committée) ; l'en-tête `Authorization` du client traverse tel quel (passthrough) — le pont ne détient aucun secret et n'élargit pas la surface d'accès, l'origine restant seule à exiger sa clé. `netlify.toml` racine : seul `infra/llm-proxy` est servi. Site créé sur le compte du responsable et déployé via l'outillage Netlify officiel (build vert du premier coup).

**Recette exécutée depuis CETTE session (sortie limitée au 443 — le cas d'usage exact) :**

- chemin hors API → `404` en 0,32 s (l'origine n'est pas touchée) ;
- `/api/version` sans clé → `401` de l'origine (« clé API manquante ») en 1,05 s — preuve du passthrough d'authentification ;
- `/api/version` avec clé → `200`, serveur Ollama `0.32.14`, 0,33 s ;
- `/api/tags` avec clé → `200` ; **fait nouveau : trois modèles servis — `qwen3.6:35b`, `qwen3.8:27b` (absent le 2026-08-27) et `all-minilm:latest`** ; le modèle de travail reste `qwen3.6:35b`, tout changement d'`AVO_MODEL` relevant du responsable ;
- `/api/chat` non-streamé (`qwen3.6:35b`, `think:false`, température 0) → `200`, réponse exacte attendue, 15,5 s dont 14,65 s de **chargement du modèle à froid** (préremplissage 0,23 s pour 25 tokens, génération 0,24 s) — les appels à chaud sont sub-secondes ;
- `/api/chat` streamé → fragments NDJSON reçus un à un à travers le pont.

**Limite de plate-forme documentée** (contexte officiel Netlify) : 40 s maximum avant les premiers en-têtes de réponse de l'origine. Avec le cache de préfixe du serveur (mesure du 2026-08-27 : préremplissage ~493 tok/s), elle n'est atteinte que sur un préremplissage à froid dépassant ~20 000 tokens sans cache — cas rare en campagne (segments frais courts) ; si elle survient, l'appel échoue au pont et le retry H4.5 s'applique.

**Documentation mise en accord dans le même chunk** : `CLAUDE_PROJECT.md` (section endpoint : le pont, son contrat, la liste des modèles observés), `README.md` (structure : `infra/`), `.env.example` (`OLLAMA_HOST` peut pointer le pont), `infra/llm-proxy/README.md` (recette), doublon `!.env.example` retiré du `.gitignore`. Le `.env` local de cette session pointe désormais le pont — les unités **[LIVE] deviennent exécutables depuis les sessions interactives**.

**Où reprendre.** U21 (E2E rejeu), puis U26–U27 ; les [LIVE] (U22 sonde, U24/U25 campagnes, U28 A/B) sont désormais accessibles d'ici, chacune sous ses gardes propres (accord de publication pour les scorecards).

---

## 2026-08-30 (suite 4) — Session interactive sous contrat worker : U21 livrée et close ; routine horaire provisionnée avec autorisation ARC Prize

**Unité.** U21 — E2E : partie complète sur rejeu local, désignée par le journal et le backlog. Pile montée et seedée après un préalable : la construction de l'image échouait sur cet hôte (proxy TLS interceptant, `CERTIFICATE_VERIFY_FAILED` au pip de l'outillage) — support générique d'un CA de build ajouté (`certs/`, spécifié en H2.4), image reconstruite, fumée de pile toute verte.

**Livré (contrat A8.5 écrit et committé avant le code).** Décor partagé `tests/e2e/scenarios.py` (environnement épinglé neutralisant tout `.env` local, `AVO_NUM_PREDICT` discriminant de scénario, suites d'actions rejouant `chemin_optimal()`), générateur `tests/e2e/generer_cassettes.py` (capture en deux passes, auto-contrôle du scénario, double génération comparée — régénération identique octet à octet), cassettes seedées committées (316 et 321 échanges), `make seed-e2e`, `test-e2e` par le réseau de l'hôte, aide du Makefile remise au réel (deux mentions « à venir » périmées). Tests : victoire par sous-processus `python -m avo` réel — « 3/3 niveaux, 76 actions, RHAE 100.00 », rapport A7.3, frames par niveau, lignée à exactement 3 commits `[n, −actions]`, reprise par la CLI réelle sans nouvel appel au modèle ; échec → RESET → victoire par `cli.main` — game_over 1, niveaux [43, 19, 18], RHAE égal à la forme fermée recalculée indépendamment (≈ 97.04).

**Preuves exécutées.** `make seed-e2e` (déterminisme vérifié par le générateur) ; `make test-e2e` vert (2 tests, ~25 s) ; campagne complète `make check` verte après une boucle de correction de style (3 écarts ruff corrigés, campagne rejouée) ; `make build` bloqué par un `429 Too Many Requests` de Docker Hub, reproduit à l'identique sur une relance — limitation du registre depuis cette sortie réseau, étrangère au produit : l'étage `runtime` a été réellement construit ce jour même par `make up` (image multi-étages). Vérification opérateur MASTER_PLAN §5 : campagne réelle par la CLI dans le terminal, artefacts conservés et relus sous `runs/e2e-operateur/` (rapport lu en entier — détail par niveau 39/39, 19/19, 18/18, coûts 316 appels, événements 3 versions committées ; `git log` de la lignée v1→v3 ; arborescence complète).

**Défaut étranger consigné au registre (avec issue).** La boucle ne s'arrête pas sur l'état terminal du jeu : victoire au tour ~76, `tours_epuises` à 120 — 44 tours d'inférence à vide, motif d'arrêt trompeur. Issue retenue : arrêt sur état terminal à spécifier (H8.3) et prouver, préalable de U24 ; comportement inchangé ce jour. Second écart tranché et traité : MASTER_PLAN §4 annonçait `build` dans `make check` — document aligné sur le réel (build s'exécute en sus depuis l'hôte).

**Routine horaire provisionnée (instruction du responsable, reçue en session).** Déclencheur `trig_01GryirsTmK638VfV7aCAuTP` « CloudWorker AVO (horaire) », cron ancré à :31, session fraîche par exécution dans cet environnement. Prompt = contenu intégral de `docs/.routine` (complété des blocs « variables de session » et « autorisations ») + les quatre variables non persistées (endpoint via le pont HTTPS 443, clé d'inférence, `OLLAMA_CONTEXT_LENGTH=229376` — plafond réel par clé mesuré, point tranché —, clé ARC Prize). Doctrine persistée avant création : MASTER_PLAN §3 (les unités [LIVE] sont prenables par la routine munie des secrets et de l'autorisation, plafonds et garde maintenus), CLAUDE_PROJECT (autorisation du responsable : jouer ARC Prize, publier les scorecards, collecter les résultats, améliorer le fonctionnement général ; INTERDICTION DE BENCHMAXING sans exception). Clé ARC ajoutée au `.env` local (ignoré par git, revérifié).

**Où reprendre.** Ordre du plan : U26 (spécification H15 puis runtime d'état structuré), puis U27 ; les [LIVE] U22 → U24 → U25/U28 sont désormais prenables par la routine — traiter d'abord l'entrée ouverte du registre (arrêt sur état terminal) comme préalable de U24. La routine tire sa première session à 14:31 UTC.

---

## 2026-08-30 (suite 5) — Session planifiée (routine CloudWorker) : U26 livrée et close

**Unité.** U26 — Spécification H15 et runtime d'état structuré, désignée par l'entrée
précédente. Git rattaché à `main` sans commit local à sauver (§1.3), Docker démarré
manuellement (`dockerd` direct, le service échoue sur `ulimit`), CA du proxy déposé
dans `certs/` pour l'image de développement.

**Séquence tenue : spéc d'abord, committée, puis code.** §H15 écrit en entier avant
la moindre ligne de `avo.context.etat` — contrat de pas `(P, Σₜ, Oₜ) → (Rₜ, ΔΣₜ, aₜ)`,
opérateur `⊕` à suppression par `null`, schéma possédé et validé par le runtime,
rollback-retry borné, schéma ARC v1 à quatre champs toujours présents, articulation
avec H5/H6.2/H10/H12 — committé et poussé seul (`19ea8f4`) avant d'ouvrir le module.

**Une décision tranchée en écrivant la spécification.** Le papier autorise la
disparition d'une clé sur `null` ; pour un schéma à champs fixes (ARC v1), disparaître
laisserait Σ dans un état incomplet. Décision : `null` réinitialise le champ à son
défaut plutôt que de le retirer — Σ reste **toujours** conforme à son schéma. Le point
est écrit dans H15.2 pour qu'un lecteur du papier ne s'attende pas à une clé absente.

**Livré.** `avo.context.etat` : `Etat` (frozen, quatre champs `position`/`essai`/
`hypotheses`/`objets`), `fusionner` (validation champ par champ avant toute mutation,
jamais d'application partielle), `decoder_pas` (bloc ```` ```json ```` à exactement
`state_patch`/`action`, annexe A.4 SKILL.state), `appliquer` (décodage + fusion),
`CompteurRetries` (budget borné `RETRIES_MAX = 3`), sérialisation JSON aller-retour.
Trois erreurs typées (`EtatInvalide`, `PatchMalforme`, `RetriesEpuises`), aucune
absorbée en silence. Module **pur** : aucune E/S, aucun réseau — le branchement dans
la boucle et la persistance réelle dans le workspace du run restent le périmètre de
U27, qui seule consomme un Σ persisté.

**Preuves exécutées, toutes en conteneur, pile compose debout et seedée.**
`tests/unit/test_etat.py` : 31 tests, dont un par classe de la taxonomie d'erreurs du
papier §5.7 nommément visée (écrasement/omission de clé 68 % — une clé absente du
patch survit —, incohérence de type/structure 20 %, JSON malformé 12 %), la
non-mutation de l'entrée fusionnée, et l'aller-retour de sérialisation exact.
Campagne complète `make check` verte : lint, `ruff format`, mypy **strict** sur 91
fichiers, **458 tests unitaires** (dont les 31 de cette unité, zéro régression sur
les 427 préexistants), **123 d'intégration**, **2 E2E**. `make build` (image de
production) vert. Vérification opérateur (MASTER_PLAN §5) : `python -m avo
--version` et un appel manuel de `appliquer()` dans le conteneur, sortie observée
conforme (patch fusionné, action extraite, raisonnement absent du résultat).

**Un aléa d'environnement rencontré et résolu, pas un défaut du produit.** Le premier
`make image` a échoué sur un `429 Too Many Requests` de Docker Hub à la résolution de
`python:3.13-slim` — même limitation de registre que celle notée le 2026-08-30 pour
`make build` en session U21. Une nouvelle tentative quelques minutes plus tard a
réussi sans autre changement : transitoire, étranger au produit, non consigné au
registre (pas une incohérence du dépôt).

**Où reprendre.** U27 — mode `state` de la boucle (`AVO_CONTEXT_MODE`, défaut
`transcript` inchangé), branchement des primitives de U26 dans `avo.loop.boucle` et
persistance de Σ dans le workspace, A/B sur rejeu (`cible`) avec rapport comparatif
committé sous `docs/rapports/`. Ensuite, les [LIVE] restent prenables par la routine
dans l'ordre déjà consigné : U22 → (registre : arrêt sur état terminal, préalable de
U24) → U24 → U25/U28.

---

## 2026-08-30 (suite 6) — Session planifiée (routine CloudWorker) : U27 branchement livré, A/B restant

**Unité.** U27 — désignée par l'entrée précédente. Git rattaché à `main` (le
checkout de départ était sur une branche temporaire fournie par l'infrastructure,
mais `origin/main` portait déjà exactement le même HEAD — aucun commit à
récupérer, §1.3). Docker démarré manuellement, CA du proxy déposé dans `certs/`
pour reconstruire l'image de développement.

**Un point de spécification tranché avant le code.** H15.1-H15.7 ne disaient pas
si « un pas » du mode `state` correspond à un tour entier de la boucle P→I→E→B ou
à chacun de ses appels. Tranché et écrit dans un nouveau §H15.8, committé et
poussé seul (`4189c02`) avant d'ouvrir le module : un pas = un tour. Motif : forcer
`(state_patch, action)` à chaque appel des phases qui ne jouent aucune action
(Evaluation, Bug-Fixing) ne peut pas se représenter proprement dans le contrat à
deux clés. Conséquences précisées dans le même chapitre : un appel LLM par tour,
rollback-retry par tour, résolution générique de l'action depuis le schéma de
l'outil (jamais un nom codé en dur — interdiction de benchmaxing), Bug-Fixing
implicite (porté par le ΔΣ du pas suivant), persistance de Σ par tour, `413` compté
puis fatal faute d'historique à raccourcir.

**Livré.** `AVO_CONTEXT_MODE` (`transcript`/`state`, défaut `transcript`, validé et
nommé sur valeur inconnue) dans `avo.config`. `BoucleAgent._jouer_tour_etat` :
compose `(P, Σₜ, Oₜ)` + notes à neuf à chaque tour (aucun outil déclaré à l'appel,
le contrat passe par le texte) ; décode et applique le patch via `avo.context.etat`
(module U26, inchangé) ; rollback-retry borné avec le message d'erreur renvoyé au
modèle ; résout l'action générique par le schéma de l'outil (nom + paramètres requis
dans l'ordre, coercés selon leur type JSON déclaré) ; exécute par le même registre
que le mode `transcript` (§H8.1 tenu dans les deux modes) ; les événements niveau
complété / game over restent décidés par l'environnement, jamais par le texte.
`Workspace.ecrire_etat`/`lire_etat` : persistance de Σ dans
`runs/<run_id>/state/etat.json`, aller-retour exact ; un `BoucleAgent` construit
sur un workspace qui en porte déjà un le recharge plutôt que de repartir de
`Etat.initial()`.

**Preuves exécutées, toutes en conteneur, image de dev reconstruite avec le CA du
proxy.** Unitaires : `AVO_CONTEXT_MODE` (défaut, reconnaissance, refus nommé,
résumé journalisable), persistance de Σ (aller-retour, réécriture, chemin). 9 tests
d'intégration nouveaux contre le VRAI rejoueur HTTP (même principe à deux passes
que `test_boucle_complete.py`, cassette bâtie sur les corps réellement émis) :
patch valide qui joue l'action et met à jour Σ, un seul appel LLM par tour (compté
via les métriques du workspace), clé absente du patch qui survit (§H15.2), patch
malformé retenté puis réussi, budget de retries épuisé qui lève `RetriesEpuises`
plutôt que de boucler, action inconnue qui ne joue rien et se signale au tour
suivant (jamais un crash), événement porté par l'environnement qui prime,
persistance ET reprise de Σ depuis un workspace existant. `make check` partiel
(lint, typecheck, test-unit, test-int) intégralement vert : **466 tests unitaires**
(+8 sur les 458 préexistants), **132 d'intégration** (+9), zéro régression sur le
mode `transcript`. `make test-e2e` et la campagne complète n'ont pas été rejoués
dans cette session (budget de temps consommé par le branchement lui-même) —
prochaine session ou fin de session à compléter.

**Ce qui reste explicitement pour clore U27, nommé au backlog.** L'A/B sur rejeu
proprement dit : deux mini-campagnes `run-arc --mode replay` sur le jeu `cible`,
une par mode, et le rapport comparatif (RHAE, actions, tokens cumulés, taille
moyenne de prompt, retries) committé sous `docs/rapports/`, plus le test E2E qui
les rejoue et relit le rapport. Rien ne bloque ce travail — ni accès externe, ni
arbitrage — c'est une suite directe de ce qui est déjà branché et prouvé.

**Où reprendre.** U27 reste `[~]` : reprendre par l'A/B sur rejeu (le jeu `cible`
et ses baselines existent déjà, U16/U21/U23). Une fois U27 close, les [LIVE]
U22 → (registre : arrêt sur état terminal, préalable de U24) → U24 → U25/U28 restent
prenables par la routine, dans l'ordre déjà consigné.

**Précision sur `test-e2e`/`make build` non rejoués (correction de l'entrée
ci-dessus).** La cause réelle n'est pas le budget de temps mais un aléa
d'environnement mesuré : `make up` et `make build` échouent tous deux sur
`429 Too Many Requests` de Docker Hub à la résolution de `python:3.13-slim`
(trois tentatives, toutes identiques) — même limitation de registre que celle déjà
notée les 2026-08-30 (sessions U21 et U26), transitoire et étrangère au produit.
`lint`, `typecheck`, `test-unit` et `test-int` n'en dépendent pas (image `avo-dev`
déjà construite en début de session) et sont tous verts, comme détaillé ci-dessus.
Non consigné au registre d'incohérences : ce n'est pas une incohérence du dépôt.

---

## 2026-08-30 (suite 7) — Session planifiée (routine CloudWorker) : U27 close, A/B sur rejeu livré

**Unité.** U27 — désignée par l'entrée précédente (« reprendre par l'A/B sur rejeu »).
Git rattaché à `main` depuis la branche temporaire fournie par l'infrastructure
(aucun commit local à sauver, §1.3). Docker démarré manuellement (`dockerd`
direct), CA du proxy déposé dans `certs/` pour reconstruire l'image de
développement (même procédure que les sessions précédentes, désormais mesurée).

**Livré.** `avo.arc.campagne.ResultatJeu.retries_patch` (défaut `0`, alimenté par
`bilan.retries_patch`), nécessaire au rapport A/B puisque `transcript` ne décode
aucun patch. `tests/e2e/generer_cassette_etat.py` : cassette de scénario `state`
dédiée (`e2e_etat_victoire.jsonl`), même principe de capture en deux passes que le
générateur `transcript`, régénération identique octet à octet vérifiée — 120
échanges (76 actions réellement jouées, 44 tours à vide après la victoire : la
boucle ne s'arrête pas sur l'état terminal, défaut déjà consigné au registre le
2026-08-30 comme préalable de U24, comportement inchangé ici, mêmes plafonds que
le scénario `transcript`). `avo.arc.rapport_ab` (fonction pure, même principe que
`avo.arc.rapport`) : `MesureMode` et `rapport()`, le markdown comparatif nommant
les cinq mesures du backlog (RHAE moyen, actions, tokens cumulés, taille moyenne
de prompt, retries de patch). `scripts/generer_rapport_ab.py` (`make rapport-ab`) :
rejoue deux mini-campagnes par la CLI réelle (sous-processus, MASTER_PLAN §5), une
par `AVO_CONTEXT_MODE`, et écrit `docs/rapports/ab_mode_contexte.md`.

**Incident mesuré et corrigé en session, avant tout commit.** La première version
de `scripts/generer_rapport_ab.py` ne fixait pas `OLLAMA_HOST`/`ARC_BASE_URL` dans
l'environnement du sous-processus. Le `.env` local de cette session planifiée
porte les vraies variables (endpoint via le pont 443, clé d'inférence) : en leur
absence de l'environnement du sous-processus, `avo.config` les a lues en repli
depuis ce `.env` — exactement le risque que `tests/e2e/scenarios.ENV_EPINGLE`
documente déjà pour les E2E `transcript`/`échec` (« neutraliser tout `.env`
local »), auquel mon script n'avait pas été soumis. La première exécution a donc
réellement interrogé l'endpoint live : latences de 20 à 45 s par appel dans les
journaux (`qwen3.6:35b`), 8 appels environ avant interruption manuelle au bout de
~8 minutes en constatant l'anomalie (une campagne sur rejeu devait durer quelques
secondes). Aucune conséquence durable : `AVO_RUNS_DIR` pointait un répertoire
temporaire (jamais le dépôt), aucun fichier écrit sous `runs/`, `ARC_BASE_URL`
n'a jamais été touché (le client ARC reste sur `arc-replay` local par défaut en
mode rejeu) donc aucun scorecard n'a été ouvert — seul un coût d'inférence réel,
non chiffrable précisément d'ici, a été consommé sur la clé du responsable.
Corrigé en épinglant `OLLAMA_HOST`, `ARC_BASE_URL` et un jeton non secret dans
l'environnement du sous-processus (`HOTE_LLM_REJEU`/`BASE_ARC_REJEU`/
`JETON_REJEU`, mêmes valeurs que la pile locale), avec un commentaire nommant
l'incident pour qu'il ne se reproduise pas à la prochaine lecture du fichier.
Reconduit ensuite avec succès : campagne « transcript » et campagne « state »
toutes deux contre la pile locale, quelques secondes chacune.

**Une limite de mesure nommée explicitement dans le rapport lui-même.** Le
rejoueur HTTP répond verbatim les `prompt_eval_count`/`eval_count` enregistrés une
seule fois à la capture (§H4.7) : la « taille moyenne de prompt » est donc
identique par construction pour les deux modes sur ce rejeu (24 tokens), et ne
porte aucun signal sur la croissance réelle du prompt en `transcript` face au
`O(1)` de `state` (§H15.1). Le rapport le dit en toutes lettres dans sa section
« Limite » plutôt que de laisser un chiffre plat se lire comme une mesure : c'est
le nombre d'appels au modèle (316 contre 120) qui porte ce signal sur ce rejeu.

**Preuves exécutées, toutes en conteneur, pile compose debout et seedée (nouvelle
cassette incluse après `make down && make up`).** `tests/unit/test_campagne.py` :
aller-retour de `retries_patch`, valeur par défaut. `tests/e2e/test_ab_mode_contexte.py` :
le rapport comparatif committé est rejouable **à l'octet près** depuis la CLI
réelle (preuve la plus forte disponible — pas seulement « le script tourne », mais
« le fichier committé est exactement ce que produit le code aujourd'hui ») et nomme
les cinq mesures du backlog. Campagne complète `make check` verte : lint, `ruff
format`, mypy strict, **467 tests unitaires** (+1 sur les 466 préexistants), **132
d'intégration** (inchangé), **4 E2E** (+2 sur les 2 préexistants — le nouveau
scénario A/B rejoint `test_partie_complete.py`). `make build` non rejoué cette
session (déjà vert le 2026-08-30, aucun changement à `Dockerfile`/`pyproject.toml`).

**Un défaut étranger revu, pas retraité.** L'arrêt trompeur sur état terminal
(tours_epuises au lieu d'un arrêt réel à la victoire), déjà consigné le 2026-08-30
comme préalable de U24, se manifeste identiquement en mode `state` (120 tours
joués pour 76 actions utiles). Comportement laissé inchangé ici : U27 ne porte pas
cette correction, et la mesure du jour (120 vs 316 appels) reste valide puisque les
deux campagnes A/B partagent exactement le même plafond et donc le même artefact.

**U27 close : DoD satisfaite** (`docs/BACKLOG.md`, statut `[x]`) — livré et
intégralement vérifié, code et documentation en accord dans le même changement.

**Où reprendre.** Ordre du plan (`docs/MASTER_PLAN.md`, `CLAUDE_PROJECT.md`) : les
unités `[LIVE]` deviennent l'unité de la prochaine session — U22 (sonde d'API ARC,
25 jeux/183 niveaux lus en lecture seule) en premier, puis le préalable consigné
au registre (arrêt sur état terminal, préalable de U24) traité sur le chemin de
U24, puis U24, puis U25/U28. La routine dispose désormais de l'autorisation du
responsable pour jouer via l'API officielle et publier des scorecards en son nom
(2026-08-30, `CLAUDE_PROJECT.md`) ; les plafonds de campagne (`SPEC_ARCAGI3.md`
§A7.1) restent obligatoires et l'interdiction de benchmaxing s'applique sans
exception à toute correction du harnais qui suivrait ces mesures.

---

## 2026-08-31 — Session planifiée (routine CloudWorker) : U22 close, le contrat de fil ARC est mesuré

**Unité.** U22 — sonde de contrat API officielle, désignée par l'entrée précédente.
Git rattaché à `main` (aucun commit local à sauver), Docker démarré manuellement,
CA du proxy déposé dans `certs/`, pile montée et seedée. Autorisation du
responsable (2026-08-30) : la routine joue via l'API officielle et publie des
scorecards à son nom.

**Sonde exécutée, périmètre minimal.** `scripts/sonde_arc.py` (nouveau) : mesure au
niveau transport, sans le parsing d'`ArcClient` — c'est lui qu'on mesure. Scorecard
de sonde `7528ca63-3eff-4866-97c3-8c4a6ded0e63` (étiquettes `probe`, `sonde-u22` ;
le serveur y ajoute `agent` de lui-même), RESET + une ACTION6 sur un jeu réel choisi
par un critère générique (modalité click, moindre somme de baselines), scorecard
fermé. Capture requête→réponse expurgée committée sous
`tests/fixtures/arc/episodes/` (brut + épisode A3.3), recoupée avec l'OpenAPI
publiée (`docs.arcprize.org/arc3v1.yaml`, copiée en scratchpad, non committée).
Deux scorecards d'essais préalables (`e8c6ffae…`, `d26657c1…`, `b8317eac…`) ont
été ouverts pendant la mise au point : aucun n'a coûté d'action scorée hormis un
RESET gratuit sur le troisième, refermé aussitôt.

**Ce que la mesure a corrigé (A1.4 réécrit en contrat mesuré).** Le fil réel
diffère du contrat supposé d'après l'export Tycho sur presque tous les points :
réponse `{game_id, guid, frame, state, levels_completed, win_levels, action_input,
full_reset, available_actions}` (entiers 0–7, RESET jamais déclaré ; ni niveau
courant, ni score, ni compteur d'actions par frame) ; requêtes `RESET {game_id,
card_id, guid?}` (les deux premiers REQUIS), actions `{game_id, guid}` sans
card_id, ACTION6 `{x, y}` avec x=colonne et y=ligne — `{row, col}` refusé (500
mesuré) ; affinité de session par cookies `AWSALB*` posés au RESET ; le listing
`/api/games` peut annoncer un jeu que le backend de commandes refuse (`400 game …
not found`, mesuré sur le jeu de moindre coût du listing) ; `GET
/api/scorecard/<id>` rend 404 sur une carte sans partie ET après fermeture — le
résumé de fermeture fait foi (il porte `level_actions`, `level_baseline_actions`,
`level_scores` par run : c'est la source de la réconciliation A5.3, preuve
déplacée vers U24 puisque la réconciliation par frame n'existe structurellement
plus). Vérifié : `baseline_actions` du listing = `level_baseline_actions` du
résumé.

**Livré, client et rejeu corrigés ensemble (règle de l'unité).** `avo.arc.client`
(fil mesuré, conversion x/y confinée, pot de cookies par instance via
`TransportUrllib`, `FrameResult.niveaux_requis`/`remise_a_zero_complete`, niveau
dérivé), `avo.arc.interface` (reset toujours offert, comptage local seul, outil
`action7`), `mocks/arc_replay` (même contrat, refus nommés identiques, résumé en
`environments`, déviation d'épisode étendue au CORPS des requêtes et rendue 409 —
un 5xx serait retenté et perdrait son motif, point tranché). Nouveau
`tests/integration/test_episode_reel_sonde.py` : l'épisode réel rejoué vert par le
client contre arc-replay. Cassettes E2E régénérées (`make seed-e2e`, observations
changées par la liste d'actions déclarées), pile relancée.

**Preuves exécutées, toutes en conteneur.** lint + `ruff format`, mypy strict (95
fichiers), 473 tests unitaires (+6), 138 d'intégration (+3), 4 E2E sur pile
fraîche (le rapport A/B committé reste identique à l'octet près). Campagne
complète de fin de session : `make check` INTÉGRALEMENT VERT (lint, format, mypy
strict, 473 + 138 + 4 tests) et `make build` vert (image de production
reconstruite).

**U22 close : DoD satisfaite** (`docs/BACKLOG.md` `[x]`) — implémenté et vérifié,
scorecard référencé ci-dessus, documents (README, DAT, SPEC, CHANGELOG, backlog)
mis à jour dans les mêmes commits.

**Où reprendre.** Ordre du plan : le préalable consigné au registre — l'arrêt de
la boucle sur état terminal du jeu (défaut du 2026-08-30, préalable de U24) — se
traite maintenant, PUIS U24 (campagne pilote : périmètre serré consigné au journal
avant lancement, plafonds obligatoires, réconciliation des compteurs sur le résumé
de scorecard). Attention mesurée pour U24 : choisir des jeux que le backend sert
réellement (refus « not found » possible) et ne pas compter sur `GET /scorecard`.

---

## 2026-08-31 (suite) — Instruction du responsable : les rôles, gravés

**Instruction reçue en session, persistée dans `CLAUDE_PROJECT.md` (« Répartition
des rôles »).** Le harnais OVA OSS joue ARC ; la session d'ingénierie ne joue
jamais à sa place, ne lui souffle aucune réponse et ne détermine aucune stratégie
en son nom. Le rôle de la session : coder le harnais, le lancer, OBSERVER son
comportement sur les résultats collectés, et améliorer son fonctionnement général
en restant dans la méthode des publications de `knowledge/`. Un échec du harnais
par manque d'information se corrige en lui donnant le réflexe générique d'aller
chercher l'information lui-même (expérimentation, inspection, prompt qui installe
ce réflexe) — jamais en la lui fournissant. La plomberie hors-jeu (contrat de fil,
transport — sonde U22) reste mesurable directement : elle ne décide d'aucun coup.

**Conséquences pour les prochaines sessions.**

1. Le préalable du registre (arrêt de la boucle sur état terminal) et U24 se font
   en lançant le HARNAIS via `run-arc` (rejeu d'abord, live ensuite sous plafonds) :
   la session lit les artefacts (`report.md`, transcripts, frames, métriques,
   notes GUIDE/WORKING) et n'intervient qu'en amélioration générale.
2. Le PROMPT est un levier de premier rang : vérifier que le prompt de tâche
   (calqué VISTA, §A5.1) installe réellement le réflexe d'exploration — prédire
   avant d'agir, observer les changements, inspecter les frames, entretenir un
   modèle révisable — et l'améliorer d'après le comportement observé, jamais
   d'après un jeu particulier.
3. Toute amélioration issue d'une observation doit valoir pour tous les jeux
   (interdiction de benchmaxing, inchangée).

---

## 2026-08-31 (suite 2) — Instruction du responsable : nature du harnais, et échéance de rejeu

**Instruction reçue en session, persistée dans `CLAUDE_PROJECT.md` (« Nature du
harnais »).** OVA OSS est à Qwen ce que Claude Code est à Claude : un harnais
d'agent LLM généraliste auquel on confie un défi mesuré. L'API ARC peut être
donnée EN CONTEXTE au harnais (outils, protocole, documentation), mais le harnais
ne se code pas AUTOUR de l'API : noyau §H agnostique, adaptateur §A mince (outils
+ prompt), résolution par le fonctionnement du modèle et le contexte fourni —
jamais par une logique de résolution codée.

**Échéance.** Le responsable rejoue le harnais avec `qwen3.6:35b` demain
(2026-09-01) : ce qu'il trouvera sera le résultat de l'implémentation. Les
sessions planifiées d'ici là exécutent, dans cet ordre et sans s'éparpiller :

1. **Arrêt de la boucle sur état terminal** (registre, préalable de U24) — en
   l'état, chaque partie gagnée brûle l'inférence jusqu'à `tours_max` et rend un
   motif d'arrêt trompeur ; inadmissible sur une exécution live du responsable.
2. **Revue du prompt de tâche et du contexte fourni au modèle** (méthode VISTA,
   §A5.1) : vérifier que le harnais reçoit le protocole (coût des actions, RESET,
   rôle des outils d'inspection) et que le prompt installe le réflexe
   d'exploration — prédire, agir, observer, réviser — sans aucun indice de jeu.
   L'amélioration se juge sur le comportement observé en rejeu et sur `cible`,
   jamais sur un jeu officiel particulier.
3. **Préparation du lancement live** : `run-arc --mode live` prêt à être lancé
   par le responsable — plafonds documentés, artefacts lisibles, reprise sûre.

Aucun de ces gestes ne joue à la place du harnais : ce sont le code, le prompt et
le contexte qui changent, la stratégie reste au modèle.

---

## 2026-08-31 (suite 3) — Décision : la méthode passe du prompt à la structure (lot H, U30)

**Question du responsable, en session.** La Definition of Done qu'il impose à
l'agent d'ingénierie — chercher l'information avant d'agir, spécifier, prouver,
persister — a mesurablement amélioré son niveau. Ces instructions doivent-elles
vivre dans le prompt du harnais, ou dans ses PHASES — y compris une recherche
documentaire de la tâche ou de la sous-tâche ?

**Décision (concordante avec le responsable, persistée au backlog : lot H, U30).**
Oui — sous forme de GARDES ET D'ARTEFACTS EXIGÉS à l'intérieur des phases
P→I→E→B existantes, jamais comme de nouvelles phases. Motif : le prompt conseille,
la structure impose — un modèle sous charge dérive de ses consignes, pas de ses
contraintes (c'est l'observation du responsable sur l'agent d'ingénierie lui-même).
Et les publications fournissent déjà tous les ancrages, donc aucune déviation de
méthode : AVO met la base de connaissances K dans la signature même de
`Vary(Pₜ) = Agent(Pₜ, K, f)` — la garde documentaire de Planning est la
mécanisation de K ; VISTA exige prédiction avant action et GUIDE/WORKING — les
gardes de prédiction et de persistance les mécanisent ; H8.1 fait déjà trancher
l'environnement — la garde d'évaluation la complète. Le champ `reasoning` du fil
officiel (mesuré en U22) portera la prédiction : auditable dans le scorecard.
Quatre gardes, spécifiées en H16 avant tout code : documentaire (entrée de
Planning), prédiction (chaque action), évaluation (prédit-vs-observé qualifié),
persistance (GUIDE.md exigé aux complétions/game over/interventions).

**Ordre révisé d'ici le rejeu du responsable (2026-09-01)** — remplace la liste de
la suite 2 : 1) arrêt de la boucle sur état terminal (registre, inchangé) ;
2) **U30** — spéc H16 committée d'abord, puis les gardes, qui SUBSUME la « revue du
prompt » (la revue se fait en écrivant H16 : ce qui doit être imposé passe en
garde, ce qui doit être conseillé reste au prompt) ; 3) U24 (campagne pilote par le
harnais) ; 4) préparation du lancement live pour le responsable. Décision
réversible : les gardes sont bornées, configurables par construction, et l'A/B sur
`cible` mesurera leur effet.

---

## 2026-08-31 (suite 4) — Arrêt de la boucle sur état terminal, livré (préalable de U24)

**Session planifiée.** Unité : le défaut du registre du 2026-08-30 (la boucle
continuait d'appeler le modèle après la victoire, motif « tours_epuises » sur
partie gagnée), premier point de l'ordre révisé de la suite 3.

**Spécifié d'abord, committé avant le code.** §H8.3 réécrit : trois causes
d'arrêt par ordre de priorité — état terminal (le contrat `Environnement` porte
`etat_terminal() -> str | None`, l'environnement tranche, la boucle ne rappelle
plus le modèle), bornes d'actions, arrêt anticipé ; une tâche accomplie au
dernier tour se clôt sur son motif terminal, jamais « tours_epuises ». §A5.4
ajouté : l'interface ARC rend « victoire » sur `WIN` ; `GAME_OVER` n'est PAS
terminal (RESET relance, Bug-Fixing traite).

**Livré.** `avo.loop.boucle` (contrat + consultation en tête de tour et à la
clôture), `avo.arc.interface.etat_terminal()`. Preuves neuves : 3 unitaires
(WIN → « victoire », GAME_OVER → None, avant démarrage → None), 2 intégration
(arrêt sans nouvel appel après l'état terminal ; priorité sur « tours_epuises »
au dernier tour). Cassettes E2E régénérées (`make seed-e2e`) : victoire 316→228
échanges, state 120→76 (un appel par action exactement), échec 321→241. Rapport
A/B régénéré ; la preuve E2E qui épinglait 316/120 révisée dans le fichier avec
son motif (la règle a changé par spécification). Registre soldé (entrée retirée),
mentions périmées corrigées (U21, U27), CHANGELOG.

**Campagne complète de fin de session : INTÉGRALEMENT VERTE** — lint,
`ruff format --check`, mypy strict, 476 unitaires (+3), 140 intégration (+2),
4 E2E sur pile fraîche, `make build` vert.

**Où reprendre.** Ordre de la suite 3, point 1 fait : U30 maintenant — spéc H16
committée AVANT le code (gardes documentaire, prédiction, évaluation,
persistance dans P→I→E→B ; bornage des artefacts ; valable `transcript` et
`state` ; zéro indice de jeu), puis les gardes et leurs preuves, A/B sur
`cible`. Ensuite U24 (campagne pilote, plafonds obligatoires), puis préparation
du lancement live pour le rejeu du responsable (2026-09-01).

---

## 2026-09-01 — U30 livrée : les gardes de méthode dans les phases (spéc H16 puis code, tout vert)

**Session planifiée.** Unité : U30, deuxième point de l'ordre révisé de la
suite 3 du 2026-08-31 (spéc H16 d'abord, puis les gardes).

**Spécifié d'abord.** §H16 écrit et committé avant toute ligne de code :
principes H16.0 (le prompt conseille, la structure impose ; jamais fatales ;
bornées ; débrayables `AVO_GARDES` ; artefacts bornés), quatre gardes H16.1–H16.4,
observabilité H16.5 ; `AVO_GARDES`/`AVO_GARDE_RETRIES` en H3.1.

**Livré.** Verrou Planning→Implementation (WORKING vide ou GUIDE dû = outils
d'action verrouillés, redemandes bornées, tour clos sans action au budget
épuisé) ; paramètre `prediction` requis sur les outils d'action, acheminé
tronqué (2000 car.) vers `reasoning` du fil officiel ; invite d'évaluation
prédit-contre-observé avec `VERDICT:` exigé (issue prudente : réputé contredit) ;
persistance par compteur d'écritures monotone des notes ; portage au mode
`state` (lignes `PREDICTION:`/`VERDICT:` extraites avant que Rₜ soit jeté,
`hypotheses` de Σ comme artefact documentaire, action retenue gratuite).
Correction liée, mesurée en écrivant la garde : une action refusée par un outil
(arguments invalides, prédiction absente) relisait l'issue PRÉCÉDENTE et comptait
une action jamais jouée — `_jouer_action` compare maintenant l'identité de
l'issue avant/après.

**Prouvé.** 17 unitaires boucle (les quatre gardes, deux modes, débrayage,
issue prudente), 6 unitaires interface (schéma, troncature, RESET sans
reasoning), intégration sur `cible` sous gardes (76 actions, RHAE 100.00,
artefacts présents, zéro événement de garde au nominal) + A/B avant/après
gardes (mêmes issues, mêmes appels sur politique conforme, artefacts en plus).
Cassettes E2E régénérées sous gardes : mêmes 228/241/76 échanges — la méthode ne
coûte rien quand les artefacts arrivent du premier coup. Campagne complète
INTÉGRALEMENT VERTE : lint, `ruff format --check`, mypy strict, 499 unitaires
(+23), 142 intégration (+2), 4 E2E sur pile fraîche, `make build`.

**Où reprendre.** Ordre de la suite 3 : points 1 et 2 faits. Maintenant U24
(campagne pilote par le harnais, [LIVE], plafonds §A7.1 OBLIGATOIRES, garde de
publication levée par l'autorisation du 2026-08-30), puis préparation du
lancement live pour le rejeu du responsable avec `qwen3.6:35b` (`run-arc --mode
live` prêt : plafonds documentés, artefacts lisibles, reprise sûre). Les gardes
sont actives par défaut : le rejeu du responsable les exercera ; leur effet réel
sur un modèle vivant se lira dans `reasoning` des scorecards et les métriques
`garde`.

---

## 2026-09-01 (suite) — U24 : périmètre de la campagne pilote, consigné AVANT lancement

**Session planifiée, autorisation du responsable du 2026-08-30** (jouer ARC Prize,
ouvrir et clore des scorecards en son nom, garde de publication levée ; plafonds
§A7.1 obligatoires). Fumée live préalable : TOUT VERT (version 0.32.14,
`qwen3.6:35b` servi, complétion et appel d'outil à travers le pont 443).

**Préalable codé dans cette session** (couvert par §A5.3/§A1.4, commit `cfea9cc`) :
le résumé de scorecard est persisté à la fermeture (`scorecard.json` du workspace)
et réconcilié champ à champ avec les compteurs locaux — la preuve « réconciliation
exacte » de U24 était impossible sans cela, un scorecard fermé n'étant plus
relisible (404 mesuré).

**Périmètre du pilote — serré, un seul jeu :**

- jeu : `r11l-495a7899` (6 niveaux, baselines [22, 33, 51, 26, 52, 49], tag
  `click`) — service PROUVÉ par la sonde U22 ; le moins cher du listing
  (`cd82-…`) est écarté car mesuré « listé non servi » (§A1.4) ;
- plafonds (§A7.1, tous obligatoires) : 80 actions/niveau, 300 actions/jeu,
  1 800 s/jeu, 1 500 000 tokens/jeu, 400 tours max ;
- mode `transcript` (défaut), gardes H16 ACTIVES (défaut) — leur premier
  exercice sur modèle vivant ; prédictions attendues dans `reasoning` du
  scorecard ;
- `run-id` : `pilote-u24` ; commande exacte :
  `make run-arc ARGS="--mode live --games r11l-495a7899 --actions-max-niveau 80
  --actions-max-jeu 300 --budget-secondes-jeu 1800 --budget-tokens-jeu 1500000
  --tours-max 400 --run-id pilote-u24 --j-autorise-la-publication"`.

Attendu du pilote : débits réels, coût par tour, comportement des gardes et du
harnais sur un jeu officiel inconnu — jamais une adaptation à ce jeu
(interdiction de benchmaxing, CLAUDE_PROJECT.md).

---

## 2026-09-01 (suite 2) — U24 : trois mesures live, deux corrections générales, périmètre ajusté AVANT relance

**Mesuré sur l'API officielle (plomberie hors-jeu, autorisée) :**

1. Le lancement sur `r11l-495a7899` a été refusé : `400 SERVER_ERROR « game …
   not found »`. Sondage dédié (scorecard `b59c1306…`, étiqueté `probe`) : sur
   cinq candidats, SEUL `cd82-fb555c5d` est servi aujourd'hui — celui-là même
   qui était refusé le 2026-08-31. **L'ensemble servi varie dans le temps**
   (§A1.4 mis à jour).
2. **L'affinité par cookies couvre le scorecard** : `close` sans les cookies de
   la session d'ouverture → `404 VALIDATION_ERROR « scorecard not found »` ;
   avec le pot (`AWSALB*`) → `200` et le résumé complet (champs additionnels
   mesurés : `score`, `total_*`, `tags_scores`). §A1.4 mis à jour.
3. Le résumé de fermeture mesuré confirme la forme attendue par `reconcilier`.

**Corrigé en conséquence (général, aucun indice de jeu)** : la fabrique de
clients de la campagne partage UN transport (un pot de cookies) entre ouverture,
jeux et fermeture (`fabrique_partagee`, §A7.4) ; un jeu refusé par le backend
n'avorte plus la campagne — refus nommé persisté (`refus` de l'état), métrique,
section du rapport, hors score, jamais rejoué par la reprise (§A7.4). Preuves :
2 unitaires (persistance du refus + transport partagé), 4 unitaires de
réconciliation.

**Scorecards de cette investigation** : `2abc230e…` (pilote avorté, vide) et
`b59c1306…` (sondage) n'ont pas pu être refermés — ouverts sans pot de cookies,
leur backend d'origine est inatteignable (mesuré : `404` à la fermeture). Limite
nommée : ils restent ouverts, vides ou quasi vides, étiquetés.

**Périmètre relancé (mêmes plafonds, consigné avant lancement)** : un jeu,
`cd82-fb555c5d` (6 niveaux, baselines somme 171, tag `keyboard_click`), 80
actions/niveau, 300 actions/jeu, 1 800 s/jeu, 1 500 000 tokens/jeu, 400 tours,
`run-id: pilote-u24b`, gardes actives, mode `transcript`.

---

## 2026-09-01 (suite 3) — Pilote b : les gardes vivent, l'endpoint casse à ~120 k, robustesse corrigée, relance c

**Mesuré sur `pilote-u24b` (cd82-fb555c5d, 17 appels, 3 actions, ~10 min)** :

- **Les gardes H16 s'exercent sur un modèle vivant et convergent** : garde
  documentaire redemandée 2× puis WORKING écrit ; garde d'évaluation redemandée
  2× puis VERDICT rendu ; les trois actions jouées portent leur prédiction
  (champ `reasoning` du scorecard).
- **Le prompt croît de ~30-40 k tokens par tour** en mode `transcript` (la
  grille 64×64 ≈ 9 k tokens revient dans l'observation de Planning, le résultat
  d'outil d'action ET l'évaluation) : 9 k → 122 k en 17 appels.
- **L'endpoint casse au-delà de ~120 k tokens de prompt à travers le pont** :
  série de `500` (40 s avant premiers en-têtes côté pont, préremplissage des
  gros deltas), retries épuisés à ~140 k → le run avortait SANS rapport ni
  fermeture de scorecard. Scorecard `pilote-u24b` resté ouvert (3 actions
  publiées) — non refermable sans les cookies du conteneur défunt, limite nommée.

**Corrigé (général)** : un échec d'inférence à retries épuisés (`ServerError`,
`TransportError`) clôt désormais le JEU en échec nommé — même traitement que le
refus de protocole (§A7.4 amendé) : état persisté, métrique, section du rapport,
scorecard fermé, campagne poursuivie. Preuve d'intégration : `500` permanent →
rapport écrit, résumé persisté, refus nommé.

**Recette d'exploitation pour la relance et le rejeu du responsable** (aucun
changement de code, configuration existante) : demander une fenêtre plus courte
pour que la continuation VISTA arrive AVANT la zone de casse —
`OLLAMA_CONTEXT_LENGTH=98304` → budget de prompt ≈ 81 k, continuation à 85 % ≈
69 k. Le plafond par clé (229 376) reste vrai ; c'est le débit de préremplissage
à travers le pont qui borne en pratique.

**Relance (périmètre consigné avant lancement)** : mêmes plafonds et même jeu
que le pilote b, `run-id: pilote-u24c`, avec `OLLAMA_CONTEXT_LENGTH=98304` dans
l'environnement du run.

---

## 2026-09-01 (suite 4) — Pilote c dépouillé, deux correctifs généraux, relance d

**Pilote `pilote-u24c` (cd82-fb555c5d, fenêtre 98 304)** : jeu servi, 3 actions
jouées (réconciliation locale/API exacte 3 = 3), gardes H16 exercées, puis série
de `500` à retries épuisés à ~48 k de prompt (4 tentatives, ~3,5 min) — l'échec
nommé du 2026-08-31 a fonctionné : campagne terminée, scorecard
`2e57f802…` fermé, résumé et rapport persistés. Rapport committé :
`docs/rapports/pilote-u24c.md`. La casse n'est PAS la fenêtre : c'est l'endpoint
sous charge à travers le pont (les 500 isolés des tours précédents guérissaient
au premier retry).

**Corrigé (général, spéc amendée avant code, tout committé)** :

1. §A7.3 : les lignes d'inférence de la section Coûts viennent des MÉTRIQUES du
   run — le pilote c a montré un rapport annonçant 0 token quand 149 705 avaient
   été dépensés par un jeu clos en échec nommé ; l'écart actions/tours des jeux
   refusés est nommé dans le rapport.
2. §H4.5 : retries étendus à six requêtes (paliers 45 s et 90 s) — à travers le
   pont chaque tentative échouée réchauffe le cache de préfixe, la patience
   transforme une panne transitoire en retard.
3. mypy strict rétabli : les scénarios de campagne héritent d'un socle partagé au
   lieu d'emprunter les méthodes attribut par attribut (préexistant, bloquait la
   campagne de preuves).

**Périmètre `pilote-u24d`, consigné avant lancement** : mêmes jeu et plafonds que
c (cd82-fb555c5d, 80 actions/niveau, 300 actions/jeu, 1 500 000 tokens/jeu,
400 tours, fenêtre 98 304, gardes actives, mode transcript) SAUF budget temps
réduit à 1 200 s/jeu pour tenir dans la session — point tranché : un pilote
borné et terminé vaut mieux qu'un pilote interrompu par la fin de machine.

---

## 2026-09-01 (suite 5) — U24 CLOSE : pilote d mené à terme, réconciliation exacte

**Mesuré sur `pilote-u24d` (cd82-fb555c5d, fenêtre 98 304, budget 1 200 s)** :

- le jeu est joué JUSQU'AU PLAFOND de temps, arrêt propre « budget de temps du
  jeu épuisé », scorecard `3b34284d…` fermé, résumé persisté, réconciliation
  locale/API EXACTE (6 actions = 6, `divergences: []`) ;
- la recette fenêtre courte FONCTIONNE : 2 continuations en contexte frais,
  prompt maximal 73 180 tokens — la zone de casse (~120 k) n'est jamais
  approchée ; l'hypothèse « casse à ~48 k » du pilote c est REQUALIFIÉE : c'était
  une panne transitoire de l'endpoint, pas un seuil — le pilote d a franchi 46 k
  puis 73 k sans encombre sous retries patients ;
- retries patients (§H4.5 six requêtes) : tous les `500` absorbés, zéro fatal ;
- débits réels qwen3.6:35b via le pont : 28 appels, 1 105 505 tokens de prompt,
  7 874 générés, 554,6 s d'inférence, ~3,7 min par action jouée ;
- comportement : 6 actions, 0/6 niveaux en 20 min — l'exploration est lente,
  dominée par le préremplissage ; RHAE 0.00 par plafond de complétion (§A6.1).
- la section Coûts du rapport porte la dépense réelle (correctif A7.3 de cette
  session, constaté en conditions réelles).

**Corrigé en cours de session (général)** : l'A/B sur rejeu épinglait un
environnement incomplet — le `.env` local (fenêtre 98 304) fuyait dans
`options.num_ctx`, le rejoueur rendait `599`, les deux mini-campagnes étaient
refusées et le rapport A/B tombait à zéro. Épinglage complet aligné sur
`tests/e2e/scenarios.ENV_EPINGLE` ; les 4 E2E repassent en 30 s.

**U24 passe à `[x]`** : toutes ses preuves sont réunies (rapport et scorecard
référencés, réconciliation exacte, limites énoncées). Point tranché : la mention
« en session interactive » de la spéc visait l'accord du responsable, donné le
2026-08-30 pour les sessions planifiées.

**Où reprendre.** Ordre du plan : U25 (campagne étendue et rapport final) — son
périmètre s'arrête AVEC le responsable au vu de U24 (cas d'arbitrage 3 si rien
au dépôt ne le fixe ; relire A7 et la dernière entrée avant de lancer quoi que
ce soit). Les scorecards `2abc230e…`, `b59c1306…` (2026-09-01, investigation) et
`pilote-u24b` restent ouverts côté ARC, non refermables (cookies des conteneurs
défunts) — limite connue, sans action possible depuis ici.

---

## 2026-09-01 (suite 6) — U28 : lancement de l'A/B réel, mode `state`, périmètre consigné avant lancement

**Choix d'unité (point tranché).** L'ordre du plan désigne U25, mais sa spécification
arrête son périmètre AVEC le responsable au vu de U24 (cas d'arbitrage 3 : ni la
demande, ni le journal, ni la spécification ne fixent jeux/plafonds/budget de la
campagne étendue, et deux périmètres raisonnables donnent deux rapports finaux
différents ; cas 2 en sus : la dépense d'inférence engagée est substantielle).
L'arbitrage est demandé au responsable ; **ce qui reste livrable sans la réponse est
U28**, dont le périmètre est entièrement fixé par le dépôt (rejeu du périmètre
pilote U24d en mode `state`) et dont la mesure ALIMENTE la décision U25
(recommandation du mode par défaut). Le point « en session interactive » de U28 est
couvert par le point tranché de U24 (autorisation du 2026-08-30 pour les sessions
planifiées).

**Vérifié avant lancement (lecture seule)** : `cd82-fb555c5d` est listé par
`/api/games` aujourd'hui, baselines [55, 8, 41, 21, 23, 23] (somme 171),
identiques au pilote U24d — la comparaison A/B est à baseline constante.

**Périmètre `ab-u28-state`, consigné avant lancement** : mêmes jeu et plafonds que
`pilote-u24d` — `cd82-fb555c5d`, 80 actions/niveau, 300 actions/jeu, 1 200 s/jeu,
1 500 000 tokens/jeu, 400 tours, fenêtre `OLLAMA_CONTEXT_LENGTH=98304` (recette du
2026-09-01), gardes H16 actives — SAUF `AVO_CONTEXT_MODE=state` (l'objet même de
U28, §H15.8) ; `run-id: ab-u28-state`, commande :
`make run-arc ARGS="--mode live --games cd82-fb555c5d --actions-max-niveau 80
--actions-max-jeu 300 --budget-secondes-jeu 1200 --budget-tokens-jeu 1500000
--tours-max 400 --run-id ab-u28-state --j-autorise-la-publication"`.

Attendu : mesures en main contre `docs/rapports/pilote-u24d.md` (RHAE, actions,
tokens prépremplis/générés, appels, incidents `413`/retries de patch, effet du
cache de préfixe) ; rapport comparatif committé sous `docs/rapports/`.

---

## 2026-09-01 (suite 7) — U28 mesuré : l'A/B réel donne 33 actions contre 6, recommandation `state` consignée

**Mesuré sur `ab-u28-state`** (`cd82-fb555c5d`, mêmes plafonds/fenêtre que
`pilote-u24d`, gardes actives, mode `state`) : jeu joué au plafond de 1 200 s,
arrêt propre, scorecard `4cedc4e1…` fermé, réconciliation locale/API EXACTE
(33 = 33, `divergences: []`). 43 appels, prompt borné 8 890–9 223 tokens (O(1)
du papier constaté en réel), 0 continuation, 389 879 tokens de prompt cumulés
(contre 1 105 505 pour 6 actions en `transcript`), 1 retry de patch (clé hors
schéma refusée en la nommant, corrigée au retry), 1 intervention superviseur,
1 `500` absorbé. Dépouillement complet : `docs/rapports/ab-u28-state.md`.

**Corrigé (général, spéc amendée avant code, test rouge avant correction)** :
la ponctuation traînante du jeton de nom d'action est normalisée (§H15.8) — un
tour entier était perdu sur « action1, » (bruit de format, taxonomie
SKILL.state). Défaut rencontré et traité dans la même session : le test CLI de
campagne n'épinglait pas `AVO_CONTEXT_MODE` et rougissait sous un `.env` local
en mode `state` (même famille que l'incident A/B du 2026-09-01 ; épinglage
aligné, reproduction puis preuve verte).

**U28 passe à `[~]` avancé** : tout le mesurable est livré et vérifié ;
seule la DÉCISION du responsable (mode par défaut, avec le périmètre U25)
reste ouverte — recommandation consignée : `state` par défaut.

**Où reprendre.** U25 attend l'arbitrage du responsable sur son périmètre
(cas 3, demandé en suite 6) et sa décision de mode (recommandation : `state`).
Sans réponse, il ne reste aucune unité constructible : U29 est hors périmètre
(arbitrage requis), U25/U28 attendent le responsable — la prochaine session
vérifie d'abord si une réponse est arrivée (journal, backlog, instruction),
sinon elle applique §4.5 (elle établit le cas 2 et arrête proprement la
boucle planifiée si rien d'autre n'est constructible).

---

## 2026-09-01 (suite 8) — ARRÊT de la boucle planifiée : cas 2 du CloudWorker §4.5 établi

**Vérifié en ouverture.** Aucune réponse du responsable n'est arrivée depuis la
suite 7 : `origin/main` s'arrête au commit de la session précédente, le prompt de
la tâche planifiée est inchangé (autorisations du 2026-08-30, rien qui fixe le
périmètre U25), le registre d'incohérences n'a aucune entrée ouverte.

**Unités restantes, vérifiées une par une (condition du §4.5)** :

- **U25 `[ ]`** — sa spécification arrête son périmètre AVEC le responsable ;
  arbitrage (cas 3 + 2) demandé en suite 6, non rendu. Bloquée.
- **U28 `[~]`** — tout le mesurable est livré et vérifié (rapport
  `docs/rapports/ab-u28-state.md`, réconciliation exacte) ; seule reste la
  DÉCISION du responsable (mode par défaut, avec le périmètre U25). Bloquée par
  le même arbitrage.
- **U29 `[ ]`** — hors périmètre par décision du 2026-08-27 ; n'entre pas dans
  l'ordre d'exécution tant que le responsable n'a pas élargi le périmètre.
  Bloquée.

L'autorisation permanente « améliorer le fonctionnement GÉNÉRAL du harnais
d'après les résultats collectés » n'ouvre aucune unité constructible ici : aucun
défaut n'est consigné au registre, et la seule amélioration désignée par les
mesures — basculer le défaut sur `state` — est précisément la décision réservée
au responsable (contrat U28). L'inventer serait du périmètre ajouté.

**Cas 2 du §4.5 établi** : tout ce qui reste est bloqué par un arbitrage
relevant de « Demande d'arbitrage » (CLAUDE.md) et non rendu. La boucle
planifiée est donc ARRÊTÉE.

**Limite d'outillage, nommée.** Cette session ne dispose d'aucun outil pour
supprimer la tâche planifiée du nuage (aucune tâche locale à couper ;
la planification vit dans la configuration du compte). Conformément au §4.5
point 1 : le responsable doit supprimer lui-même la tâche planifiée
« CloudWorker » dans son interface. Tant qu'elle n'est pas supprimée, chaque
exécution refera ce même constat d'arrêt sans rien modifier.

**Points tranchés de la session** : pile compose non montée et campagne de
preuves non exécutée — aucun code n'est modifié (session documentaire d'arrêt,
cas de blocage réel consigné, §4.2 bis) ; le temps d'une campagne de 40–70 min
n'apprendrait rien sur un dépôt inchangé dont la campagne complète était verte
en suite 7.

**Où reprendre, quand l'arbitrage sera rendu.** Le responsable fixe : (1) le
périmètre U25 (jeux, plafonds, budget temps/coût) ; (2) le mode par défaut
(recommandation mesurée : `state`). La session suivante exécute alors U25 par
tranches reprenables (A7), solde U28 en consignant la décision, et U29 reste
fermée sauf élargissement explicite. Scorecards `2abc230e…`, `b59c1306…` et
`pilote-u24b` : toujours ouverts côté ARC, non refermables d'ici (limite connue).

---

## 2026-09-01 (suite 9) — Arbitrages rendus par le responsable : U25 débloquée, `state` par défaut, mission permanente de concours

Session interactive. Le responsable a rendu en séance les arbitrages demandés en
suite 6 et constatés bloquants en suite 8 — l'arrêt de la boucle prononcé en
suite 8 est donc LEVÉ :

1. **Budget U25** : illimité TANT QUE le modèle de travail est `qwen3.6:35b` ET que
   l'inférence passe par le gateway LLM du responsable. Le reste du périmètre
   proposé est validé : tous les jeux que `/api/games` déclare, plafonds par jeu du
   pilote (80 actions/niveau, 300 actions/jeu, 1 200 s/jeu, 1 500 000 tokens/jeu,
   400 tours). Consigné dans l'unité U25.
2. **Mode par défaut** : `state` (« c'est plus cohérent ») — la recommandation
   mesurée de U28 est suivie. La bascule du défaut `AVO_CONTEXT_MODE` (spéc §H15.7
   amendée, `avo.config`, README) s'applique dans cette même session, chunk de code
   dédié, preuves ciblées puis campagne complète.
3. **Mission permanente** : la boucle planifiée change de raison d'être — RÉUSSIR
   ARC Prize. Chaque itération joue (campagne officielle au périmètre U25), observe
   les résultats, puis améliore ou corrige le fonctionnement GÉNÉRAL du harnais
   d'après ces mesures. Nouvelle unité PERMANENTE U31 (lot I) ;
   `CLAUDE_PROJECT.md` (« Concours permanent ») et `docs/MASTER_PLAN.md` §7
   portent la règle. La condition d'arrêt « backlog terminé » ne s'applique plus
   tant que U31 est active.
4. **U29** : détails fournis au responsable en séance (InterCode CTF, τ-Bench,
   patron SkillExecBench) ; décision toujours ouverte, l'unité reste hors
   périmètre.

**Où reprendre.** La prochaine session planifiée exécute U31 : ouvrir la campagne
au périmètre U25 (mode `state`) et jouer la première tranche, puis observer et
améliorer sur les mesures.

---

## 2026-09-01 (suite 10) — Bascule `state` par défaut livrée et prouvée, U28 close

**Livré** : défaut `AVO_CONTEXT_MODE=state` (`avo.config`), spéc §H15.0 réécrite
(les deux modes livrés, `state` défaut sur mesures) et §H15.7 alignée, README, DAT
et CHANGELOG dans le même geste. **Preuves révisées, pas contournées** (règle
« preuve rougie par changement de règle ») : le test du défaut affirme désormais
`state` et un test `transcript` explicite est ajouté ; les bancs dont les cassettes
et réponses scriptées encodent le chemin `transcript` épinglent leur mode
(`test_gardes.py`, `test_boucle_complete.py`, `test_campagne_sur_rejeu.py`,
`test_gardes_sur_cible.py`, `test_interface_sur_arc_replay.py`, `ENV_EPINGLE` des
E2E) — même famille que l'incident du test CLI de campagne (2026-09-01). Constat
utile : sous le nouveau défaut, l'E2E victoire s'appariait par accident à la
cassette `state` (même discriminant 4096) pendant que l'E2E échec rougissait —
l'épinglage rétablit l'intention des deux.

**Campagne complète verte** : lint, ruff format, mypy strict (97 fichiers),
508 unitaires, 145 intégration, 4 E2E sur pile fraîche, build. **U28 passe à
`[x]`.**

**Où reprendre.** La prochaine session planifiée exécute U31 (mission permanente) :
ouvrir la campagne au périmètre U25 — tous les jeux de `/api/games`, plafonds
80/300/1 200 s/1,5 M tokens/400 tours, défaut `state` désormais actif — et jouer
la première tranche, puis observer et améliorer sur les mesures.

---

## 2026-09-01 (suite 11) — U29 ouverte comme terrain d'affinage, campagne ARC mise sous déclencheur

Session interactive, instruction du responsable : le harnais s'AFFINE d'abord sur
les trois bancs proposés (a : patron SkillExecBench ; b : InterCode CTF ; c :
τ-Bench), et la campagne ARC ne se (re)jouera que lorsqu'il aura des résultats
intéressants — scores comparables aux modèles de taille similaire, ou score qui a
cessé de progresser.

**Persisté** : U29 ouverte (ordre a → b → c, spécification S1+ d'abord, scores de
référence des modèles open-weight comparables à consigner par la spéc depuis
l'export SKILL.state) ; U25 gardée par le déclencheur (plateau opérationnalisé par
défaut, révisable : trois itérations d'amélioration successives sans gain sur le
banc concerné) ; U31 réécrite — la cible d'évaluation courante est U29 tant que le
déclencheur n'est pas atteint, la campagne ARC ensuite ; `CLAUDE_PROJECT.md`
(« Mission permanente ») et `MASTER_PLAN` §2/§7 alignés.

**Où reprendre.** La prochaine session planifiée exécute U31 avec pour cible U29 :
écrire et committer la spécification S1+ du banc a (patron SkillExecBench —
générateurs seedés déterministes, score continu, scores de référence consignés),
puis coder par unités d'une session.

---

## 2026-09-01 (suite 12) — U31/U29 : spécification du banc a écrite, U29a1 (environnement Entrepôt) livrée et close

Session planifiée. Cible désignée par la suite 11 : U31 → U29, banc a.

**Livré** : `docs/SPEC_BANCS.md` (§S1–§S7), committée avant le code — cadre commun
des bancs (adaptateurs minces sur le contrat `Environnement` §H8.2, noyau §H
intouché, règles du banc DONNÉES à l'agent contrairement à §A5.1, différence
assumée en §S1.3), environnement Entrepôt normé (§S3), Dépôt logiciel en
invariants (§S4), score continu (§S5), scores de référence open-weight consignés
(§S5.4 : fourchette Qwen-3-8B ↔ Gemma-4-31B pour le déclencheur U25), découpage
U29a1–a4 (§S7). Puis U29a1 codée : `src/avo/bancs/skillexec/{generation,entrepot,
score}.py` — générateur d'épisodes seedé à DOUBLE flux (événements/bruit séparés :
le niveau de bruit ne change pas la tâche), état de vérité, transitions validées,
obligations par événement, relevé `en_dict()` pour le futur `banc.json`.

**Points tranchés** (motifs en §S3.4 et §S3.7) : les événements référencent l'état
NOMINAL d'un jeu parfait — épisodes comparables entre runtimes, la divergence de
l'agent se paie au score ; une action invalide consomme l'événement (un agent
bloqué ne boucle pas) ; l'article d'une réception entre au quai à l'émission de
l'événement, un rangement tardif reste valide mais jamais correct.

**Preuves** : 26 unitaires du banc verts ; balayage « mots du banc hors
`src/avo/bancs/` » vide ; campagne complète verte (lint, ruff format, mypy strict
103 fichiers, 534 unitaires, 145 intégration, 4 E2E sur pile fraîche, build).
U29a1 `[x]`, U29 passe `[~]`.

**Où reprendre.** U29a2 (§S7) : `adaptateur.py` (contrat `Environnement`, outils
étiquetés `action` avec `prediction`, contexte de tâche §S6.2) + sous-commande CLI
`banc`, cassette de rejeu, intégration + E2E, premier relevé live 3 seeds aux
horizons 10 et 25, consigné au journal pour amorcer le suivi du déclencheur U25.

---

## 2026-09-01 (suite 13) — U31/U29a2 : décisions d'ouverture, avant le code

Session planifiée. Cible désignée par la suite 12 : U29a2 (adaptateur harnais +
CLI `banc`). La spécification existe (§S6) et couvre le reste à livrer : pas de
réécriture, code direct (exception « spécification existante » du contrat worker).
Trois points d'implémentation tranchés, persistés ici avant la première ligne :

1. **Message système du mode `state`** : `_messages_etat` employait la constante
   `prompts.SYSTEME` au lieu du message système du contexte monté — le mode
   `transcript` honore `Contexte.systeme`, le mode `state` l'ignorait. Sans cette
   surface, aucun adaptateur ne peut fournir son contexte de tâche à K (§H16.1,
   §S6.2). §H15.8 est amendé sur ce point précis ; le défaut reste
   `prompts.SYSTEME`, ARC inchangé octet pour octet (cassettes intactes). Issue
   écartée : injecter le protocole du banc dans `GUIDE.md` — les notes sont la
   mémoire de l'agent, pas la documentation du responsable.
2. **L'issue de la dernière action entre dans l'observation du banc** : en mode
   `state`, le prompt d'un pas ne porte que (P, Σ, O) ; sans cela l'agent ne
   verrait jamais « Succès/error » de son action précédente, que §S2.3 lui donne
   (« les observations textuelles et les issues de ses actions »). C'est
   l'adaptateur qui compose, le noyau est intouché.
3. **`tours_max` par défaut de la CLI `banc` = 4 × horizon** : un pas retenu par
   une garde ou une résolution d'action refusée consomme un tour sans consommer
   d'événement ; 4× laisse ces détours possibles sans permettre une boucle sans
   fin. Surchargé par `--tours-max`.

La sous-commande `banc` du noyau reste générique : `cli.py` délègue à
`avo.bancs.executer_banc` sans nommer aucun banc ni environnement (balayage
« zéro indice » préservé sur le noyau).

---

## 2026-09-01 (suite 14) — U29a2 : premier relevé live du banc a (reprise et clôture)

Session planifiée. La session précédente (suite 13) a livré et poussé TOUT le code
de U29a2 — adaptateur, CLI `banc`, intégration, E2E, documentation — plus deux
améliorations générales désignées par son relevé live (retry `RemoteDisconnected`
§H4.4-4.5 ; normalisation de la syntaxe d'appel de fonction et repli par espaces
§H15.8), mais a été interrompue avant la consignation du relevé, le journal et le
backlog. Cette session reprend : relevé live (3 seeds × horizons 10 et 25), puis
clôture.

Pile montée et seedée (CA du proxy déposé dans `certs/`, dockerd manuel),
`make smoke-live` tout vert (qwen3.6:35b servi à travers le pont 443).

**Relevé live, horizon 10** (`python -m avo banc skillexec --env entrepot
--seed S --horizon 10 --mode live`, défaut `state`, bruit 0, gardes actives) :

| seed | score | correctes | incorrectes | invalides | tours | tokens | durée |
|---|---|---|---|---|---|---|---|
| 1 | 0,80 | 8 | 1 | 1 | 13 | 18 500 | 536 s |
| 2 | 0,80 | 8 | 1 | 1 | 13 | 17 262 | 333 s |
| 3 | 0,60 | 6 | 3 | 1 | 14 | 16 718 | 314 s |

Moyenne h10 : **0,73** — sous la fourchette de référence §S5.4
(Qwen-3-8B 0,94 ; Gemma-4-31B 0,98). Les normalisations §H15.8 de la suite 13
portent : plus aucun tour perdu en résolution d'action (contre 11/30 au relevé
d'hier soir) ; les pertes restantes sont des choix d'action erronés, pas du bruit
de format.

---

## 2026-09-01 (suite 15) — U31/U29a2 livrée et close : adaptateur + CLI `banc`, premier relevé live, deux corrections génériques désignées par la mesure

Session planifiée — celle-là même qui a écrit la suite 13 et livré le code ; la suite 14 ci-dessus est une session parallèle (démarrage horaire suivant) qui a joué son propre relevé h10 (seeds 1–3) pendant que celui-ci s'exécutait, et confirme indépendamment l'effet des normalisations. **Livré et intégralement vérifié** :

- **U29a2** : adaptateur du banc a (`src/avo/bancs/skillexec/adaptateur.py` —
  contrat `Environnement`, quatre outils `action` avec `prediction`, contexte de
  tâche §S6.2 donné en message système, issue de la dernière action composée
  dans l'observation, relevé `banc.json`), sous-commande CLI `banc` générique
  (dispatch sous `avo.bancs`, aucun mot de banc dans le noyau), §H15.8 amendé :
  le mode `state` emploie le message système du contexte monté (défaut
  `prompts.SYSTEME`, ARC inchangé). Preuves : 18 + 8 unitaires, intégration en
  rejeu HTTP réel, cassette E2E `e2e_banc_entrepot.jsonl` (6 échanges, double
  génération comparée) + scénario CLI réelle contre la pile. Campagne complète
  verte deux fois (finale : lint, format, mypy strict 111 fichiers,
  562 unitaires, 148 intégration, 5 E2E, build).
- **Correction générique 1 (transport)** : une coupure de connexion avant les
  premiers en-têtes (`RemoteDisconnected`, reset nu pendant le handshake) levait
  une exception NON TYPÉE qui arrêtait le run — mesurée deux fois sur le pont
  443 au premier essai de relevé. Typée `TransportError`, donc retentée (§H4.5) ;
  défaut reproduit sur ligne de base avant correction, 2 unitaires ajoutés.
  Vérifiée en réel : les coupures suivantes ont été absorbées par retry.
- **Correction générique 2 (résolution d'action, §H15.8 amendé avant code)** :
  le modèle écrit `wait()`, `store(article_1, etagere_2)` ou des valeurs
  séparées par des espaces — 21 tours perdus sur l'épisode h25-s101. Normalisées
  (syntaxe d'appel de fonction, repli par espaces quand les virgules ne rendent
  pas le compte), 8 unitaires + 1 intégration. Vérifiée en réel : 0 refus de
  résolution sur les deux épisodes h25 joués après le correctif.

**Premier relevé live du banc a** (Entrepôt, bruit 0, mode `state`, gardes
actives, `qwen3.6:35b` via le pont 443 ; runs `banc-live-*`, non committés) :

| h  | seed | score | corr/inc/inv | tours | tokens | s |
|----|------|-------|--------------|-------|--------|---|
| 10 | 101  | 0,70  | 7/1/2        | 14    | 17 486 | 346 |
| 10 | 102  | 0,70  | 7/3/0        | 22    | 25 049 | 561 |
| 10 | 103  | 0,70  | 7/1/2        | 22    | 29 206 | 644 |
| 25 | 101  | 0,88  | 22/2/1       | 62    | 80 447 | 1 908 |
| 25 | 102  | 0,56  | 14/4/7       | 32    | 37 515 | 1 105 |
| 25 | 103  | 0,64  | 16/3/6       | 34    | 43 688 | 791 |

Moyennes : **h10 = 0,700**, **h25 = 0,693** (3 seeds chacun). Références §S5.4
(runtime SKILL.state) : h10 ∈ [0,94 ; 0,98], h25 ∈ [0,76 ; 0,84] — le harnais est
SOUS la fourchette du déclencheur U25 sur les deux horizons : l'affinage continue.
Homogénéité : h10×3 et h25-s101 joués AVANT la correction 2, h25-s102/s103 APRÈS
(chaque épisode est un processus neuf) ; h25-s103 est un rejeu après un
`ServerError HTTP 500` persistant (6 tentatives) — panne serveur, arrêt propre.

**Observations pour la suite** (mesures, pas encore d'unité) : les pertes
restantes sont de vraies erreurs de TENUE D'ÉTAT (6–7 invalides par épisode
h25 : mauvais article ou mauvaise étagère référencés après divergence) — le cœur
de ce que le banc mesure ; 4 patchs refusés sur clés `essais`/`objet` montrent
que le schéma Σ « arc-v1 » (§H15.6) est imposé à un banc qui n'est pas ARC —
piste générique : le schéma de Σ fourni par l'adaptateur de tâche, à SPÉCIFIER
avant tout code ; le superviseur est intervenu 1× (Bug-Fixing en rafale) : la
pile harnais entière fonctionne sur le banc.

**Environnement worker, mesuré** : pour tout run live Python, exporter
`SSL_CERT_FILE=/root/.ccr/ca-bundle.crt` (le proxy TLS interpose son autorité ;
`urllib` ne lit pas la configuration de curl) ET recharger `.env` explicitement
(`set -a; . ./.env; set +a`) : l'environnement du conteneur porte des `OLLAMA_*`
périmés (origine hors 443, plafond 114688) qui priment sur `.env` (§H3.1).

**Où reprendre.** U31 → U29a3 : environnement Dépôt logiciel — écrire d'abord le
détail exécutable de §S4 (dans ce chapitre), puis `depot.py` et ses preuves.
L'amélioration « schéma Σ par adaptateur » attend une spécification dédiée si la
prochaine mesure la confirme ; le relevé du déclencheur U25 s'étoffe en U29a4.
---

## 2026-09-01 (suite 16) — session parallèle : relevé h25 indépendant (seeds 1–3), incident d'endpoint mesuré, relevé d'incident spécifié

Session planifiée, démarrée au créneau horaire suivant la suite 14 et jouée en
PARALLÈLE de la suite 15 ci-dessus (constaté au push : la suite 15 avait déjà
clos U29a2). Cette session avait repris la consigne de la suite 14 — compléter le
relevé h25 (3 seeds) — et l'a exécutée sur les seeds 1–3 : mesure INDÉPENDANTE du
relevé 101–103 de la suite 15 — la session a été interrompue avant de consigner
ce relevé, qui est donc perdu (constat en suite 17). Pile montée
et seedée (dockerd manuel, CA du proxy dans `certs/`), `make smoke-live` tout
vert.

**Incident mesuré pendant le relevé.** Le seed 2 h25 est mort à mi-épisode :
l'endpoint a rendu des HTTP 500 continus de 20:53 à 20:57 (plus de quatre
minutes), les cinq relances §H4.5 (repli exponentiel 1,2 → 69,7 s) ont été
épuisées, et `ServerError` a remonté — 19 inférences et ~13 minutes perdues sans
AUCUN relevé : `banc.json` n'est écrit qu'au terme de l'épisode. C'est la même
famille de panne que le `ServerError` persistant déjà noté en suite 15
(h25-s103) : la panne y avait coûté un rejeu complet, ici elle coûte l'épisode.

**Décision (persistée avant le code).** §S5.3 amendé : le relevé s'écrit MÊME
quand l'épisode est interrompu — `arret` porte `incident : <classe>: <message>`,
les compteurs valent ce qui a réellement été consommé, l'erreur remonte
inchangée (aucun masquage, aucune perte silencieuse) ; un relevé dont
`evenements_consommes < horizon` n'entre dans aucune comparaison de scores.
Issue écartée : élever le plafond de relances §H4.5 — une panne peut durer
arbitrairement et ce plafond protège la latence de TOUS les appels ; l'invariant
est « aucune perte silencieuse », pas « attendre indéfiniment ». Le seed 2 sera
rejoué après le seed 3 pour compléter le relevé.

---

## 2026-09-01 (suite 17) — U31/U29a3 livrée et close : environnement Dépôt logiciel (§S4)

Session planifiée. Pile montée et seedée (dockerd manuel, CA du proxy dans
`certs/`), reprise désignée par la suite 15 : U29a3.

**Spécifié d'abord.** Détail exécutable de §S4 écrit et committé avant le code
(commit `3257a6f`) : la source (annexe B.1) ne donnant aucun algorithme pour cet
environnement, le patron mesuré de l'Entrepôt est transposé — état nominal,
événements référençant le nominal, une obligation par événement. Points tranchés
notables : cycle affectation → revue → [échec CI si défaut tiré, équiprobable] →
CI verte ; `merge` sur CI rouge VALIDE et cassant (donne son sens au « sans
casser la CI » de B.1 ; l'issue nomme la casse) ; demandes JUGÉES = celles dont
le `ci_verte` nominal est dans l'épisode, `resolution` nulle à dénominateur nul.

**Livré.** `src/avo/bancs/skillexec/depot.py` (commit `adf3989`) : générateur
déterministe, transitions `commit`/`create_pr`/`merge`/`fix_ci`/`wait`,
résolution au relevé. 30 unitaires (`tests/unit/test_banc_depot.py`), partie
parfaite h60 à score 1,0 et résolution 1,0, `wait` dû sur les trois divergences,
bruit C.3 sans effet sur les événements. Balayage « mots du banc hors
`src/avo/bancs/` » : vide (seuls faux positifs génériques `demande_outil`,
`lire_fichier_env`). Campagne complète verte : lint, mypy strict 112 fichiers,
592 unitaires, 148 intégration, 5 E2E, build.

**Tranché à la clôture.** Le branchement adaptateur+CLI du dépôt appartient à
U29a4, premier consommateur (campagne de banc) — §S7 amendé, message du dispatch
`avo.bancs` mis au vrai. La session de la suite 16 tournait encore en parallèle :
son relevé h25 (seeds 1–3) est consigné dans sa clôture ci-dessous ; le
déclencheur U25 s'appuie sur la série 101–103 de la suite 15, complète, et les
relevés suivants viennent de U29a4 (multi-seeds, les deux environnements).

**Où reprendre.** U31 → U29a4 : brancher le Dépôt logiciel à l'adaptateur et à
la CLI (§S6 : outils, contexte de tâche, dispatch, intégration + E2E), puis
campagne de banc — bruit, récupération d'état, relevés multi-seeds sur les deux
environnements, alimentation du déclencheur U25.
---

## 2026-09-01 (suite 16, clôture — consignée après la suite 17)

La session de la suite 16 s'est achevée après le push de la suite 17 ; sa
clôture vient donc ici, à sa place chronologique.

**Relevé live h25, seeds 1–3** (`python -m avo banc skillexec --env entrepot
--seed S --horizon 25 --mode live`, défaut `state`, bruit 0, gardes actives) —
mesure indépendante, complémentaire du relevé 101–103 de la suite 15 :

| seed | score | corr/inc/inv | évts | tours | tokens | durée | arrêt |
|---|---|---|---|---|---|---|---|
| 1 | 0,84 | 21/2/2 | 25/25 | 31 | 36 095 | 725 s | épisode épuisé |
| 2 | — | 7/2/2 | 11/25 | 14 | 17 665 | 592 s | incident HTTP 500 (3ᵉ tentative) |
| 3 | 0,44 | 11/4/10 | 25/25 | 35 | 45 029 | 1 473 s | épisode épuisé |

Le seed 2 reste SANS score comparable : trois tentatives, trois pannes
d'endpoint (20:53–20:57, 21:27–21:34, ~22:05 — HTTP 500 continus au-delà des
relances §H4.5). Écart nommé : le point h25-seed2 de cette série manque ; le
déclencheur U25 s'appuie sur la série 101–103 de la suite 15, complète. Sur les
seeds aboutis (1 : 0,84 ; 3 : 0,44), la variance rejoint celle de la suite 15
(0,88/0,56/0,64) : mêmes vraies erreurs de tenue d'état (10 invalides sur le
seed 3), même conclusion — l'affinage continue, sous la fourchette §S5.4.

**Livré et vérifié : relevé d'incident (§S5.3).** Défaut reproduit par test
unitaire avant correction (`test_incident_ecrit_le_releve_partiel_et_remonte`),
correction dans `jouer_episode` (écriture du relevé refactorisée, `arret` porte
l'incident, erreur remontée inchangée), VALIDÉE DEUX FOIS en conditions réelles
dans cette même session : les deux interruptions du seed 2 (r2 et r3) ont chacune
laissé leur `banc.json` d'incident, là où la première (avant correction) n'avait
rien laissé. Campagne complète verte après le changement : lint, ruff format,
mypy strict 110 fichiers, 563 unitaires, 148 intégration, 5 E2E sur pile
fraîche, build.

**Où reprendre.** La suite 17 ayant clos U29a3 entre-temps : U31 → U29a4,
brancher le Dépôt logiciel à l'adaptateur et à la CLI (§S6), puis campagne de
banc — bruit, récupération d'état, relevés multi-seeds sur les deux
environnements, alimentation du déclencheur U25. La piste « schéma Σ par
adaptateur » (suite 15) reste en attente d'une mesure qui la confirme.

---

## 2026-09-01 (suite 14, clôture — consignée après les suites 15–17)

La session de la suite 14 s'est achevée après les pushes des suites 15–17 ; sa
clôture vient ici. Constaté au push : U29a2 était déjà close (suite 15), U29a3
livrée (suite 17), et le relevé d'incident §S5.3 déjà spécifié ET livré — la
piste que cette session avait notée en observation. Aucun document n'est modifié
au-delà de la présente entrée ; le backlog distant fait foi.

**Relevé live h25, seeds 1–3** — TROISIÈME série indépendante, mêmes commandes
et conditions que les suites 15 (101–103) et 16 (1–3) :

| seed | score | corr/inc/inv | évts | tours | tokens | durée |
|---|---|---|---|---|---|---|
| 1 | 1,00 | 25/0/0 | 25/25 | 26 | 36 082 | 375 s |
| 2 | 0,76 | 19/1/5 | 25/25 | 32 | 41 781 | 761 s |
| 3 | 0,28 | 7/10/8 | 25/25 | 31 | 40 084 | 926 s |

Le seed 3 a exigé SIX lancements (cinq morts en rafale de HTTP 500 : 0, 8, 0,
19 et 3 événements consommés — antérieurs au relevé d'incident §S5.3, donc sans
`banc.json`) ; le sixième est complet. Lecture croisée des trois séries h25 :
la variance INTER-RUNS sur un même seed est du même ordre que la variance
inter-seeds (seed 1 : 1,00 ici contre 0,84 en suite 16 ; seed 3 : 0,28 contre
0,44) — un score h25 isolé ne dit rien, seule la moyenne multi-seeds
multi-séries alimente le déclencheur U25. Taxonomie confirmée : zéro tour perdu
en résolution d'action (normalisations §H15.8 efficaces sur les trois séries),
pertes = tenue d'état (identifiant inventé `article_4_new`, `move` répété trois
fois vers une étagère occupée, `wait` face à une réception).

**Campagne complète verte** (aucun code modifié par cette session) : lint, ruff
format 111 fichiers, mypy strict 110 fichiers, 562 unitaires, 148 intégration,
5 E2E sur pile fraîche, build — état AVANT la fusion des suites 15–17, qui ont
rejoué leur propre campagne en aval. Registre : entrée « contrôle `RESET` du
script de fumée périmé » consignée (poussée avec la suite 14).

**Où reprendre.** Inchangé de la suite 17 : U31 → U29a4 (branchement du Dépôt
logiciel à l'adaptateur et à la CLI, campagne de banc multi-seeds). La mesure
de variance inter-runs ci-dessus appartient au dossier du déclencheur U25.

---

## 2026-09-01 (suite 18) — U31/U29a4 : le Dépôt logiciel branché, premiers relevés live du dépôt

Session planifiée. Pile montée et seedée (dockerd manuel, CA du proxy dans
`certs/`), reprise désignée par la suite 17 : U29a4. La spécification (§S6,
§S4) couvrant déjà le branchement, aucun commit documentaire préalable — code
directement (§3.2 du CloudWorker, exception de reprise).

**Livré.** Adaptateur des deux environnements (`adaptateur.py`, commits
`e99ff11`/`cf3f3d8`) : mécanique de boucle factorisée en base commune générique
(observation, issue, motif de fin — identiques par construction), contexte de
tâche du dépôt (protocole §S4.2/§S4.5), cinq outils `action`, dispatch CLI
`--env depot`, résolution B.1 au relevé (incident compris). Points tranchés :
`jouer_episode` prend `environnement` (défaut `entrepot`, appels intacts) ; le
numéro de PR de `merge` reste `string` au schéma et s'analyse dans le moteur
(« 3 »/« #3 » se lisent, l'imprenable est invalide nommé qui consomme, §S4.6) —
issue écartée : type `integer` au schéma, qui ferait échouer la résolution AVANT
l'environnement et créerait un comportement différent entre outils.

**Prouvé.** 18 unitaires (`test_banc_adaptateur_depot.py`), intégration rejeu
HTTP deux passes avec résolution exacte, cassette `e2e_banc_depot.jsonl` seedée
(double génération comparée) + scénario CLI réel ; la cassette Entrepôt
régénérée est IDENTIQUE octet pour octet — la refactorisation ne change pas la
boucle. Campagne complète verte : lint, mypy strict, 610 unitaires,
149 intégration, 6 E2E, build.

**Relevé live du dépôt** (`--env depot --horizon 10 --mode live`, `state`,
gardes actives) — premier relevé de cet environnement :

| seed | bruit | score | corr/inc/inv | résolution | tokens | durée |
|---|---|---|---|---|---|---|
| 1 | 0 | 0,60 | 6/1/3 | 0,0 (0/2) | 22 930 | 148 s |
| 2 | 0 | 0,80 | 8/1/1 | 0,5 (1/2) | 25 434 | 241 s |
| 3 | 0 | 0,60 | 6/0/4 | 0,0 (0/2) | 19 239 | 270 s |
| 1 | 5 | 1,00 | 10/0/0 | 1,0 (2/2) | 21 109 | 206 s |

Entrepôt h10 bruit 5, seed 1 : 0,80 (8/0/2), premier point bruit de cet
environnement. Lecture : le dépôt (état intriqué) score sous l'entrepôt à
horizon égal, la résolution paie cher chaque divergence ; à bruit 5 la variance
inter-runs domine l'effet du bruit (1,00 sur le même seed qui rendait 0,60).
Erreurs observées : tenue d'état du modèle (`wait` face à des `revue` sans
divergence, `merge` d'une PR jamais ouverte) — aucune anomalie du harnais ; le
`wait` dû en divergence a compté correct en réel (§S4.5 confirmé).

**Où reprendre.** U29a4 reste `[~]` : campagne de banc systématique — bruit aux
niveaux de référence (0/5/20/50) et récupération d'état sur les DEUX
environnements, relevés multi-seeds aux horizons 25+ (3 seeds minimum par
point), alimentation du déclencheur U25 avec ces séries.

---

## 2026-09-02 (suite 19) — U29a4 : condition 3 livrée (dérive d'état), premiers relevés de récupération

Session planifiée. Pile montée et seedée (dockerd manuel, CA du proxy dans
`certs/`), reprise désignée par la suite 18 : U29a4, campagne de banc. La
« récupération d'état » du reste-à-livrer n'était ni spécifiée ni implémentée :
spécification écrite et committée d'abord (§S3.8, §S4.7, §S5.5, §S6.2–§S6.4
amendés — commit `0efb5df`), puis code.

**Livré.** Condition 3 sur les deux environnements (`c38d6b6`, `fc21739`) :
générateurs (`derive=True` : une dérive unique, rng séparé `derive-<seed>`,
premier pas ≥ horizon//2 avec candidat, erreur nommée sinon, génération
inchangée octet pour octet à dérive inactive), application réelle par
l'environnement au pas porteur (Entrepôt : article déplacé s'il est réellement
porté ; Dépôt : CI cassée si réellement verte), alerte non structurée sous
`--- ALERTE EXTERNE ---`, événement forcé qui teste la lecture de l'alerte
(`commande` de l'article déplacé ; `ci_verte` périmé où `wait` est dû), mesure
§S5.5 au relevé (`derive_evenement`, `pas_de_recuperation`, `recupere`), CLI
`--derive` avec annonce en fin d'épisode. Contextes de tâche : canal d'alerte
nommé (§S6.2) — générique, aucun contenu d'alerte annoncé. Cassettes E2E du
banc régénérées en conséquence (`81857d5`).

**Prouvé.** 14 unitaires (`test_banc_derive.py`), intégration en rejeu HTTP
deux passes (politique parfaite lisant l'alerte : ombre déplacée, `wait` sur
notification périmée ; récupération 0 au relevé), campagne complète verte
APRÈS régénération des cassettes : lint, ruff format, mypy strict, 624
unitaires, 151 intégration, 6 E2E sur pile fraîche, build.

**Relevés live de récupération** (`--derive --horizon 10 --mode live`, bruit 0,
`state`, gardes actives) — premiers points de la condition 3 :

| env | seed | score | corr/inc/inv | dérive à | récup. (pas) | tokens | durée |
|---|---|---|---|---|---|---|---|
| entrepot | 1 | 1,00 | 10/0/0 | 6 | 0 | 17 814 | 129 s |
| entrepot | 2 | 0,40 | 4/1/5 | 5 | 2 | 22 042 | 189 s |
| entrepot | 3 | 1,00 | 10/0/0 | 5 | 0 | 20 775 | 173 s |
| depot | 1 | 0,80 | 8/1/1 | 6 | 1 | 25 515 | 164 s |
| depot | 2 | 0,70 | 7/1/2 | 5 | 3 | 17 668 | 103 s |
| depot | 3 | 0,80 | 8/0/2 | 5 | 1 | 24 148 | 185 s |

Lecture : les SIX épisodes récupèrent (`recupere` vrai partout, retard 0–3
pas) — le canal d'alerte est intégré par le modèle, et le mode `state` colle au
comportement SKILL.state de la source (récupération immédiate dans 2 cas sur 6,
lag court sinon ; la source table 3/10 donne 0 pas pour SKILL.state, 5–14 pour
les runtimes à historique). Les pertes de score restent la tenue d'état
ordinaire (entrepot seed 2 : 5 invalides étrangères à la dérive), pas la dérive
elle-même. Résolution dépôt 0/jugées sur les trois seeds : à h10, le `ci_verte`
propre de la demande dérivée tombe après l'horizon — cohérent avec la ligne de
base bruit 0 de la suite 18.

**Où reprendre.** U29a4 reste `[~]` : campagne de banc systématique — bruit aux
niveaux de référence (0/5/20/50) et horizons 25+ multi-seeds (3 minimum par
point, §S5.4) sur les deux environnements, dérive aux horizons 25+, alimentation
du déclencheur U25 avec ces séries. La condition 3 est livrée et mesurable :
les prochaines sessions n'ont plus que du relevé à produire sur ce volet.

---

## 2026-09-02 (suite 20) — U29a4 : campagne de banc systématique, séries h25

Session planifiée. Pile montée et seedée (dockerd manuel, CA du proxy dans
`certs/`), `make smoke-live` tout vert, reprise désignée par la suite 19 :
U29a4, campagne de banc — relevés uniquement, la condition 3 étant livrée.
Point tranché (ordre de campagne, motif : chaque série de 3 seeds est
consignable seule, l'ordre maximise la valeur en cas d'interruption) :
1) dépôt h25 bruit 0 — le point 25+ manquant du second environnement ;
2) dérive h25 sur les deux environnements ; 3) bruit 5/20/50 à h25.
Constat d'ouverture : `make smoke-pile` rouge sur `RESET` sans `game_id` —
défaut préexistant DÉJÀ consigné au registre (entrée du 2026-09-01), étranger
au banc (llm-replay vert) ; rien de neuf à consigner, comportement inchangé.

**Relevé live dépôt h25, bruit 0** (`python -m avo banc skillexec --env depot
--seed S --horizon 25 --mode live`, `state`, gardes actives) :

| seed | score | corr/inc/inv | évts | résolution | tokens | durée |
|---|---|---|---|---|---|---|
| 1 | 0,80 | 20/1/4 | 25/25 | 0,0 (0/5) | 61 142 | 424 s |
| 2 | 0,68 | 17/1/7 | 25/25 | 0,0 (0/7) | 55 578 | 329 s |
| 3 | 0,80 | 20/0/5 | 25/25 | 0,0 (0/5) | 58 545 | 422 s |

Moyenne h25 dépôt : **0,76** — au niveau de l'entrepôt h25 bruit 0 (0,88/0,56/
0,64 suite 15 ; 0,84/—/0,44 suite 16), l'état intriqué du dépôt ne dégrade
plus le score à cet horizon. Fait saillant : **résolution 0/17 au cumul** —
aucune demande jugée n'est résolue à h25, alors que h10 en résolvait jusqu'à
1/2. À investiguer AVANT toute correction : part du comportement modèle
(`merge` prématuré, `ci_verte` manquée) vs artefact de mesure ; piste générale,
aucune adaptation au banc.

**Relevé live entrepôt h25, dérive** (`--derive --horizon 25 --mode live`,
bruit 0, `state`, gardes actives) :

| seed | score | corr/inc/inv | dérive à | récup. (pas) | tokens | durée |
|---|---|---|---|---|---|---|
| 1 | 0,52 | 13/5/7 | 12 | 0 | 56 510 | 827 s |
| 2 | 0,32 | 8/6/11 | 12 | 1 | 66 057 | 1 096 s |
| 3 | 0,52 | 13/6/6 | 12 | 0 | 51 990 | 524 s |

Récupération intacte à h25 : les trois épisodes récupèrent en 0–1 pas (comme
h10, 0–3 pas) — le canal d'alerte reste intégré aux horizons longs. Les scores
(0,32–0,52) rejoignent la ligne de base entrepôt h25 SANS dérive (0,44–0,88,
suites 15–16) par le bas : la perte vient de la tenue d'état ordinaire aux
horizons longs (jusqu'à 11 invalides au seed 2), pas de la dérive elle-même.

---

## 2026-09-02 (suite 20, session interactive) — U31 : deux améliorations génériques désignées par la mesure

Demande du responsable : « lis les papiers, inspire-toi de la façon dont Claude
Code fonctionne, rends le harnais globalement meilleur ». Méthode U31 : partir
des mesures de la suite 19, pas d'une idée.

**Mesure de départ** (run `derive-entrepot-h10-s2`, suite 19, score 0,40) : les
5 actions invalides sont TOUTES des erreurs de tenue d'état sur des faits que le
modèle avait lui-même produits (`store` sur une étagère qu'il venait d'occuper,
`ship` depuis la mauvaise étagère). Σ final :
`objets: [{id: article_2, position: null}, …]` — le schéma ARC v1 imposé au banc
n'offre aucun champ où écrire « article_0 sur etagere_1 » ; l'information tombe
dans `description` ou se perd, et le prompt du pas suivant ne la porte plus.
Papier SKILL.state §3.1 : « schemas are authored once per domain » ; exemple
B.3 : `inventory: {shelf_42: null}`. Le noyau contredisait la source.

**Livré 1 — H15.9, schéma de Σ déclaré par le domaine** (`f6a8619` spec,
`7adb063` code). Le noyau possède les GENRES (`position`, `entier_positif`,
`liste_chaines`, `liste_objets`, `dictionnaire`), la validation, ⊕ et la
persistance ; le domaine déclare ses champs (`SchemaEtat`, porté par
`Contexte.schema_etat`, `arc-v1` par défaut sans déclaration). Genre
`dictionnaire` fusionné clé par clé avec retrait sur `null` — l'opérateur du
papier, qui évite au modèle de réémettre l'objet entier (mode d'erreur à 68 %
de la taxonomie §5.7). Protocole engendré depuis le schéma (prompts 1.2), Σ
relu sous son schéma, relevé nommant `schema_etat`. Banc a : `banc-entrepot-v1`
(`inventaire`, `en_attente`), `banc-depot-v1` (`branches`, `prs`). C'est la
répartition de Claude Code : le harnais reste générique, la structure vient de
la tâche (CLAUDE.md, schémas d'outils) — jamais une règle de jeu dans le noyau.
Preuves : 12 unitaires, intégration (Σ du banc sous son schéma), cassettes E2E
régénérées (ARC `state` et banc), lint, mypy, 636 unitaires, 151 intégration,
6 E2E.

**Livré 2 — H15.10, archive des pas** (`cc1d6ac`). En dépouillant le premier
run A/B, constat : 25 appels pour 8 actions, 17 refus de garde (11
« documentaire »), et RIEN dans le workspace ne dit ce que le modèle avait
répondu — le transcript `state` ne porte que les issues d'outils. Le papier
jette Rₜ du PROMPT, pas de l'archive ; Claude Code garde tout. Désormais chaque
appel du mode `state` écrit `state/pas.jsonl` (réponse brute, patch/action ou
erreur, refus de garde), jamais réinjecté. Preuve d'intégration (patch malformé
puis valide : deux lignes, la première avec `erreur`).

**A/B live, sous endpoint DÉGRADÉ** (rafales de HTTP 500, 20–35 s par appel,
campagne h25 de la session planifiée en parallèle sur le même endpoint) — mêmes
points que la suite 19 (`--derive --horizon 10`), schéma du domaine :

| env | seed | suite 19 (arc-v1) | suite 20 (schéma domaine) |
|---|---|---|---|
| entrepot | 1 | 1,00 (10/0/0), récup. 0 | incident HTTP 500 au 2ᵉ tour — sans mesure |
| entrepot | 2 | 0,40 (4/1/5), récup. 2 | incident au 8ᵉ événement : 6/0/2, récup. 0 (partiel, non comparable §S5.3) |
| entrepot | 3 | 1,00 (10/0/0), récup. 0 | en cours à la clôture de cette entrée |
| depot | 1–3 | 0,80 / 0,70 / 0,80 | en file (script `ab_schema.sh`, hors dépôt) |

Lecture prudente : sur le seul point partiellement comparable (seed 2), les
invalides passent de 5 à 2 sur les 8 premiers événements et la récupération de
2 à 0 — Σ final porte bien `inventaire: {etagere_1: article_0, …}`. Mais le run
est incomplet et l'endpoint instable : AUCUNE conclusion de score tant que trois
seeds complets par point n'existent (§S5.4). Observé en revanche, indépendant du
bruit d'endpoint : la garde documentaire refuse 11 fois sur 25 appels (7 sur 17
en suite 19) — le modèle vide ou omet `hypotheses` à répétition. C'est le
premier objet à dépouiller avec `pas.jsonl`, maintenant qu'il existe.

**Points tranchés.** (1) `hypotheses` reste le champ commun obligatoire de tout
schéma : la garde §H16.1 s'y appuie ; issue écartée : la rendre optionnelle,
qui aurait supprimé la garde en mode `state`. (2) Les cassettes ARC `state`
sont régénérées plutôt que de reproduire octet pour octet l'ancien texte :
un seul générateur de protocole, pas deux parcours. (3) Le schéma se déclare
par domaine, jamais par épisode — écrit en §H15.9.

**Où reprendre.** U31, dans l'ordre : (a) relever l'A/B complet sous le schéma
du domaine (h10 dérive seeds 1–3 × 2 env, puis h25 bruit 0 entrepot seeds 1–3
contre les séries des suites 14–16) quand l'endpoint est stable ; (b) dépouiller
`state/pas.jsonl` des runs sous H15.10 pour établir POURQUOI la garde
documentaire refuse si souvent, et livrer la correction générique désignée ;
(c) piste ouverte, non désignée par une mesure encore : garde d'ancrage —
refuser sans consommer d'événement une action dont un argument n'a jamais
figuré dans une observation ni dans Σ (l'analogue de « Read avant Edit »),
à ne coder que si `pas.jsonl` montre des identifiants inventés.

---

## 2026-09-02 (suite 21, session planifiée) — U31 : dépouillement de `pas.jsonl`, révision H16.1 (pas blanc atomique, `hypotheses` non vidable)

**Relevé (a) interrompu — endpoint instable.** Série A/B h10 dérive lancée
(`s20-derive-{entrepot,depot}-h10-s{1,2,3}`, live, `state`, gardes, schéma du
domaine). Deux rafales de HTTP 500 en dix minutes — mesuré à la sonde : le pont
rend « the edge function timed out », sa limite de 40 s avant premiers en-têtes,
alors que l'origine répond (modèle chargé, `/api/version` 200 en 0,5 s). La
rafale de 02:38–02:44 (≈ 6 min) excède la couverture de l'échelle de relances
H4.5 (attentes 1+4+16+45+102 s ≈ 6 min appels compris) : s1 meurt à 2/10
événements (relevé partiel `arret: incident`, non comparable §S5.3), s2 en 500
dès son premier appel. Point tranché : série arrêtée, la condition « endpoint
stable » (suite 20) n'est pas remplie ; le relevé se refera sous le code corrigé
— l'A/B pur H15.9 (suite 19 contre suite 20 à code constant) reste sans mesure
complète et le restera, les prochaines lignes de base étant celles du code
suite 21. Défaut de plomberie consigné au registre : l'échelle de relances est
plus courte que la rafale mesurée.

**Dépouillement (b) — `pas.jsonl` du run s1 (10 pas archivés avant l'incident,
4 refus documentaires, score 0, 0/2 correctes).** La cause est double et NE
tient pas au « mauvais vouloir » du modèle :

1. **Le patch acquis sous action retenue fait mentir Σ.** t1 : le modèle répond
   patch (`inventaire.etagere_0=article_0`, `en_attente=[]` — l'effet ATTENDU de
   son action, exactement comme l'exemple B.3 du papier) + `store`. La garde
   documentaire retient `store` (hypotheses vide, cas d'ouverture voulu), mais le
   patch est acquis (H16.1 d'avant cette session). Σ affirme un rangement jamais
   joué : t2 en déduit la livraison redondante (`wait` indu, 0), t3 déplace un
   article jamais rangé (invalide), t4 doit tout réviser.
2. **Le modèle vide `hypotheses` en révisant.** t4 : révision après l'erreur,
   patch `hypotheses: []` (nettoyage des hypothèses caduques) → garde réarmée,
   refus t4 et t5. Même mécanisme que les 11 refus/25 appels de la suite 20.

**Décision (H16.1 révisé sur place, spec committée avant le code).**
(1) Refus de garde = pas blanc atomique : le patch du pas refusé est annulé avec
l'action, Σ et workspace reviennent à l'état d'avant le pas — patch et action
forment un pas dans la source ; rien n'est perdu, le pas suivant re-dérive tout
du même (Σ, O). (2) Un patch qui vide `hypotheses` non vide (liste vide ou
`null`) est un `EtatInvalide` de §H15.4 (retry immédiat, gratuit) ; le protocole
engendré énonce la règle. Issues écartées : ne corriger que le prompt (la
structure doit imposer, H16.0) ; annuler aussi le patch des actions invalides
(l'événement y est consommé et le patch peut porter une vraie correction —
hors mesure, comportement H15.8 inchangé).
