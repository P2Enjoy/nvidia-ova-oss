"""Prompts de la boucle agent, versionnés.

@spec docs/BACKLOG.md U13 — Boucle agent P→I→E→B
@spec docs/SPEC_HARNAIS.md §H8.1 (contenu des phases), §H12 (raisonnement en clair)
@spec docs/SPEC_ARCAGI3.md §A5.1 (contrainte direct-interaction : aucune règle de jeu)
@spec docs/BACKLOG.md U27 — `PROTOCOLE_ETAT` (§H15.1, §H15.8)

**Contrainte fondatrice, vérifiée par test** : aucun de ces textes ne décrit les
règles, les objets ni le but d'un jeu. L'agent reçoit les actions disponibles et rien
d'autre ; il doit inférer leurs effets en interagissant. Un indice glissé ici
invaliderait toute l'évaluation, sans que rien ne le signale dans les scores.

Les prompts sont courts à dessein : ils sont réémis à chaque tour et le
préremplissage domine le coût (§H1.3.1).
"""

from __future__ import annotations

from typing import Final

#: Version des prompts. Change dès qu'un texte change : le rapport d'une campagne
#: doit pouvoir dire sous quelle formulation ses résultats ont été obtenus.
VERSION: Final = "1.0"

#: Contrat de tâche, posé une fois en tête de segment (§A5.1, calqué sur VISTA).
SYSTEME: Final = """Tu joues à un jeu inconnu, tour par tour, sur une grille de
cellules colorées. Ses objets, ses mécaniques et son but ne te sont pas donnés :
découvre-les en observant et en agissant, comme un scientifique.

Ton objectif : terminer chaque niveau en aussi peu d'actions que possible. Seules
les actions d'environnement comptent ; réfléchir et inspecter sont gratuits.

Entretiens un modèle compact et révisable du jeu dans tes notes. Avant chaque
action, énonce ce que tu attends. Après, énonce tous les changements visibles,
attendus ou non."""

#: Phase Planning (§H8.1) : relire, formuler, choisir, PRÉDIRE.
PLANNING: Final = """[PLANNING] Relis l'évidence et tes notes. Formule ou révise
tes hypothèses, puis choisis la prochaine action. Énonce en une phrase ce que tu
attends d'elle : cette prédiction est ce qui rendra la prochaine observation
informative."""

#: Phase Implementation (§H8.1) : exactement une action d'environnement.
IMPLEMENTATION: Final = """[IMPLEMENTATION] Exécute maintenant exactement UNE action
d'environnement, celle que tu viens d'annoncer. Une seule : chaque action compte au
score."""

#: Phase Evaluation (§H8.1) : confronter, énoncer, mettre à jour.
EVALUATION: Final = """[EVALUATION] Compare l'observation obtenue à ta prédiction.
Énonce tous les changements visibles, y compris ceux que tu n'attendais pas. Si ta
prédiction est contredite, dis-le explicitement. Mets à jour tes notes si ta
compréhension a changé."""

#: Phase Bug-Fixing (§H8.1) : réviser après contradiction ou situation dégradée.
BUG_FIXING: Final = """[BUG-FIXING] Ton hypothèse vient d'être contredite, ou la
situation s'est dégradée. Révise ton modèle du jeu plutôt que de réessayer la même
chose. Si la tentative en cours est condamnée ou plus coûteuse qu'un redémarrage,
recommence-la."""

#: Rappel émis quand une borne d'actions approche (§H8.3).
BORNE_PROCHE: Final = """[BORNE] Le budget d'actions de ce niveau touche à sa fin.
Privilégie l'action la plus décisive dont tu disposes."""

#: Invite de protocole du mode `state` (§H15.1, §H15.8) : format de réponse et
#: schéma de Σ uniquement — générique à toute grille ARC-AGI-3, aucune règle de jeu
#: (§A5.1). Réémise à chaque tour : le mode `state` ne conserve aucun historique.
PROTOCOLE_ETAT: Final = """Réponds en terminant TOUJOURS par un unique bloc ```json
contenant exactement deux clés : « state_patch » (objet, peut être vide {}) et
« action » (chaîne, le nom de l'action à jouer, éventuellement suivi d'un espace
et des valeurs requises séparées par des virgules pour une action qui en exige).

« state_patch » modifie Σ, ton état d'exécution structuré à quatre champs
toujours présents : « position » ({"x": int, "y": int} ou null), « essai »
(entier ≥ 1), « hypotheses » (liste de chaînes), « objets » (liste d'objets avec
au moins « id » et « description »). Une clé absente du patch laisse le champ
inchangé ; une clé présente à null réinitialise le champ à son défaut. N'inclus
dans le patch que ce qui change réellement."""


def prompt_de_phase(phase: str) -> str:
    """Rend le prompt d'une phase. Lève sur une phase inconnue plutôt que de deviner."""
    textes = {
        "planning": PLANNING,
        "implementation": IMPLEMENTATION,
        "evaluation": EVALUATION,
        "bug_fixing": BUG_FIXING,
    }
    try:
        return textes[phase]
    except KeyError as erreur:
        raise KeyError(f"aucun prompt pour la phase « {phase} »") from erreur
