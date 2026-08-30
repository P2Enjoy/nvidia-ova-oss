// @spec Pont HTTPS 443 vers l'endpoint d'inférence — décision du responsable du
// 2026-08-30 (docs/JOURNAL.md, entrée du jour ; CLAUDE_PROJECT.md, « Configuration
// de l'endpoint d'inférence »). Aucun secret ni adresse en dur : l'URL d'origine
// vient de la variable d'environnement Netlify LLM_ORIGIN_URL, et l'en-tête
// Authorization du client est transmis tel quel à l'origine (passthrough) — le
// proxy n'authentifie rien lui-même et n'élargit pas la surface d'accès :
// l'origine continue d'exiger sa clé (401 sans elle).
//
// Limites de la plate-forme à connaître (contexte officiel Netlify) : 40 s
// maximum avant les premiers en-têtes de réponse de l'origine ; corps de
// requête mis en mémoire (les requêtes du harnais restent de l'ordre du Mo).

declare const Netlify: { env: { get(name: string): string | undefined } };

export default async (req: Request, _context: unknown) => {
  const origine = Netlify.env.get("LLM_ORIGIN_URL");
  if (!origine) {
    return new Response(
      JSON.stringify({ error: "LLM_ORIGIN_URL non configurée sur le site" }),
      { status: 503, headers: { "content-type": "application/json" } },
    );
  }

  const url = new URL(req.url);
  // Seules les surfaces de l'API d'inférence sont relayées.
  if (!url.pathname.startsWith("/api/") && !url.pathname.startsWith("/v1/")) {
    return new Response("Not Found", { status: 404 });
  }

  const cible = origine.replace(/\/+$/, "") + url.pathname + url.search;

  // En-têtes transmis tels quels (Authorization comprise) ; seuls les en-têtes
  // de connexion (hop-by-hop) et Host sont retirés.
  const interdits = new Set([
    "host",
    "connection",
    "keep-alive",
    "transfer-encoding",
    "upgrade",
    "te",
    "trailer",
    "expect",
    "proxy-authorization",
    "proxy-connection",
  ]);
  const entetes = new Headers();
  for (const [nom, valeur] of req.headers) {
    if (!interdits.has(nom.toLowerCase())) entetes.set(nom, valeur);
  }

  const corps =
    req.method === "GET" || req.method === "HEAD"
      ? undefined
      : await req.arrayBuffer();

  let reponse: Response;
  try {
    reponse = await fetch(cible, {
      method: req.method,
      headers: entetes,
      body: corps,
      redirect: "manual",
    });
  } catch (erreur) {
    return new Response(
      JSON.stringify({ error: "origine injoignable", detail: String(erreur) }),
      { status: 502, headers: { "content-type": "application/json" } },
    );
  }

  // Réponse renvoyée en flux (le streaming NDJSON d'Ollama passe tel quel) ;
  // les en-têtes de codage/longueur sont retirés, fetch ayant déjà décodé.
  const sortie = new Headers(reponse.headers);
  for (const nom of ["content-encoding", "content-length", "transfer-encoding", "connection"]) {
    sortie.delete(nom);
  }
  return new Response(reponse.body, {
    status: reponse.status,
    statusText: reponse.statusText,
    headers: sortie,
  });
};

export const config = { path: "/*" };
