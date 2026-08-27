"""Point d'entrée en ligne de commande du harnais AVO.

@spec docs/BACKLOG.md U3 — Squelette Python et outillage
@spec docs/SPEC_HARNAIS.md §H2.2 (``cli.py`` : point d'entrée ``python -m avo``),
      §H2.3 (contrat des commandes)
@spec docs/MASTER_PLAN.md §5 (produit CLI : la vérification utilisateur passe par ces commandes)

Les sous-commandes du contrat sont déclarées ici dès maintenant afin que
``python -m avo --help`` dise la vérité sur ce que le produit fera, mais celles
dont l'unité n'est pas livrée refusent explicitement de s'exécuter en nommant
l'unité attendue, plutôt que d'échouer obscurément ou de simuler un succès
(CLAUDE.md §18).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from avo import __version__

#: Sous-commandes prévues par le contrat, et unité de backlog qui les livre.
#: Une entrée disparaît de cette table le jour où son unité la livre réellement.
_A_VENIR: dict[str, tuple[str, str]] = {
    "run-arc": ("U23", "campagne d'évaluation ARC-AGI-3 (docs/SPEC_ARCAGI3.md §A7)"),
    "resume": ("U8", "reprise d'un run existant (docs/SPEC_HARNAIS.md §H13.2)"),
}


class PasEncoreLivre(RuntimeError):
    """Sous-commande déclarée par le contrat mais non encore implémentée."""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="avo",
        description="Harnais d'agent AVO — implémentation open source.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
        help="affiche la version du harnais et quitte",
    )
    sub = parser.add_subparsers(dest="commande")
    for nom, (unite, objet) in _A_VENIR.items():
        sub.add_parser(nom, help=f"[{unite}] {objet}", add_help=False)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Exécute la CLI. Renvoie le code de sortie du processus."""
    parser = _build_parser()
    args, _inconnus = parser.parse_known_args(argv)

    if args.commande is None:
        parser.print_help()
        return 0

    if args.commande in _A_VENIR:
        unite, objet = _A_VENIR[args.commande]
        print(
            f"avo: la commande « {args.commande} » n'est pas encore livrée.\n"
            f"     Elle est spécifiée et attribuée à l'unité {unite} du backlog : {objet}.\n"
            f"     Voir docs/BACKLOG.md et docs/MASTER_PLAN.md.",
            file=sys.stderr,
        )
        return 2

    parser.error(f"commande inconnue : {args.commande}")
    return 2  # pragma: no cover — argparse.error quitte le processus


if __name__ == "__main__":  # pragma: no cover — couvert par tests/unit/test_cli.py
    raise SystemExit(main())
