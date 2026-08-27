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
- *Réserve* : le scorecard **officiel** ARC-AGI-3 suppose un accès à l'API ARC Prize, qui relève du cas 4 de la « Demande d'arbitrage » (autorité ou accès externes indispensables). À défaut de cet accès, l'évaluation se fera en RHAE calculé localement selon la définition de l'export Tycho, et le rapport dira explicitement laquelle des deux voies a servi.

**Où reprendre.** Unité U2 : rédiger et committer la spécification du harnais, en y intégrant comme contraintes de conception les trois points mesurés ci-dessus (historique append-only pour le cache de préfixe, budget de ~199 k tokens avec gestion du `413`, politique de raisonnement) ainsi que le périmètre arrêté. Plus aucun point n'est en attente du responsable.
