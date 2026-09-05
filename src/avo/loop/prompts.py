"""Prompts de la boucle agent, versionnés.

@spec docs/BACKLOG.md U13 — Boucle agent P→I→E→B
@spec docs/SPEC_HARNAIS.md §H8.1 (contenu des phases), §H12 (raisonnement en clair)
@spec docs/SPEC_ARCAGI3.md §A5.1 (contrainte direct-interaction : aucune règle de jeu)
@spec docs/BACKLOG.md U27 — `PROTOCOLE_ETAT` (§H15.1, §H15.8)
@spec docs/BACKLOG.md U30 — invites des gardes de méthode (§H16.1–§H16.4)
@spec docs/BACKLOG.md U31 — `protocole_etat` engendré depuis le schéma de Σ (§H15.9)

**Contrainte fondatrice, vérifiée par test** : aucun de ces textes ne décrit les
règles, les objets ni le but d'un jeu. L'agent reçoit les actions disponibles et rien
d'autre ; il doit inférer leurs effets en interagissant. Un indice glissé ici
invaliderait toute l'évaluation, sans que rien ne le signale dans les scores.

Les prompts sont courts à dessein : ils sont réémis à chaque tour et le
préremplissage domine le coût (§H1.3.1).
"""

from __future__ import annotations

from typing import Final

from avo.context.etat import ARC_V1, CHAMP_HYPOTHESES, DICTIONNAIRE, FORMES, SchemaEtat

#: Version des prompts. Change dès qu'un texte change : le rapport d'une campagne
#: doit pouvoir dire sous quelle formulation ses résultats ont été obtenus.
VERSION: Final = "1.10"

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

#: Tête de l'invite de protocole du mode `state` (§H15.1, §H15.8) : le format de
#: réponse, identique pour tout schéma. Réémise à chaque tour : le mode `state` ne
#: conserve aucun historique.
PROTOCOLE_ETAT_FORMAT: Final = """Réponds en terminant TOUJOURS par un unique bloc ```json
contenant exactement deux clés : « state_patch » (objet, peut être vide {}) et
« action » (chaîne, le nom de l'action à jouer, éventuellement suivi d'un espace
et des valeurs requises séparées par des virgules pour une action qui en exige)."""


def protocole_etat(schema: SchemaEtat = ARC_V1) -> str:
    """Invite de protocole du mode `state`, ENGENDRÉE depuis le schéma de Σ (§H15.9).

    Le noyau ne connaît que les genres (§H15.9) ; les champs, leur ordre et leur
    rôle viennent du schéma déclaré par le domaine. Aucune règle de tâche ici : le
    texte cite des contenants, jamais des contenus (§A5.1). Le protocole énonce
    aussi l'annulation du patch sous action refusée (§H15.8).
    """
    champs = ", ".join(
        f"« {champ.nom} » ({FORMES[champ.genre]}{' : ' + champ.role if champ.role else ''})"
        for champ in schema.champs
    )
    texte = (
        f"{PROTOCOLE_ETAT_FORMAT}\n\n« state_patch » modifie Σ, ton état d'exécution "
        f"structuré à {len(schema.champs)} champs toujours présents : {champs}. Une clé "
        "absente du patch laisse le champ inchangé ; une clé présente à null réinitialise "
        "le champ à son défaut."
    )
    if any(champ.genre == DICTIONNAIRE for champ in schema.champs):
        texte += (
            " Pour un champ « objet clé → valeur », le patch fusionne clé par clé : une "
            "entrée présente est remplacée, une entrée à null est retirée, une entrée "
            "absente est laissée — ne réémets jamais l'objet entier."
        )
    texte += (
        f" Le champ « {CHAMP_HYPOTHESES} » ne se vide jamais : remplace une hypothèse "
        "périmée par sa révision."
    )
    texte += (
        " Si l'environnement refuse ton action, le patch du même pas est annulé "
        "avec elle : Σ n'enregistre que ce qui a réellement eu lieu."
    )
    texte += (
        " Un refus te renseigne : il nomme le point sur lequel Σ est faux — le "
        "patch de ton pas suivant corrige Σ d'après ce message avant de rejouer."
    )
    # §H16.0.7 : les exigences que la structure impose s'annoncent d'emblée, et
    # l'exigence documentaire CLÔT le protocole en exception nommée à la
    # parcimonie — annoncée avant elle, elle perdait chaque fois que la première
    # observation ne laissait aucune incertitude réelle (mesuré : 2/2 premiers
    # pas refusés, patchs t01 réduits aux champs que l'événement change).
    texte += " N'inclus dans le patch que ce qui change réellement,"
    return texte + (
        f" à une exception près : tant que « {CHAMP_HYPOTHESES} » est vide, "
        "aucune action n'est jouée — ta première réponse écrit au moins une "
        "hypothèse dans son patch."
    )


