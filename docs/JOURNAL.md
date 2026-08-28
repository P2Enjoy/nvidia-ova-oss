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
