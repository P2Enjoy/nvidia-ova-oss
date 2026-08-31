"""Client de l'API ARC-AGI-3 : commandes typées et historique typé.

@spec docs/BACKLOG.md U17 — Client API ARC ; U22 — format de fil mesuré
@spec docs/SPEC_ARCAGI3.md §A2.1 (méthodes, `FrameResult`, cookies), §A2.2
      (historique typé), §A2.3 (garde anti-publication), §A1.2 (protocole),
      §A1.3–A1.4 (format de fil MESURÉ par la sonde U22), §A4.2 (conversion
      (row, col) → {x, y} confinée ici)
@spec docs/SPEC_HARNAIS.md §H4.5 (retries partagés), §H4.6 (aucun secret journalisé)

**La garde anti-publication est la pièce maîtresse de ce module.** Jouer via l'API
officielle enregistre un scorecard sur le compte du responsable : un test qui
l'atteindrait par accident publierait un résultat. En mode rejeu, le client refuse
donc de se construire vers autre chose qu'un hôte local — par construction, et non
par discipline.
"""

from __future__ import annotations

import http.cookiejar
import json
import logging
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, Protocol

from avo.config import Config, Mode
from avo.transport import avec_retries

_journal = logging.getLogger("avo.arc")

#: Hôtes acceptés en mode rejeu (§A2.3). Le nom `arc-replay` est celui du service
#: compose : depuis un conteneur de la pile, c'est ainsi qu'on l'atteint.
HOTES_REJEU: Final = frozenset({"127.0.0.1", "localhost", "::1", "arc-replay"})


class EtatArc(StrEnum):
    """États rendus par le protocole (§A1.1)."""

    NON_COMMENCEE = "NOT_PLAYED"
    EN_COURS = "NOT_FINISHED"
    GAGNEE = "WIN"
    PERDUE = "GAME_OVER"


class TypeFrame(StrEnum):
    """Rôle d'une frame dans l'interaction (§A2.2, Tycho déf. 3).

    Le typage empêche le modèle — et nous — de fabriquer une transition entre deux
    grilles qui ne se sont jamais suivies comme frames de décision.
    """

    DECISION = "decision"
    TRANSITOIRE = "transient"
    TERMINAL_GAGNE = "terminal_win"
    TERMINAL_PERDU = "terminal_gameover"
    INIT_RESET = "reset_init"
    INIT_NIVEAU = "level_init"


class PublicationInterdite(RuntimeError):
    """Le client viserait un hôte qui pourrait publier un scorecard (§A2.3)."""


class ArcError(RuntimeError):
    """Erreur de l'API ARC."""


class ArcAuthError(ArcError):
    """401/403 : clé refusée. Fatale, jamais retentée."""


class ArcServeurError(ArcError):
    """5xx : panne serveur. Retentée (§H4.5)."""


class ArcTransportError(ArcError):
    """Réseau injoignable ou délai dépassé. Retentée (§H4.5)."""


class ArcProtocoleError(ArcError):
    """Réponse inexploitable ou requête refusée. Non retentée."""


@dataclass(frozen=True)
class FrameTypee:
    """Une grille reçue, avec le rôle qu'elle a joué (§A2.2)."""

    grille: list[list[int]]
    type: TypeFrame
    index: int


@dataclass(frozen=True)
class FrameResult:
    """Réponse normalisée d'une commande (§A2.1, format de fil §A1.4).

    `score` est le nombre de niveaux complétés (`levels_completed` du fil) ;
    `niveau` en est dérivé — le fil ne porte ni niveau courant ni compteur
    d'actions (§A5.3 : le comptage est local).
    """

    guid: str
    game_id: str
    frames: tuple[FrameTypee, ...]
    etat: EtatArc
    score: int
    niveau: int
    niveaux_requis: int
    actions_disponibles: tuple[str, ...]
    remise_a_zero_complete: bool = False

    @property
    def frame_de_decision(self) -> FrameTypee | None:
        """Dernière frame sur laquelle l'agent peut agir, s'il y en a une."""
        for frame in reversed(self.frames):
            if frame.type in (TypeFrame.DECISION, TypeFrame.INIT_RESET, TypeFrame.INIT_NIVEAU):
                return frame
        return None

    @property
    def terminee(self) -> bool:
        return self.etat in (EtatArc.GAGNEE, EtatArc.PERDUE)

    def resume(self) -> dict[str, Any]:
        """Résumé journalisable : des compteurs, aucune grille (§H4.6)."""
        return {
            "etat": self.etat.value,
            "score": self.score,
            "niveau": self.niveau,
            "niveaux_requis": self.niveaux_requis,
            "frames": len(self.frames),
            "types": [frame.type.value for frame in self.frames],
        }


