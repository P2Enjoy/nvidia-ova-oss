# infra/llm-proxy — pont HTTPS 443 vers l'endpoint d'inférence

Fonction edge Netlify qui relaie `/api/*` et `/v1/*` vers l'endpoint d'inférence,
pour le rendre joignable depuis les environnements dont la sortie réseau est
limitée au port 443 (mesure et motif : `docs/JOURNAL.md`, entrées du 2026-08-27
et du 2026-08-30).

Propriétés de sécurité, voulues par le responsable :

- **aucun secret ni adresse en dur** : l'URL d'origine vit dans la variable
  d'environnement Netlify `LLM_ORIGIN_URL` (configurée sur le site, hors dépôt) ;
- **authentification en passthrough** : l'en-tête `Authorization` du client est
  transmis tel quel à l'origine, qui reste seule à exiger et vérifier la clé
  (`401` sans elle) — le proxy n'élargit donc pas la surface d'accès ;
- tout chemin hors `/api/*` et `/v1/*` répond `404` sans atteindre l'origine.

Limites de la plate-forme (documentées par Netlify) : 40 s maximum avant les
premiers en-têtes de réponse de l'origine — le cache de préfixe du serveur rend
ce délai rarement atteint ; corps de requête mis en mémoire.

Usage côté harnais : faire pointer `OLLAMA_HOST` sur l'URL du site Netlify
(fournie hors dépôt), le reste de la configuration est inchangé.

Déploiement : site Netlify du responsable, variable `LLM_ORIGIN_URL` posée sur
le site (hors dépôt), fonctions edge servies depuis `netlify/edge-functions/`
via le `netlify.toml` racine. La fonction interceptant tous les chemins,
`public/` n'est qu'un dossier de publication requis, jamais servi en pratique.

**Déployé et recetté le 2026-08-30** depuis un environnement limité au port
443 : `404` hors `/api`/`/v1`, `401` de l'origine sans clé, `200` avec
(version, tags), complétion réelle `/api/chat` en 15,5 s à froid (dont 14,6 s
de chargement du modèle ; préremplissage 0,23 s), streaming NDJSON transmis
fragment par fragment. Mesures : `docs/JOURNAL.md`, entrée du 2026-08-30.
