"""Environnement Entrepôt : état de vérité, transitions, obligations, issues.

@spec docs/BACKLOG.md U29a1 — environnement Entrepôt du banc a
@spec docs/SPEC_BANCS.md §S3.1 (état de vérité, jamais montré à l'agent),
      §S3.2 (espace d'actions et validité ; une action invalide rend une erreur
      locale nommée et ne change pas l'état), §S3.5 (obligation d'un événement,
      évaluée sur l'état RÉEL au moment de l'action), §S3.6 (le bruit accompagne
      l'observation sans altérer l'état), §S3.7 (une action consomme l'événement,
      fin d'épisode), §S5.2 (la première action de l'événement fait le score)

L'état de vérité appartient à l'environnement et évolue exclusivement par les
actions VALIDES de l'agent. L'agent ne voit que `observation()` et les issues.
"""

from __future__ import annotations

from dataclasses import dataclass

from avo.bancs.skillexec.generation import (
    COMMANDE,
    ENTETE_TELEMETRIE,
    MAINTENANCE,
    NB_ETAGERES,
    RECEPTION,
    Episode,
    EvenementEntrepot,
)
from avo.bancs.skillexec.score import Releve

#: Motif d'arrêt rendu par `etat_terminal()` (§S3.7).
MOTIF_EPUISE = "épisode épuisé : tous les événements sont consommés"


@dataclass(frozen=True)
class IssueBanc:
    """Issue d'une action : le texte rendu à l'agent, et les deux verdicts.

    `valide` dit si la transition a été acceptée (§S3.2) ; `correcte` si l'action
    était l'obligation de l'événement (§S3.5). L'agent voit `observation` ; les
    verdicts alimentent le relevé, jamais le prompt.
    """

    observation: str
    valide: bool
    correcte: bool


