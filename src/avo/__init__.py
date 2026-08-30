"""Harnais d'agent AVO — paquet applicatif.

@spec docs/BACKLOG.md U3 — Squelette Python et outillage
@spec docs/SPEC_HARNAIS.md §H1 (objet), §H2.2 (arborescence)

Le paquet n'a aucune dépendance d'exécution hors bibliothèque standard (§H2.1).
Les sous-paquets sont introduits par leurs unités respectives :
``config`` (U6), ``llm`` (U7), ``context`` (U9-U10), ``memory`` (U11),
``tools`` (U12), ``loop`` (U13), ``lineage`` (U14), ``supervisor`` (U15),
``runlog`` (U8), ``arc`` (U16-U23).
"""

__all__ = ["__version__"]

#: Version du harnais. Source unique ; ``pyproject.toml`` porte la même valeur.
__version__ = "0.1.0"
