"""`arc-replay` — contrat ARC-AGI-3 local : jeu synthétique et rejeu d'épisodes.

@spec docs/BACKLOG.md U16 — Serveur de rejeu arc-replay et jeu cible
@spec docs/SPEC_ARCAGI3.md §A3

Contrairement à `llm-replay`, ce service **simule** un contrat, et c'est assumé :
chaque partie jouée via l'API officielle publie un scorecard sur le compte du
responsable (`CLAUDE_PROJECT.md`). C'est le cas « dépendance impossible à exécuter
localement » de CLAUDE.md §15. Le contrat reste néanmoins ancré sur du réel : la
sonde U22 enregistrera un épisode authentique qui fera référence (§A3.3), et le jeu
`cible` n'imite aucun jeu officiel — c'est une fixture pour éprouver le harnais.
"""

from arc_replay.jeu_cible import EtatPartie, JeuCible, Resultat

__all__ = ["EtatPartie", "JeuCible", "Resultat"]
