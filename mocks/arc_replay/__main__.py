"""Entrée en ligne de commande d'`arc-replay`.

@spec docs/BACKLOG.md U16 · docs/SPEC_ARCAGI3.md §A3.1

    python -m arc_replay serve [--port N] [--hote ADRESSE] [--niveaux N] [--episode F]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from arc_replay.serveur import creer_serveur


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(prog="arc_replay", description="Contrat ARC-AGI-3 local.")
    sous = parseur.add_subparsers(dest="commande", required=True)
    servir = sous.add_parser("serve", help="sert le jeu synthétique ou un épisode enregistré")
    servir.add_argument("--port", type=int, default=8765)
    servir.add_argument("--hote", default="127.0.0.1")
    servir.add_argument("--niveaux", type=int, default=3)
    servir.add_argument("--episode", type=Path, default=None)

    args = parseur.parse_args(argv)
    serveur = creer_serveur(args.port, args.niveaux, args.hote, args.episode)
    hote, port = serveur.server_address[0], serveur.server_address[1]
    source = f"épisode {args.episode}" if args.episode else f"jeu cible, {args.niveaux} niveaux"
    print(f"arc-replay écoute sur http://{hote!s}:{port} ({source})", flush=True)
    serveur.serve_forever()
    return 0


if __name__ == "__main__":  # pragma: no cover — couvert par les tests d'intégration
    raise SystemExit(main())