@dataclass
class EntreeHistorique:
    """Une commande et ce qu'elle a produit, rattachée à sa frame de décision (§A2.2)."""

    index: int
    niveau: int
    commande: str
    coordonnees: tuple[int, int] | None
    frame_de_decision: int | None
    types_recus: list[str]
    etat: str
    score: int

    def en_json(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "niveau": self.niveau,
            "commande": self.commande,
            "coordonnees": list(self.coordonnees) if self.coordonnees else None,
            "frame_de_decision": self.frame_de_decision,
            "types_recus": self.types_recus,
            "etat": self.etat,
            "score": self.score,
        }


@dataclass
class HistoriqueFrames:
    """Historique typé d'une partie, persisté par niveau (§A2.2)."""

    entrees: list[EntreeHistorique] = field(default_factory=list)
    frames: list[FrameTypee] = field(default_factory=list)

    def enregistrer(
        self,
        commande: str,
        coordonnees: tuple[int, int] | None,
        resultat: FrameResult,
        frame_de_decision: int | None,
    ) -> None:
        depart = len(self.frames)
        self.frames.extend(
            FrameTypee(frame.grille, frame.type, depart + position)
            for position, frame in enumerate(resultat.frames)
        )
        self.entrees.append(
            EntreeHistorique(
                index=len(self.entrees),
                niveau=resultat.niveau,
                commande=commande,
                coordonnees=coordonnees,
                frame_de_decision=frame_de_decision,
                types_recus=[frame.type.value for frame in resultat.frames],
                etat=resultat.etat.value,
                score=resultat.score,
            )
        )

    def derniere_frame_de_decision(self) -> int | None:
        for frame in reversed(self.frames):
            if frame.type in (TypeFrame.DECISION, TypeFrame.INIT_RESET, TypeFrame.INIT_NIVEAU):
                return frame.index
        return None

    def ecrire(self, dossier: Path) -> None:
        """Écrit un JSONL par niveau dans `runs/<id>/frames/` (§A2.2, §H6.1)."""
        dossier.mkdir(parents=True, exist_ok=True)
        par_niveau: dict[int, list[EntreeHistorique]] = {}
        for entree in self.entrees:
            par_niveau.setdefault(entree.niveau, []).append(entree)
        for niveau, entrees in par_niveau.items():
            chemin = dossier / f"niveau_{niveau:02d}.jsonl"
            chemin.write_text(
                "".join(
                    json.dumps(entree.en_json(), ensure_ascii=False) + "\n" for entree in entrees
                ),
                encoding="utf-8",
            )


class TransportArc(Protocol):
    """Contrat minimal d'un transport HTTP, pour rendre le client éprouvable."""

    def __call__(
        self,
        methode: str,
        url: str,
        corps: bytes | None,
        entetes: Mapping[str, str],
        timeout: float,
    ) -> tuple[int, bytes]: ...


class TransportUrllib:
    """Transport par défaut, bibliothèque standard, UN pot de cookies par instance.

    L'API officielle route les commandes d'une partie par affinité de session :
    les cookies (`AWSALB*`) posés au `RESET` doivent revenir sur chaque commande
    suivante (§A1.4). Chaque `ArcClient` reçoit donc sa propre instance — les
    sessions de deux clients ne se mélangent jamais.
    """

    def __init__(self) -> None:
        self._ouvreur = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    def __call__(
        self,
        methode: str,
        url: str,
        corps: bytes | None,
        entetes: Mapping[str, str],
        timeout: float,
    ) -> tuple[int, bytes]:
        requete = urllib.request.Request(url, data=corps, method=methode)  # noqa: S310
        for nom, valeur in entetes.items():
            requete.add_header(nom, valeur)
        try:
            with self._ouvreur.open(requete, timeout=timeout) as reponse:
                return int(reponse.status), reponse.read()
        except urllib.error.HTTPError as erreur:
            return int(erreur.code), erreur.read()
        except urllib.error.URLError as erreur:
            raise ArcTransportError(f"API ARC injoignable : {erreur.reason}") from erreur
        except TimeoutError as erreur:
            raise ArcTransportError(f"délai dépassé après {timeout} s") from erreur