class EnvironnementEntrepot:
    """État de vérité et règles de l'entrepôt (§S3).

    Chaque action — valide ou non — consomme l'événement courant (§S3.7) et
    compte au relevé (§S5.2) : un événement reçoit exactement une action.
    """

    def __init__(self, episode: Episode) -> None:
        self._episode = episode
        self._etageres: list[str | None] = [None] * NB_ETAGERES
        #: Articles livrés non rangés (§S3.2 : `store` n'accepte qu'eux).
        self._quai: set[str] = set()
        self._index = 0
        #: Dernier indice d'événement dont l'arrivée a été appliquée (§S3.2).
        self._prepare_index = -1
        self.releve = Releve(seed=episode.seed, horizon=episode.horizon, bruit=episode.bruit)

    def _preparer(self) -> None:
        """Applique l'arrivée de l'événement courant, une seule fois : l'article
        d'une réception entre au quai dès que l'événement est observable, pour que
        le `store` dû soit valide (§S3.2, §S3.5)."""
        evenement = self._evenement_courant()
        if evenement is not None and self._prepare_index != self._index:
            self._prepare_index = self._index
            if evenement.type == RECEPTION:
                self._quai.add(evenement.article)

    # ------------------------------------------------------------ observation
    def observation(self) -> str:
        """L'événement courant et sa télémétrie (§S3.6) ; le motif de fin sinon."""
        self._preparer()
        if self._index >= len(self._episode.evenements):
            return MOTIF_EPUISE
        evenement = self._episode.evenements[self._index]
        lignes = [evenement.observation]
        bruit = self._episode.telemetrie[self._index]
        if bruit:
            lignes.append(ENTETE_TELEMETRIE)
            lignes.extend(bruit)
        return "\n".join(lignes)

    def etat_terminal(self) -> str | None:
        """Motif d'arrêt quand l'épisode est épuisé (§S3.7), sinon None."""
        if self._index >= len(self._episode.evenements):
            return MOTIF_EPUISE
        return None

    # ----------------------------------------------------------------- accès
    def etagere(self, nom: str) -> str | None:
        """Contenu réel d'une étagère — pour les preuves, jamais pour l'agent."""
        return self._etageres[self._indice(nom)]

    @staticmethod
    def _indice(nom: str) -> int:
        prefixe = "etagere_"
        if not nom.startswith(prefixe):
            raise ValueError(f"étagère inconnue : {nom}")
        try:
            indice = int(nom[len(prefixe) :])
        except ValueError as exc:
            raise ValueError(f"étagère inconnue : {nom}") from exc
        if not 0 <= indice < NB_ETAGERES:
            raise ValueError(f"étagère inconnue : {nom}")
        return indice

    def _evenement_courant(self) -> EvenementEntrepot | None:
        if self._index >= len(self._episode.evenements):
            return None
        return self._episode.evenements[self._index]

    # --------------------------------------------------------------- actions
    def store(self, article: str, etagere: str) -> IssueBanc:
        """`store <article> <etagere>` (§S3.2)."""
        self._preparer()
        evenement = self._evenement_courant()
        if evenement is None:
            return IssueBanc(f"error: {MOTIF_EPUISE}", valide=False, correcte=False)
        try:
            indice = self._indice(etagere)
        except ValueError as exc:
            return self._consommer(False, False, f"error: {exc}")
        if article not in self._quai:
            return self._consommer(
                False, False, f"error: {article} n'est pas en attente de rangement."
            )
        if self._etageres[indice] is not None:
            return self._consommer(False, False, f"error: {etagere} est occupée.")
        correcte = evenement.type == RECEPTION and evenement.article == article
        self._quai.discard(article)
        self._etageres[indice] = article
        return self._consommer(True, correcte, f"Succès : {article} rangé sur {etagere}.")

    def ship(self, article: str, etagere: str) -> IssueBanc:
        """`ship <article> <etagere>` (§S3.2) : l'article est détruit."""
        self._preparer()
        evenement = self._evenement_courant()
        if evenement is None:
            return IssueBanc(f"error: {MOTIF_EPUISE}", valide=False, correcte=False)
        try:
            indice = self._indice(etagere)
        except ValueError as exc:
            return self._consommer(False, False, f"error: {exc}")
        if self._etageres[indice] != article:
            return self._consommer(False, False, f"error: {etagere} ne porte pas {article}.")
        correcte = evenement.type == COMMANDE and evenement.article == article
        self._etageres[indice] = None
        return self._consommer(True, correcte, f"Succès : {article} expédié depuis {etagere}.")

    def move(self, article: str, source: str, destination: str) -> IssueBanc:
        """`move <article> <src> <dst>` (§S3.2)."""
        self._preparer()
        evenement = self._evenement_courant()
        if evenement is None:
            return IssueBanc(f"error: {MOTIF_EPUISE}", valide=False, correcte=False)
        try:
            indice_source = self._indice(source)
            indice_destination = self._indice(destination)
        except ValueError as exc:
            return self._consommer(False, False, f"error: {exc}")
        if self._etageres[indice_source] != article:
            return self._consommer(False, False, f"error: {source} ne porte pas {article}.")
        if self._etageres[indice_destination] is not None:
            return self._consommer(False, False, f"error: {destination} est occupée.")
        correcte = evenement.type == MAINTENANCE and evenement.etagere == source
        self._etageres[indice_source] = None
        self._etageres[indice_destination] = article
        return self._consommer(
            True, correcte, f"Succès : {article} déplacé de {source} vers {destination}."
        )

    def wait(self) -> IssueBanc:
        """`wait` (§S3.2, toujours valide) : dû seulement au cas de §S3.5."""
        self._preparer()
        evenement = self._evenement_courant()
        if evenement is None:
            return IssueBanc(f"error: {MOTIF_EPUISE}", valide=False, correcte=False)
        correcte = self._wait_du(evenement)
        return self._consommer(True, correcte, "Rien à faire.")

    def _wait_du(self, evenement: EvenementEntrepot) -> bool:
        """`wait` n'est l'obligation que si la maintenance vise une étagère
        réellement vide — divergence de §S3.4, rien à déplacer (§S3.5)."""
        if evenement.type != MAINTENANCE or evenement.etagere is None:
            return False
        return self._etageres[self._indice(evenement.etagere)] is None

    # -------------------------------------------------------------- mécanique
    def _consommer(self, valide: bool, correcte: bool, observation: str) -> IssueBanc:
        """Compte la première action au relevé et consomme l'événement (§S3.7).

        L'article d'une réception non honorée reste au quai : un `store` tardif
        demeure VALIDE (il ne sera plus l'obligation d'aucun événement, donc
        jamais correct).
        """
        self.releve.compter(valide, correcte)
        self._index += 1
        return IssueBanc(observation, valide=valide, correcte=correcte)
