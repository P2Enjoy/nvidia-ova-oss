"""Serveur `arc-replay` : contrat ARC-AGI-3 local, jeu synthétique et épisodes.

@spec docs/BACKLOG.md U16 ; U22 — format de fil mesuré
@spec docs/SPEC_ARCAGI3.md §A3.1 (même contrat HTTP que l'API officielle),
      §A3.3 (rejeu d'épisodes, déviation = erreur explicite), §A1.2 (protocole),
      §A1.3 (surfaces), §A1.4 (format de fil MESURÉ par la sonde U22)

Le format de fil implémenté ici est celui MESURÉ sur l'API officielle par la sonde
U22 (2026-08-31, capture committée sous `tests/fixtures/arc/episodes/`) : `frame`
au singulier, `levels_completed`/`win_levels`, `available_actions` en entiers,
`game_id` requis dans chaque action, `card_id` requis au `RESET`, `x`/`y` pour
`ACTION6`.
"""

from __future__ import annotations

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from arc_replay.jeu_cible import JeuCible, Resultat

#: Jeu servi par défaut. Identifiant stable : les tests s'y réfèrent.
JEU = {
    "game_id": "cible-synthetique",
    "title": "CIBLE",
    "tags": ["keyboard_click"],
}

#: Point de santé, hors contrat officiel (préfixé comme dans `llm-replay`).
ROUTE_SANTE = "/_health"


class EpisodeDevie(LookupError):
    """La requête ne suit pas l'épisode enregistré (§A3.3)."""


class EtatServeur:
    """Parties en cours, scorecards ouverts, et épisode éventuellement rejoué."""

    def __init__(self, niveaux: int = 3, episode: Path | None = None) -> None:
        self.niveaux = niveaux
        self.parties: dict[str, JeuCible] = {}
        self.scorecards: dict[str, dict[str, Any]] = {}
        #: L'attribution au scorecard est faite par le RESET (§A1.4) : les actions
        #: ne portent pas de `card_id`, la partie s'en souvient.
        self.carte_par_partie: dict[str, str] = {}
        self.verrou = threading.Lock()
        self.episode = self._charger_episode(episode) if episode else None
        self.position_episode = 0

    @staticmethod
    def _charger_episode(chemin: Path) -> list[dict[str, Any]]:
        return [
            json.loads(ligne)
            for ligne in chemin.read_text(encoding="utf-8").splitlines()
            if ligne.strip()
        ]

    def nouvelle_partie(self) -> tuple[str, JeuCible]:
        guid = uuid.uuid4().hex
        jeu = JeuCible(niveaux=self.niveaux)
        with self.verrou:
            self.parties[guid] = jeu
        return guid, jeu

    def partie(self, guid: str) -> JeuCible:
        with self.verrou:
            jeu = self.parties.get(guid)
        if jeu is None:
            raise KeyError(f"partie inconnue : {guid}")
        return jeu


def _carte_en_json(carte: dict[str, Any]) -> dict[str, Any]:
    """Résumé de scorecard, au gabarit du résumé mesuré (§A1.4) : les parties
    apparaissent dans `environments`, une entrée par jeu."""
    return {
        "card_id": carte["card_id"],
        "tags": carte["tags"],
        "closed": carte["closed"],
        "environments": [{"id": game_id, **donnees} for game_id, donnees in carte["cards"].items()],
    }


def _numero_action(commande: str) -> int:
    """Numéro de fil d'une commande : `RESET` → 0, `ACTIONn` → n (§A1.4)."""
    return 0 if commande == "RESET" else int(commande.removeprefix("ACTION"))