#: Invite de protocole du schéma ARC v1 (§H15.6) — constante pour le balayage
#: « zéro indice » (§A5.1), qui lit les constantes de ce module.
PROTOCOLE_ETAT: Final = protocole_etat(ARC_V1)


#: Amorce documentaire du mode `state` (§H16.0.7) : tant que le champ de
#: connaissances est vide — la condition exacte de la garde §H16.1 —, le message
#: du pas s'ouvre sur ce rappel d'une ligne ; la phrase finale du protocole,
#: éloignée dans le message système, perd contre une observation volumineuse.
AMORCE_DOCUMENTAIRE: Final = (
    f"[GARDE] Le champ « {CHAMP_HYPOTHESES} » de Σ est encore vide : aucune action "
    "n'est jouée tant qu'il l'est. Ta réponse à CE pas écrit au moins une hypothèse "
    "dans son state_patch, en plus de ce qui change."
)

#: Garde documentaire (§H16.1) : l'artefact exigé avant de déverrouiller l'action.
GARDE_DOCUMENTAIRE: Final = """[GARDE] Avant toute action, écris dans WORKING.md
(outil note_write) : ce que tu sais déjà, ce que tu ignores encore, et comment tu
comptes le découvrir. Les outils d'action restent verrouillés tant que WORKING.md
est vide."""

#: Garde de persistance (§H16.4) : la connaissance s'écrit avant de poursuivre.
GARDE_PERSISTANCE: Final = """[GARDE] Ce qui vient de se passer mérite d'être
retenu : mets à jour GUIDE.md (outil note_write) avec ce que tu en retiens de
durable. Les outils d'action restent verrouillés tant que GUIDE.md n'a pas été
mis à jour."""

#: Garde d'évaluation (§H16.3) : la qualification exigée, en clair.
GARDE_VERDICT: Final = """Termine par une ligne « VERDICT: confirmee »,
« VERDICT: contredite » ou « VERDICT: caduque » — confirmee si l'observation
confirme ta prédiction, contredite si elle la contredit, caduque si un
événement postérieur l'a rendue sans objet."""

#: Redemande de verdict, quand la réponse d'évaluation n'en portait pas (§H16.3).
GARDE_VERDICT_REDEMANDE: Final = """[GARDE] Ta réponse ne qualifie pas ta
prédiction. Réponds par une seule ligne : « VERDICT: confirmee »,
« VERDICT: contredite » ou « VERDICT: caduque »."""

#: Complément de protocole du mode `state` quand les gardes sont actives (§H16.2,
#: §H16.3) : la prédiction et le verdict voyagent en lignes de texte, le bloc JSON
#: à deux clés de §H15.1 restant inchangé.
PROTOCOLE_ETAT_GARDES: Final = """Fais précéder ton bloc ```json d'une ligne
« PREDICTION: … » énonçant en une phrase l'effet que tu attends de l'action
choisie. Si le message te présente une prédiction antérieure à qualifier, ajoute
aussi une ligne « VERDICT: confirmee », « VERDICT: contredite » ou
« VERDICT: caduque » (caduque : un événement postérieur l'a rendue sans
objet)."""


