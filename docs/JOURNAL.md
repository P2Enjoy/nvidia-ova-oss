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
