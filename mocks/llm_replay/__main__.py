"""Entrée en ligne de commande de `llm-replay`.

@spec docs/BACKLOG.md U4
@spec docs/SPEC_HARNAIS.md §H4.7

    python -m llm_replay serve  [--cassettes DIR] [--port N]
    python -m llm_replay record [--cassettes DIR] [--nom NOM]

`record` exige OLLAMA_HOST et OLLAMA_API_KEY dans l'environnement : le conteneur
les reçoit via `--env-file .env`, de sorte qu'aucun analyseur de `.env` ne soit
nécessaire ici et qu'aucun secret ne transite par un fichier du dépôt.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from llm_replay.record import enregistrer_tout
from llm_replay.server import creer_serveur

CASSETTES_DEFAUT = Path("tests/fixtures/llm/cassettes")


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(
        prog="llm_replay", description="Enregistre et rejoue le vrai endpoint."
    )
    sous = parseur.add_subparsers(dest="commande", required=True)

    servir = sous.add_parser("serve", help="sert les cassettes enregistrées")
    servir.add_argument("--cassettes", type=Path, default=CASSETTES_DEFAUT)
    servir.add_argument("--port", type=int, default=11435)

    capturer = sous.add_parser("record", help="enregistre le contrat sur le VRAI endpoint")
    capturer.add_argument("--cassettes", type=Path, default=CASSETTES_DEFAUT)
    capturer.add_argument("--nom", default="contrat_endpoint")

    args = parseur.parse_args(argv)

    if args.commande == "serve":
        serveur = creer_serveur(args.cassettes, args.port, os.environ.get("OLLAMA_API_KEY"))
        hote, port = serveur.server_address[0], serveur.server_address[1]
        print(
            f"llm-replay écoute sur http://{hote!s}:{port} (cassettes : {args.cassettes})",
            flush=True,
        )
        serveur.serve_forever()
        return 0

    hote = os.environ.get("OLLAMA_HOST", "")
    cle = os.environ.get("OLLAMA_API_KEY", "")
    if not hote or not cle:
        print(
            "llm_replay record : OLLAMA_HOST et OLLAMA_API_KEY sont requis.\n"
            "  Ils ne sont jamais lus depuis le dépôt : passez-les au conteneur\n"
            "  avec « --env-file .env » (cf. cible make record-llm).",
            file=sys.stderr,
        )
        return 2

    destination = args.cassettes / f"{args.nom}.jsonl"
    print(f"enregistrement du contrat sur le VRAI endpoint → {destination}", flush=True)
    cassette = enregistrer_tout(hote, cle, destination)
    print(f"{len(cassette)} échanges enregistrés.", flush=True)
    return 0


if __name__ == "__main__":  # pragma: no cover — couvert par les tests d'intégration
    raise SystemExit(main())