def transport_urllib(
    methode: str, url: str, corps: bytes | None, entetes: Mapping[str, str], timeout: float
) -> tuple[int, bytes]:
    """Transport stdlib SANS état de session — pour un appel isolé (sonde, listing)."""
    return TransportUrllib()(methode, url, corps, entetes, timeout)


def verifier_hote(base_url: str, mode: Mode) -> None:
    """Garde anti-publication (§A2.3).

    En mode rejeu, viser autre chose qu'un hôte local est une erreur fatale : jouer
    via l'API officielle publierait un scorecard sur le compte du responsable. La
    protection est structurelle, pas une consigne à respecter.
    """
    if mode is not Mode.REJEU:
        return
    reste = base_url.split("://", 1)[-1]
    hote = reste.split("/", 1)[0].split("@")[-1]
    if hote.startswith("["):
        hote = hote[1 : hote.index("]")] if "]" in hote else hote
    else:
        hote = hote.split(":", 1)[0]
    if hote not in HOTES_REJEU:
        raise PublicationInterdite(
            f"en mode rejeu, l'API ARC doit pointer un hôte local ; « {hote} » n'en est "
            f"pas un (autorisés : {', '.join(sorted(HOTES_REJEU))}). Jouer via l'API "
            "officielle publierait un scorecard sur le compte du responsable "
            "(docs/SPEC_ARCAGI3.md §A2.3)."
        )


