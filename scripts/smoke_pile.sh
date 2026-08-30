#!/bin/sh
# Fumée de la pile de services : le rejeu répond-il par le port composé ?
#
# @verifies docs/BACKLOG.md U5 — Pile compose des services
# @verifies docs/SPEC_HARNAIS.md §H2.4 (healthcheck, ports), §H4.7 (rejeu fidèle)
#
# Exécuté sur l'HÔTE (il pilote docker compose) par « make smoke-pile ».
# N'entre pas dans « make check », qui tourne en conteneur et sans Docker.
set -eu

PORT="${AVO_PORT_LLM_REPLAY:-11435}"
BASE="http://127.0.0.1:${PORT}"
echec=0

verifier() { # $1=libellé  $2=attendu  $3=obtenu
  if [ "$2" = "$3" ]; then
    printf '  OK   %-46s %s\n' "$1" "$3"
  else
    printf '  ECHEC %-45s attendu %s, obtenu %s\n' "$1" "$2" "$3"
    echec=1
  fi
}

printf 'attente du healthcheck du service llm-replay...\n'
i=0
while [ "$i" -lt 30 ]; do
  etat="$(docker compose ps --format '{{.Health}}' llm-replay 2>/dev/null || true)"
  [ "$etat" = "healthy" ] && break
  i=$((i + 1))
  sleep 1
done
verifier "healthcheck du service" "healthy" "${etat:-<aucun>}"

code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

verifier "GET /_health"                       "200" "$(code "$BASE/_health")"
verifier "GET /api/version SANS clé"          "401" "$(code "$BASE/api/version")"
verifier "GET /api/version AVEC clé"          "200" "$(code -H 'Authorization: Bearer peu-importe' "$BASE/api/version")"
verifier "GET /api/tags AVEC clé"             "200" "$(code -H 'Authorization: Bearer peu-importe' "$BASE/api/tags")"

version="$(curl -s -H 'Authorization: Bearer peu-importe' "$BASE/api/version")"
# Le rejoueur re-sérialise le corps de façon canonique (séparateurs compacts) :
# c'est la même donnée que celle enregistrée, écrite sans espace superflu.
verifier "corps rejoué du vrai serveur"       '{"version":"0.32.14"}' "$version"

# --- arc-replay (U16) ---------------------------------------------------------
PORT_ARC="${AVO_PORT_ARC_REPLAY:-8765}"
BASE_ARC="http://127.0.0.1:${PORT_ARC}"

printf 'attente du healthcheck du service arc-replay...\n'
i=0
while [ "$i" -lt 30 ]; do
  etat_arc="$(docker compose ps --format '{{.Health}}' arc-replay 2>/dev/null || true)"
  [ "$etat_arc" = "healthy" ] && break
  i=$((i + 1))
  sleep 1
done
verifier "healthcheck du service arc-replay" "healthy" "${etat_arc:-<aucun>}"
verifier "GET /_health (arc)"                "200" "$(code "$BASE_ARC/_health")"
verifier "GET /api/games (arc)"              "200" "$(code "$BASE_ARC/api/games")"

# Une vraie partie commence : RESET crée la partie et rend une grille jouable.
etat_jeu="$(curl -s -X POST -H 'Content-Type: application/json' -d '{}' \
  "$BASE_ARC/api/cmd/RESET" | sed -n 's/.*"state": *"\([A-Z_]*\)".*/\1/p')"
verifier "POST /api/cmd/RESET rend une partie" "NOT_FINISHED" "${etat_jeu:-<vide>}"

if [ "$echec" -eq 0 ]; then
  printf 'fumée de la pile : TOUT VERT\n'
else
  printf 'fumée de la pile : ECHEC\n' >&2
fi
exit "$echec"
