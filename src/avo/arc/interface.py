"""Interface de tâche direct-interaction : ce que l'agent voit et ce qu'il peut faire.

@spec docs/BACKLOG.md U19 — Interface de tâche direct-interaction ; U22 — fil mesuré
@spec docs/SPEC_ARCAGI3.md §A5.1 (contrainte fondatrice : aucune règle de jeu),
      §A5.2 (outils filtrés par la frame, reset toujours offert), §A5.3 (comptage
      local, réconciliation au résumé de scorecard), §A5.4 (état terminal),
      §A1.2 (protocole de score), §A4.1 (rendu), §A4.3 (mémoire de frames)
@spec docs/SPEC_HARNAIS.md §H8.2 (contrat `Environnement` de la boucle),
      §H8.3 (arrêt sur état terminal)
@spec docs/BACKLOG.md U30 — garde de prédiction (§H16.2 : paramètre `prediction`
      des outils d'action, acheminé tronqué vers `reasoning` du fil officiel)

**Contrainte fondatrice** (billet NVIDIA, VISTA) : l'agent reçoit les actions
disponibles *sans* description des règles ni du but. Ce module est le seul endroit où
un indice pourrait se glisser — un nom d'outil parlant, une description qui explique
ce qu'une action « fait ». Les descriptions y sont donc délibérément muettes sur les
effets : elles nomment la commande, rien de plus. Un test le vérifie.

Ce module implémente le contrat `Environnement` de la boucle : c'est lui qui relie le
client ARC, le rendu texte, la mémoire de frames et la machine d'états.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from avo.arc.client import ArcClient, EtatArc, FrameResult, TypeFrame
from avo.arc.memoire import MemoireFrames
from avo.arc.rendu import COTE, rendre_observation
from avo.loop.etats import Evenement
from avo.tools.registre import Outil, RegistreOutils

#: Étiquette portée par les outils qui dépensent une action (§H7.1). C'est elle qui
#: fait qu'ils ne sont offerts qu'à la phase où agir est permis.
ETIQUETTE_ACTION: Final = "action"

#: Troncature de la prédiction transmise au fil (§H16.0.5) : bien sous la limite
#: mesurée de 16 Ko du champ `reasoning` (§A1.4), le préremplissage dominant le coût.
PREDICTION_MAX_CARACTERES: Final = 2000

#: Description du paramètre de prédiction (§H16.2) : générique, aucun effet réel
#: d'aucune commande n'y est décrit (§A5.1).
DESCRIPTION_PREDICTION: Final = "Ce que tu attends de cette action, en une ou deux phrases."

#: Descriptions des commandes. Volontairement **muettes sur les effets** (§A5.1) :
#: dire « déplace vers le haut » donnerait à l'agent ce qu'il doit inférer.
DESCRIPTIONS: Final = {
    "action1": "Joue la commande ACTION1. Coûte une action.",
    "action2": "Joue la commande ACTION2. Coûte une action.",
    "action3": "Joue la commande ACTION3. Coûte une action.",
    "action4": "Joue la commande ACTION4. Coûte une action.",
    "action5": "Joue la commande ACTION5. Coûte une action.",
    "action6": "Joue la commande ACTION6 aux coordonnées (row, col). Coûte une action.",
    "action7": "Joue la commande ACTION7. Coûte une action.",
    "reset": "Joue la commande RESET : relance la tentative en cours. Coûte une action.",
}


class ActionIndisponible(RuntimeError):
    """Commande absente de celles que la frame courante déclare (§A5.2)."""


class CoordonneesInvalides(ValueError):
    """Coordonnées hors grille (§A5.2)."""


@dataclass(frozen=True)
class IssueArc:
    """Ce qu'une action rend à la boucle (§H8.2).

    `refusee` reste faux sur le fil ARC (§H15.8) : toute commande acceptée par
    l'API produit une frame — le fil ne refuse pas d'action, il en rend l'effet.
    """

    observation: str
    evenement: Evenement
    refusee: bool = False


@dataclass
class Comptage:
    """Compteurs locaux (§A5.3 : le fil ne rend aucun compteur par frame).

    `divergences` accueille les écarts constatés à la réconciliation contre le
    résumé de scorecard (fermeture de campagne) — jamais masqués.
    """

    actions_niveau: int = 0
    actions_jeu: int = 0
    divergences: list[dict[str, int]] = field(default_factory=list)

    def resume(self) -> dict[str, Any]:
        return {
            "actions_niveau": self.actions_niveau,
            "actions_jeu": self.actions_jeu,
            "divergences": len(self.divergences),
        }


class InterfaceArc:
    """Relie le client ARC à la boucle agent (§A5, §H8.2)."""

    def __init__(
        self,
        client: ArcClient,
        memoire: MemoireFrames | None = None,
        game_id: str | None = None,
        card_id: str | None = None,
        registre: RegistreOutils | None = None,
        avec_prediction: bool = False,
        prediction_requise: bool = True,
    ) -> None:
        """`registre` : si fourni, son groupe « action » suit la frame courante.

        C'est ce qui rend le filtrage de §A5.2 effectif jusque dans ce que le modèle
        voit : le registre de la boucle est construit une fois, mais les commandes
        déclarées changent à chaque frame. Sans cette synchronisation, l'agent se
        verrait offrir des actions que l'environnement n'offre plus.

        `avec_prediction` (§H16.2) : chaque outil d'action déclare un paramètre
        `prediction`, acheminé tronqué vers le champ `reasoning` du fil officiel.
        `prediction_requise` le rend obligatoire (mode `transcript` : un appel sans
        prédiction est une erreur d'outil, l'action n'est pas jouée) ; en mode
        `state` il reste optionnel, la prédiction voyageant en ligne de texte et
        étant injectée par la boucle (§H16.2, §H15.8).
        """
        self.client = client
        self.memoire = memoire or MemoireFrames()
        self.game_id = game_id
        self.card_id = card_id
        self.registre = registre
        self.avec_prediction = avec_prediction
        self.prediction_requise = prediction_requise
        self.comptage = Comptage()
        self.guid: str | None = None
        self.dernier: FrameResult | None = None
        self._derniere_issue: IssueArc | None = None

    # ------------------------------------------------------------------ départ
    def demarrer(self) -> str:
        """`RESET` initial : crée la partie. Gratuit au score (§A1.2)."""
        resultat = self.client.reset(game_id=self.game_id, card_id=self.card_id)
        self.guid = resultat.guid
        self._absorber(resultat, compte_une_action=False)
        return self.observation()

    # ----------------------------------------------------- contrat Environnement
    def observation(self) -> str:
        """Rendu de la frame de décision courante (§A4.1).

        Les frames transitoires ne sont pas rendues : elles restent consultables par
        `inspect`, ce qui laisse à l'agent le choix de les regarder — et lui épargne
        le coût de préremplissage quand il ne le souhaite pas.
        """
        if self.dernier is None:
            raise RuntimeError("partie non démarrée : appeler demarrer() d'abord")
        frame = self.dernier.frame_de_decision or self.dernier.frames[-1]
        rendu = rendre_observation(
            frame.grille,
            self.dernier.niveau,
            self.dernier.score,
            # Le fil ne rend aucun compteur par frame (§A1.4) : le compteur
            # local fait l'affichage, la réconciliation officielle passant par
            # le résumé de scorecard (§A5.3).
            self.comptage.actions_niveau,
            self.dernier.actions_disponibles,
        )
        transitoires = sum(
            1 for candidate in self.dernier.frames if candidate.type is TypeFrame.TRANSITOIRE
        )
        if transitoires:
            rendu += (
                f"\n({transitoires} frame(s) intermédiaire(s) conservée(s), "
                f"consultables par inspect sur le tour {self.memoire.tour_courant})"
            )
        return rendu

    def actions_disponibles(self) -> Sequence[str]:
        return () if self.dernier is None else self.dernier.actions_disponibles

    def derniere_issue(self) -> IssueArc | None:
        return self._derniere_issue

    def etat_terminal(self) -> str | None:
        """Motif d'arrêt terminal (§A5.4, §H8.3) : « victoire » sur l'état `WIN`.

        `GAME_OVER` n'est pas terminal : `RESET` reste jouable (§A1.2) et relance la
        tentative — c'est le Bug-Fixing de la boucle qui traite l'échec (§H8.1).
        """
        if self.dernier is not None and self.dernier.etat is EtatArc.GAGNEE:
            return "victoire"
        return None

    # ------------------------------------------------------------------ outils
    def outils(self) -> list[Outil]:
        """Un outil par commande que la frame courante déclare (§A5.2).

        Le filtrage vient de la frame, pas d'une liste figée : si l'environnement
        cesse d'offrir une commande, l'agent cesse de la voir. Seul `reset` est
        toujours offert : le protocole le rend toujours jouable (§A1.2) et le fil
        ne le déclare jamais dans `available_actions` (§A1.4).
        """
        commandes = list(self.actions_disponibles())
        if "RESET" not in commandes:
            commandes.append("RESET")
        outils: list[Outil] = []
        for commande in commandes:
            nom = commande.lower()
            if nom not in DESCRIPTIONS:
                continue
            outils.append(
                Outil(
                    nom=nom,
                    description=DESCRIPTIONS[nom],
                    parametres=self._parametres(nom),
                    fonction=self._fabriquer(commande),
                    etiquettes=frozenset({ETIQUETTE_ACTION}),
                )
            )
        return outils

    def _parametres(self, nom: str) -> dict[str, Any]:
        proprietes: dict[str, Any] = {}
        requis: list[str] = []
        if nom == "action6":
            proprietes.update({"row": {"type": "integer"}, "col": {"type": "integer"}})
            requis.extend(["row", "col"])
        if self.avec_prediction:
            # Garde de prédiction (§H16.2) : le schéma porte l'exigence, le registre
            # la fait respecter (§H7.4) — une action sans prédiction n'est pas jouée.
            proprietes["prediction"] = {"type": "string", "description": DESCRIPTION_PREDICTION}
            if self.prediction_requise:
                requis.append("prediction")
        parametres: dict[str, Any] = {"type": "object", "properties": proprietes}
        if requis:
            parametres["required"] = requis
        return parametres

    def _fabriquer(self, commande: str) -> Any:
        if commande == "ACTION6":

            def executer_clic(row: int, col: int, prediction: str | None = None) -> str:
                return self.jouer(commande, (int(row), int(col)), prediction=prediction)

            return executer_clic

        def executer(prediction: str | None = None) -> str:
            return self.jouer(commande, prediction=prediction)

        return executer

    # ------------------------------------------------------------------- jouer
    def jouer(
        self,
        commande: str,
        coordonnees: tuple[int, int] | None = None,
        prediction: str | None = None,
    ) -> str:
        """Joue une commande et rend l'observation résultante (§A5.2).

        `prediction` (§H16.2) : acheminée tronquée dans `reasoning` des commandes
        `ACTION1`–`ACTION7` — auditable dans le scorecard. `RESET` n'en porte pas
        sur le fil mesuré (§A1.4).
        """
        if self.guid is None or self.dernier is None:
            raise RuntimeError("partie non démarrée : appeler demarrer() d'abord")
        # RESET est toujours jouable (§A1.2) : le fil ne le déclare jamais (§A1.4).
        disponibles = set(self.actions_disponibles()) | {"RESET"}
        if commande not in disponibles:
            raise ActionIndisponible(
                f"« {commande} » n'est pas déclarée par la frame courante ; "
                f"disponibles : {', '.join(sorted(disponibles)) or 'aucune'}"
            )
        if commande == "ACTION6":
            if coordonnees is None:
                raise CoordonneesInvalides("ACTION6 exige row et col")
            self._valider(coordonnees)

        game_id = self.game_id or self.dernier.game_id
        if commande == "RESET":
            resultat = self.client.reset(game_id=game_id, card_id=self.card_id, guid=self.guid)
        else:
            numero = int(commande.removeprefix("ACTION"))
            resultat = self.client.action(
                numero,
                game_id=game_id,
                guid=self.guid,
                coordonnees=coordonnees,
                reasoning=prediction[:PREDICTION_MAX_CARACTERES] if prediction else None,
            )
        self._absorber(resultat, compte_une_action=True)
        return self.observation()

    @staticmethod
    def _valider(coordonnees: tuple[int, int]) -> None:
        for nom, valeur in zip(("row", "col"), coordonnees, strict=True):
            if not 0 <= valeur < COTE:
                raise CoordonneesInvalides(f"{nom}={valeur} hors de la grille (0 à {COTE - 1})")

    # ---------------------------------------------------------------- internes
    def _absorber(self, resultat: FrameResult, compte_une_action: bool) -> None:
        """Met à jour mémoire, compteurs locaux et issue (§A5.3)."""
        niveau_avant = self.dernier.niveau if self.dernier else resultat.niveau
        self.memoire.enregistrer_tour(
            [(frame.type.value, frame.grille) for frame in resultat.frames]
        )
        if compte_une_action:
            self.comptage.actions_niveau += 1
            self.comptage.actions_jeu += 1
        if resultat.niveau != niveau_avant:
            self.comptage.actions_niveau = 0
        self.dernier = resultat
        if self.registre is not None:
            self.registre.synchroniser(ETIQUETTE_ACTION, self.outils())
        self._derniere_issue = IssueArc(
            observation=self.observation(), evenement=self._evenement(resultat)
        )

    @staticmethod
    def _evenement(resultat: FrameResult) -> Evenement:
        if resultat.etat is EtatArc.GAGNEE:
            return Evenement.NIVEAU_COMPLETE
        if resultat.etat is EtatArc.PERDUE:
            return Evenement.GAME_OVER
        if resultat.frames and resultat.frames[-1].type is TypeFrame.INIT_NIVEAU:
            return Evenement.NIVEAU_COMPLETE
        return Evenement.PREDICTION_CONFIRMEE

    def resume(self) -> dict[str, Any]:
        """Résumé journalisable : des compteurs, aucune grille (§H4.6)."""
        return {
            "guid": self.guid,
            "niveau": self.dernier.niveau if self.dernier else None,
            "score": self.dernier.score if self.dernier else 0,
            "etat": self.dernier.etat.value if self.dernier else None,
            **self.comptage.resume(),
            "memoire": self.memoire.resume(),
        }