class ArcClient:
    """Client de l'API ARC-AGI-3 (§A2.1)."""

    def __init__(
        self,
        config: Config,
        transport: TransportArc | None = None,
        dormir: Any = None,
        alea: Any = None,
    ) -> None:
        verifier_hote(config.arc_base_url, config.mode)
        self.config = config
        # Un pot de cookies PAR CLIENT : l'affinité de session de l'API (§A1.4)
        # exige que les cookies posés au RESET reviennent sur chaque commande.
        self._transport: TransportArc = transport or TransportUrllib()
        self._dormir = dormir
        self._alea = alea
        self.historique = HistoriqueFrames()
        self._score_courant = 0

    # ------------------------------------------------------------------ requête
    def _entetes(self) -> dict[str, str]:
        """En-têtes. La clé n'est JAMAIS journalisée (§H4.6)."""
        entetes = {"Content-Type": "application/json"}
        if self.config.arc_api_key:
            entetes["X-API-Key"] = self.config.arc_api_key
        return entetes

    def _appeler(self, methode: str, chemin: str, corps: Any = None) -> Any:
        charge = json.dumps(corps).encode() if corps is not None else None
        url = f"{self.config.arc_base_url}{chemin}"

        def tenter() -> Any:
            statut, brut = self._transport(
                methode, url, charge, self._entetes(), self.config.timeout_s
            )
            return self._classer(statut, brut, chemin)

        options: dict[str, Any] = {"journal": _journal}
        if self._dormir is not None:
            options["dormir"] = self._dormir
        if self._alea is not None:
            options["alea"] = self._alea
        return avec_retries(tenter, (ArcServeurError, ArcTransportError), **options)

    @staticmethod
    def _classer(statut: int, brut: bytes, chemin: str) -> Any:
        if statut in (401, 403):
            raise ArcAuthError(
                f"authentification refusée sur {chemin} (HTTP {statut}) — vérifier ARC_API_KEY"
            )
        if statut >= 500:
            raise ArcServeurError(f"erreur serveur HTTP {statut} sur {chemin}")
        try:
            charge = json.loads(brut)
        except json.JSONDecodeError as erreur:
            raise ArcProtocoleError(f"{chemin} : réponse HTTP {statut} non JSON") from erreur
        if statut >= 400:
            detail = charge.get("error") if isinstance(charge, dict) else charge
            raise ArcProtocoleError(f"{chemin} : HTTP {statut} — {detail}")
        return charge

    # ------------------------------------------------------------------ typage
    @staticmethod
    def _nommer_action(numero: int) -> str:
        """Nom normalisé d'une action du fil : `0` → `RESET`, `n` → `ACTIONn` (§A1.4)."""
        return "RESET" if numero == 0 else f"ACTION{numero}"

    def _typer(self, charge: Mapping[str, Any], commande: str) -> FrameResult:
        """Normalise une réponse du fil mesuré (§A1.4) et étiquette les frames (§A2.2)."""
        grilles = list(charge.get("frame") or [])
        etat = EtatArc(str(charge.get("state", EtatArc.EN_COURS.value)))
        score = int(charge.get("levels_completed") or 0)
        niveaux_requis = int(charge.get("win_levels") or 0)
        # Le fil ne porte pas de niveau courant : il se dérive (§A1.4).
        niveau = min(score + 1, niveaux_requis) if niveaux_requis else score + 1

        if etat is EtatArc.GAGNEE:
            dernier = TypeFrame.TERMINAL_GAGNE
        elif etat is EtatArc.PERDUE:
            dernier = TypeFrame.TERMINAL_PERDU
        elif commande == "RESET":
            dernier = TypeFrame.INIT_RESET
        elif score > self._score_courant:
            dernier = TypeFrame.INIT_NIVEAU
        else:
            dernier = TypeFrame.DECISION
        self._score_courant = score

        frames = tuple(
            FrameTypee(
                grille=grille,
                type=dernier if position == len(grilles) - 1 else TypeFrame.TRANSITOIRE,
                index=position,
            )
            for position, grille in enumerate(grilles)
        )
        return FrameResult(
            guid=str(charge.get("guid", "")),
            game_id=str(charge.get("game_id", "")),
            frames=frames,
            etat=etat,
            score=score,
            niveau=max(niveau, 1),
            niveaux_requis=niveaux_requis,
            actions_disponibles=tuple(
                self._nommer_action(int(numero))
                for numero in (charge.get("available_actions") or ())
            ),
            remise_a_zero_complete=bool(charge.get("full_reset") or False),
        )

    # ---------------------------------------------------------------- méthodes
    def games(self) -> list[dict[str, Any]]:
        """Listing des jeux et de leurs baselines humaines (§A1.3, §A6.2)."""
        charge = self._appeler("GET", "/api/games")
        return list(charge) if isinstance(charge, list) else []

    def open_scorecard(self, tags: Sequence[str] = ()) -> str:
        charge = self._appeler("POST", "/api/scorecard/open", {"tags": list(tags)})
        return str(charge["card_id"])

    def scorecard(self, identifiant: str) -> dict[str, Any]:
        charge = self._appeler("GET", f"/api/scorecard/{identifiant}")
        return dict(charge)

    def close_scorecard(self, identifiant: str) -> dict[str, Any]:
        charge = self._appeler("POST", "/api/scorecard/close", {"card_id": identifiant})
        return dict(charge)

    def reset(
        self, game_id: str | None = None, card_id: str | None = None, guid: str | None = None
    ) -> FrameResult:
        """`RESET` : crée la partie sans `guid`, relance le niveau courant avec (§A1.2).

        Le fil mesuré exige `game_id` ET `card_id` (§A1.4) ; le serveur nomme leur
        absence — le client transmet ce qu'on lui donne et laisse le refus parler.
        """
        corps: dict[str, Any] = {}
        if game_id:
            corps["game_id"] = game_id
        if card_id:
            corps["card_id"] = card_id
        if guid:
            corps["guid"] = guid
        if guid is None:
            self._score_courant = 0
        return self._commande("RESET", corps, None)

    def action(
        self,
        numero: int,
        game_id: str,
        guid: str,
        coordonnees: tuple[int, int] | None = None,
    ) -> FrameResult:
        """`ACTION1`–`ACTION7` : `game_id` et `guid` requis dans chaque action (§A1.4).

        `ACTION6` porte des coordonnées, données en (row, col) internes : la
        conversion vers le fil — `x` = colonne, `y` = ligne — est confinée ici
        (§A4.2, mesurée : `{row, col}` est refusé par le serveur).
        """
        corps: dict[str, Any] = {"game_id": game_id, "guid": guid}
        if coordonnees is not None:
            row, col = coordonnees
            corps["x"], corps["y"] = col, row
        return self._commande(f"ACTION{numero}", corps, coordonnees)

    def _commande(
        self, commande: str, corps: dict[str, Any], coordonnees: tuple[int, int] | None
    ) -> FrameResult:
        depuis = self.historique.derniere_frame_de_decision()
        charge = self._appeler("POST", f"/api/cmd/{commande}", corps)
        resultat = self._typer(charge, commande)
        self.historique.enregistrer(commande, coordonnees, resultat, depuis)
        _journal.info("commande ARC", extra={"commande": commande, **resultat.resume()})
        return resultat
