"""Point d'entrée en ligne de commande du harnais AVO.

@spec docs/BACKLOG.md U3 — Squelette Python et outillage, U23 — Runner de campagne,
      U29a2 — sous-commande `banc` (générique : le dispatch vit sous `avo.bancs`)
@spec docs/SPEC_HARNAIS.md §H2.2 (``cli.py`` : point d'entrée ``python -m avo``),
      §H2.3 (contrat des commandes), §H13.2 (reprise de run)
@spec docs/SPEC_ARCAGI3.md §A7.1 (surface du runner et plafonds), §A7.2 (garde
      d'accord de publication), §A7.4 (contrat d'implémentation de la CLI)
@spec docs/SPEC_BANCS.md §S6.3 (CLI `banc` : boucle complète, relevé §S5.3)
@spec docs/MASTER_PLAN.md §5 (produit CLI : la vérification utilisateur passe par ces commandes)

Les sous-commandes du contrat sont déclarées ici dès maintenant afin que
``python -m avo --help`` dise la vérité sur ce que le produit fait, et celles dont
l'unité n'est pas livrée refusent explicitement de s'exécuter en nommant l'unité
attendue, plutôt que d'échouer obscurément ou de simuler un succès (CLAUDE.md §18).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from avo import __version__

if TYPE_CHECKING:  # pragma: no cover — import de typage seul, la CLI reste légère
    from avo.arc.campagne import ResultatCampagne

#: Sous-commandes prévues par le contrat, et unité de backlog qui les livre.
#: Une entrée disparaît de cette table le jour où son unité la livre réellement.
_A_VENIR: dict[str, tuple[str, str]] = {}


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
    sub.add_parser(
        "smoke-live",
        help="fumée contre le VRAI endpoint : version, modèles, complétion, appel d'outil",
        add_help=False,
    )

    campagne = sub.add_parser(
        "run-arc", help="campagne d'évaluation ARC-AGI-3 (docs/SPEC_ARCAGI3.md §A7)"
    )
    campagne.add_argument(
        "--mode",
        choices=("replay", "live"),
        default="replay",
        help="replay : pile locale, rien n'est publié. live : API officielle (défaut : replay)",
    )
    campagne.add_argument(
        "--games",
        default=None,
        help="identifiants séparés par des virgules (défaut : tous ceux que le serveur déclare)",
    )
    campagne.add_argument("--actions-max-niveau", type=int, default=None)
    campagne.add_argument("--actions-max-jeu", type=int, default=None)
    campagne.add_argument("--tours-max", type=int, default=None)
    campagne.add_argument(
        "--budget-secondes-jeu",
        type=float,
        default=None,
        help="arrêt propre du jeu au-delà de cette durée, évalué entre deux tours",
    )
    campagne.add_argument("--budget-tokens-jeu", type=int, default=None)
    campagne.add_argument("--run-id", default=None, help="identifiant du run (défaut : horodaté)")
    campagne.add_argument(
        "--j-autorise-la-publication",
        action="store_true",
        help="OBLIGATOIRE en mode live : jouer enregistre un scorecard sur votre compte",
    )

    reprise = sub.add_parser("resume", help="reprend un run existant (docs/SPEC_HARNAIS.md §H13.2)")
    reprise.add_argument("run_id", help="identifiant du run à reprendre")
    reprise.add_argument("--mode", choices=("replay", "live"), default="replay")

    # La CLI du noyau reste générique : aucun nom de banc ni d'environnement ici —
    # le dispatch et ses mots vivent sous `src/avo/bancs/` (docs/SPEC_BANCS.md §S6.3).
    banc = sub.add_parser(
        "banc", help="joue un épisode de banc d'affinage (docs/SPEC_BANCS.md §S6)"
    )
    banc.add_argument("nom", help="nom du banc (voir docs/SPEC_BANCS.md)")
    banc.add_argument("--env", required=True, help="environnement du banc")
    banc.add_argument("--seed", type=int, required=True, help="seed de l'épisode (§S2.2)")
    banc.add_argument("--horizon", type=int, required=True, help="événements actionnables (§S2.2)")
    banc.add_argument("--bruit", type=int, default=0, help="lignes de télémétrie par observation")
    banc.add_argument(
        "--derive",
        action="store_true",
        help="active la dérive d'état de la condition 3 (docs/SPEC_BANCS.md §S3.8, §S4.7)",
    )
    banc.add_argument("--mode", choices=("replay", "live"), default="replay")
    banc.add_argument("--run-id", default=None, help="identifiant du run (défaut : horodaté)")
    banc.add_argument(
        "--tours-max",
        type=int,
        default=None,
        help="tours de boucle au plus (défaut : 4 × horizon)",
    )
    return parser


def _executer_campagne(args: argparse.Namespace) -> int:
    """Monte la campagne depuis les arguments et écrit son rapport (§A7.1, §A7.3)."""
    from avo.arc.campagne import CampagneInvalide, Plafonds, executer_campagne
    from avo.config import charger
    from avo.memory.workspace import Workspace
    from avo.runlog import configurer_journalisation, nouveau_run_id

    config = charger(args.mode)
    run_id = args.run_id or nouveau_run_id()
    configurer_journalisation(run_id)
    plafonds = Plafonds(
        actions_niveau=args.actions_max_niveau or config.actions_max_niveau,
        actions_jeu=args.actions_max_jeu or config.actions_max_jeu,
        tours_max=args.tours_max or (args.actions_max_jeu or config.actions_max_jeu),
        secondes_jeu=args.budget_secondes_jeu,
        tokens_jeu=args.budget_tokens_jeu,
    )
    jeux = [nom.strip() for nom in args.games.split(",") if nom.strip()] if args.games else None
    espace = Workspace.ouvrir(config, run_id)
    try:
        resultat = executer_campagne(
            config,
            espace,
            plafonds,
            jeux=jeux,
            autorise_publication=args.j_autorise_la_publication,
        )
    except CampagneInvalide as erreur:
        print(f"avo: campagne refusée — {erreur}", file=sys.stderr)
        return 2
    return _annoncer(resultat, espace.rapport)


def _reprendre(args: argparse.Namespace) -> int:
    """Reprend un run : les jeux terminés ne sont pas rejoués (§H13.2, §A7.4)."""
    from avo.arc.campagne import CampagneInvalide, reprendre_campagne
    from avo.config import charger
    from avo.memory.workspace import Workspace
    from avo.runlog import configurer_journalisation

    config = charger(args.mode)
    configurer_journalisation(args.run_id)
    try:
        resultat = reprendre_campagne(config, config.runs_dir, args.run_id)
    except CampagneInvalide as erreur:
        print(f"avo: reprise impossible — {erreur}", file=sys.stderr)
        return 2
    espace = Workspace(config.runs_dir, args.run_id)
    return _annoncer(resultat, espace.rapport)


def _executer_banc(args: argparse.Namespace) -> int:
    """Joue un épisode de banc et annonce le relevé (docs/SPEC_BANCS.md §S6.3)."""
    from avo.bancs import BancInconnu, executer_banc

    try:
        sortie = executer_banc(
            nom=args.nom,
            environnement=args.env,
            seed=args.seed,
            horizon=args.horizon,
            bruit=args.bruit,
            mode=args.mode,
            run_id=args.run_id,
            tours_max=args.tours_max,
            derive=args.derive,
        )
    except BancInconnu as erreur:
        print(f"avo: banc refusé — {erreur}", file=sys.stderr)
        return 2
    releve = sortie.releve
    print(
        f"épisode terminé : seed {releve.seed}, horizon {releve.horizon}, "
        f"bruit {releve.bruit} — score {releve.score:.2f} "
        f"({releve.correctes} correctes, {releve.incorrectes} incorrectes, "
        f"{releve.invalides} invalides)"
    )
    if "derive_evenement" in releve.champs_libres:
        # Mesure de récupération de la condition 3 (docs/SPEC_BANCS.md §S5.5).
        pas = releve.champs_libres["pas_de_recuperation"]
        etat = f"récupération en {pas} pas" if pas is not None else "non récupérée"
        print(f"dérive à l'événement {releve.champs_libres['derive_evenement']} — {etat}")
    print(f"relevé : {sortie.chemin_releve}")
    return 0


def _annoncer(resultat: ResultatCampagne, chemin_rapport: Path) -> int:
    """Ce que l'opérateur lit dans son terminal (MASTER_PLAN §5)."""
    from avo.arc.rapport import formater

    print(f"campagne terminée : {len(resultat.jeux)} jeu(x)")
    for jeu in resultat.jeux:
        print(
            f"  {jeu.game_id} : {jeu.niveaux_completes}/{len(jeu.niveaux)} niveaux, "
            f"{jeu.actions} actions, RHAE {formater(jeu.rhae.valeur)} ({jeu.arret})"
        )
    print(f"score global : {formater(resultat.score_global)}")
    print(f"rapport : {chemin_rapport}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Exécute la CLI. Renvoie le code de sortie du processus."""
    parser = _build_parser()
    args, _inconnus = parser.parse_known_args(argv)

    if args.commande is None:
        parser.print_help()
        return 0

    if args.commande == "smoke-live":
        from avo.smoke import executer

        return executer()

    if args.commande == "run-arc":
        return _executer_campagne(args)

    if args.commande == "resume":
        return _reprendre(args)

    if args.commande == "banc":
        return _executer_banc(args)

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