def _resultat_en_json(
    guid: str,
    resultat: Resultat,
    niveaux: int,
    commande: str,
    donnees: dict[str, Any],
    full_reset: bool,
) -> dict[str, Any]:
    """Forme de réponse du contrat mesuré (§A1.4).

    Ni niveau courant, ni score, ni compteur d'actions : comme l'API officielle,
    le rejoueur ne rend que `levels_completed` et `win_levels` — et il ne déclare
    jamais `RESET` (0) dans `available_actions`.
    """
    return {
        "guid": guid,
        "game_id": JEU["game_id"],
        "frame": resultat.frames,
        "state": resultat.etat.value,
        "levels_completed": resultat.score,
        "win_levels": niveaux,
        "action_input": {"id": _numero_action(commande), "data": donnees, "reasoning": None},
        "full_reset": full_reset,
        "available_actions": [
            _numero_action(action) for action in resultat.actions_disponibles if action != "RESET"
        ],
    }


class GestionnaireArc(BaseHTTPRequestHandler):
    """Gestionnaire HTTP du contrat ARC-AGI-3 local."""

    protocol_version = "HTTP/1.1"
    etat: EtatServeur

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Silencieux : les tests n'ont pas besoin du journal d'accès."""

    # ------------------------------------------------------------------ sortie
    def _repondre(self, status: int, charge: Any) -> None:
        corps = json.dumps(charge, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def _erreur(self, status: int, message: str) -> None:
        self._repondre(status, {"error": message})

    def _corps(self) -> dict[str, Any]:
        longueur = int(self.headers.get("Content-Length") or 0)
        if longueur == 0:
            return {}
        charge = json.loads(self.rfile.read(longueur))
        return charge if isinstance(charge, dict) else {}

    # ------------------------------------------------------------------ routes
    def do_GET(self) -> None:  # noqa: N802 — nom imposé par BaseHTTPRequestHandler
        if self.path == ROUTE_SANTE:
            self._repondre(200, {"status": "ok", "parties": len(self.etat.parties)})
            return
        if self.path == "/api/games":
            jeu = JeuCible(niveaux=self.etat.niveaux)
            self._repondre(200, [{**JEU, "baseline_actions": jeu.baselines()}])
            return
        if self.path.startswith("/api/scorecard/"):
            identifiant = self.path.rsplit("/", 1)[-1]
            carte = self.etat.scorecards.get(identifiant)
            if carte is None:
                self._erreur(404, f"scorecard inconnu : {identifiant}")
                return
            self._repondre(200, _carte_en_json(carte))
            return
        self._erreur(404, f"route inconnue : {self.path}")

    def do_POST(self) -> None:  # noqa: N802 — nom imposé par BaseHTTPRequestHandler
        corps = self._corps()
        if self.path == "/api/scorecard/open":
            identifiant = uuid.uuid4().hex
            self.etat.scorecards[identifiant] = {
                "card_id": identifiant,
                "tags": corps.get("tags", []),
                "cards": {},
                "closed": False,
            }
            self._repondre(200, {"card_id": identifiant})
            return
        if self.path == "/api/scorecard/close":
            carte = self.etat.scorecards.get(str(corps.get("card_id")))
            if carte is None:
                self._erreur(404, "scorecard inconnu")
                return
            carte["closed"] = True
            self._repondre(200, _carte_en_json(carte))
            return
        if self.path.startswith("/api/cmd/"):
            self._commande(self.path.rsplit("/", 1)[-1], corps)
            return
        self._erreur(404, f"route inconnue : {self.path}")

    def _commande(self, commande: str, corps: dict[str, Any]) -> None:
        """`RESET` et `ACTION1`–`ACTION7`, au fil mesuré (§A1.4)."""
        if self.etat.episode is not None:
            self._rejouer_episode(commande, corps)
            return
        game_id = str(corps.get("game_id") or "")
        if game_id != JEU["game_id"]:
            # Même refus que l'API officielle : un jeu absent du backend est nommé.
            self._erreur(400, f"game {game_id or '(absent)'} not found")
            return
        full_reset = False
        try:
            if commande == "RESET":
                card_id = str(corps.get("card_id") or "")
                carte = self.etat.scorecards.get(card_id)
                if carte is None or carte.get("closed"):
                    self._erreur(400, f"card_id {card_id or '(absent)'} inconnu ou fermé")
                    return
                guid = str(corps.get("guid") or "")
                if guid and guid in self.etat.parties:
                    jeu = self.etat.partie(guid)
                else:
                    guid, jeu = self.etat.nouvelle_partie()
                    full_reset = True
                self.etat.carte_par_partie[guid] = card_id
                resultat = jeu.reset()
            else:
                guid = str(corps.get("guid") or "")
                if not guid:
                    self._erreur(400, "guid requis pour une action (§A1.4)")
                    return
                jeu = self.etat.partie(guid)
                if commande == "ACTION6":
                    x, y = corps.get("x"), corps.get("y")
                    if not isinstance(x, int) or not isinstance(y, int):
                        # Le fil mesuré exige x et y ; row/col est refusé (§A1.4).
                        self._erreur(400, "ACTION6 exige x et y entiers (§A1.4)")
                        return
                    resultat = jeu.jouer(commande, y, x)
                else:
                    resultat = jeu.jouer(commande)
        except KeyError as erreur:
            self._erreur(404, str(erreur))
            return
        except ValueError as erreur:
            self._erreur(400, str(erreur))
            return
        carte = self.etat.scorecards.get(self.etat.carte_par_partie.get(guid, ""))
        if carte is not None:
            carte["cards"][JEU["game_id"]] = {
                "levels_completed": resultat.score,
                "state": resultat.etat.value,
            }
        donnees = {cle: valeur for cle, valeur in corps.items() if cle in ("x", "y")}
        self._repondre(
            200,
            _resultat_en_json(guid, resultat, self.etat.niveaux, commande, donnees, full_reset),
        )

    def _rejouer_episode(self, commande: str, corps: dict[str, Any]) -> None:
        """Sert un épisode enregistré ; toute déviation est dite explicitement (§A3.3).

        La déviation porte sur la commande ET sur le corps : chaque clé du corps
        enregistré doit revenir avec la même valeur — `card_id` et `guid` exceptés,
        propres à chaque session. C'est ce qui fait de l'épisode réel une preuve du
        format de fil émis par le client, pas seulement de l'ordre des commandes.

        Le refus répond 409 : un 5xx serait retenté par le client (§H4.5) et son
        motif remplacé par « erreur serveur » — le test doit rougir LISIBLEMENT.
        """
        position = self.etat.position_episode
        episode = self.etat.episode or []
        if position >= len(episode):
            self._erreur(409, f"épisode épuisé après {position} commandes")
            return
        attendu = episode[position]
        if attendu.get("command") != commande:
            self._erreur(
                409,
                f"déviation de l'épisode à l'étape {position} : commande "
                f"« {commande} » reçue, « {attendu.get('command')} » attendue. "
                "Réenregistrez l'épisode plutôt que d'inventer une réponse "
                "(docs/SPEC_ARCAGI3.md §A3.3).",
            )
            return
        enregistre = attendu.get("request") or {}
        for cle, valeur in enregistre.items():
            if cle in ("card_id", "guid"):
                continue
            if corps.get(cle) != valeur:
                self._erreur(
                    409,
                    f"déviation de l'épisode à l'étape {position} ({commande}) : "
                    f"champ « {cle} » = {corps.get(cle)!r} reçu, {valeur!r} attendu "
                    "(docs/SPEC_ARCAGI3.md §A3.3).",
                )
                return
        self.etat.position_episode += 1
        self._repondre(200, attendu["response"])


def creer_serveur(
    port: int = 8765, niveaux: int = 3, hote: str = "127.0.0.1", episode: Path | None = None
) -> ThreadingHTTPServer:
    """Crée le serveur. `port=0` alloue un port éphémère (tests).

    `hote` vaut la boucle locale par défaut ; la pile compose passe `0.0.0.0`, sans
    quoi le port publié n'atteindrait pas le service — même mesure qu'en U5.
    """
    etat = EtatServeur(niveaux=niveaux, episode=episode)
    gestionnaire = type("GestionnaireLie", (GestionnaireArc,), {"etat": etat})
    return ThreadingHTTPServer((hote, port), gestionnaire)