def rappel_patch_annule(action: str, patch_json: str) -> str:
    """Rappel du pas suivant un refus d'environnement (§H15.8) : le patch annulé, verbatim.

    Le prompt du mode `state` est recomposé à neuf à chaque tour : sans ce rappel,
    ce que le patch annulé portait AU-DELÀ de l'effet de l'action refusée — la
    correction de Σ qu'un refus précédent exigeait — disparaît du contexte de
    travail du modèle avec l'annulation (mesuré : journal 2026-09-02, suite 30,
    cascade de 8 refus sur le même point). C'est le modèle qui décide de ce qui
    survit, jamais le harnais.
    """
    return (
        f"Ton action précédente « {action} » a été refusée par l'environnement : "
        f"le patch du même pas a été annulé, Σ n'en garde rien. Patch annulé : "
        f"{patch_json}. Réinscris dans ton prochain patch ce qui y décrit la "
        "situation indépendamment de l'action refusée ; n'y reprends pas l'effet "
        "de cette action."
    )


def annonce_action(nom: str, requis: list[str] | None) -> str:
    """Annonce d'une action disponible avec ses valeurs requises (§H15.8).

    La forme d'appel s'annonce d'emblée (principe §H16.0.7) : mesuré (journal
    2026-09-05, suite 46, dépouillement des 25 jeux de la campagne U25
    tranche 1), 161 actions invalides sur 646 jouées quand seule la liste des
    NOMS atteint le modèle — 82 appels à outil à coordonnées sans valeur,
    47 valeurs données à un outil qui n'en prend pas. Les paramètres viennent
    du schéma déclaré au registre, jamais d'une liste codée ; un nom sans
    schéma (`requis` à None) reste nu.
    """
    if requis is None:
        return nom
    if not requis:
        return f"{nom} (aucune valeur)"
    return f"{nom} (valeurs requises : {', '.join(requis)})"


def forme_appel_attendue(nom: str, requis: list[str], types: dict[str, str]) -> str:
    """Forme complète attendue d'un appel d'action, pour clore un refus (§H15.8).

    Principe de §H16.0.6 étendu à la résolution d'action : le refus qui ne nomme
    que le compte manquant laisse le modèle deviner la forme. Les types cités
    sont ceux que le schéma déclare ; sans type déclaré, le paramètre est cité
    seul.
    """
    if not requis:
        return f"Forme attendue : « {nom} » seul, sans valeur."
    details = ", ".join(f"{cle} : {types[cle]}" if types.get(cle) else cle for cle in requis)
    return (
        f"Forme attendue : « {nom} {', '.join(requis)} », en remplaçant chaque "
        f"nom par sa valeur ({details})."
    )


def forme_pas_attendue(verdict_attendu: bool) -> str:
    """Forme complète d'un pas du mode `state` sous gardes (§H16.0.6).

    Une redemande l'énonce en ENTIER, jamais la seule pièce manquante : mesuré
    (journal 2026-09-02, suite 24), le modèle qui ne reçoit que la ligne absente
    la produit seule et perd l'autre — quatre redemandes alternées sur un tour.
    """
    verdict = (
        "la ligne « VERDICT: confirmee », « VERDICT: contredite » ou "
        "« VERDICT: caduque » (les trois issues reconnues), puis "
        if verdict_attendu
        else ""
    )
    return (
        "Forme complète attendue de ta réponse, dans cet ordre : "
        f"{verdict}la ligne « PREDICTION: … », puis le bloc ```json "
        "à deux clés « state_patch » et « action »."
    )


def evaluation_gardee(prediction: str) -> str:
    """Invite d'Evaluation sous garde (§H16.3) : prédit-contre-observé, en clair."""
    return f"{EVALUATION}\n\nTu avais prédit : « {prediction} »\n{GARDE_VERDICT}"


def verdict_a_qualifier(prediction: str) -> str:
    """Rappel du mode `state` (§H16.3) : la prédiction du pas précédent à qualifier."""
    return f"Tu avais prédit : « {prediction} ». Qualifie cette prédiction (VERDICT)."


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
