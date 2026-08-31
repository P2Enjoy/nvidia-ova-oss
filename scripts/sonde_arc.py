"""Sonde du contrat de fil de l'API ARC-AGI-3 officielle (U22).

@spec docs/BACKLOG.md U22 — Sonde de contrat API officielle
@spec docs/SPEC_ARCAGI3.md §A1.4 (format de fil à confirmer), §A3.3 (l'épisode réel
      capturé devient la première fixture d'épisode), §A4.2 (convention de
      coordonnées du fil à confirmer), §A7.2 (scorecard étiqueté)
@spec docs/SPEC_HARNAIS.md §H4.6 (aucun secret capturé ni journalisé)

Instrument de MESURE : la sonde parle à l'API au niveau transport (JSON brut) et ne
passe PAS par le parsing d'`ArcClient` — c'est précisément ce parsing que la mesure
doit confirmer ou corriger. Elle ouvre un scorecard explicitement étiqueté sonde,
joue un RESET et quelques actions sur un jeu de moindre coût, referme le scorecard,
et écrit la capture requête→réponse EXPURGÉE (aucun en-tête, donc aucune clé) :

- ``tests/fixtures/arc/episodes/sonde_u22_brut.json`` : la capture complète, y
  compris listing, refus mesurés et scorecard, pour la lecture humaine et le journal ;
- ``tests/fixtures/arc/episodes/sonde_u22.jsonl`` : les seules commandes de jeu
  acceptées, au format épisode d'`arc-replay` (§A3.3), rejouées par `make test-int`.

Protocole mesuré (2026-08-31) que cette sonde applique :

- l'API exige une **affinité de session par cookies** (`AWSALB*`) posés au RESET —
  la sonde tient un pot de cookies, comme le client devra le faire ;
- certains jeux du listing ne sont **pas servis** par le backend de jeu
  (« game … not found ») : la sonde essaie les candidats dans l'ordre du moindre
  coût et consigne chaque refus, qui fait partie de la mesure ;
- la convention de coordonnées d'ACTION6 est sondée en deux temps : d'abord
  ``{"row","col"}`` (la convention du client avant U22, §A4.2), puis ``{"x","y"}``
  — les deux échanges sont capturés, le refus étant lui-même la mesure.

Choix du jeu, générique et déterministe (aucun indice de jeu, CLAUDE_PROJECT.md) :
les jeux à modalité « click » d'abord (pour pouvoir mesurer ACTION6), la modalité
pure ``click`` avant ``keyboard_click``, puis somme des `baseline_actions`
croissante, nombre de niveaux, identifiant.

Usage : ``python scripts/sonde_arc.py`` depuis la racine (``.env`` requis :
``ARC_API_KEY`` ; l'endpoint LLM n'est pas sollicité).
"""

from __future__ import annotations

import http.cookiejar
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

from avo.config import Mode, charger  # noqa: E402

DOSSIER_EPISODES = RACINE / "tests" / "fixtures" / "arc" / "episodes"
ETIQUETTES_SONDE = ["probe", "sonde-u22"]
ACTIONS_SIMPLES_MAX = 2
JEUX_CANDIDATS_MAX = 3
TIMEOUT_S = 60.0


class Sonde:
    """Capture chaque échange HTTP, tient les cookies, n'enregistre aucun en-tête."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url
        self._api_key = api_key
        # Affinité de session mesurée : le backend de jeu route par cookies AWSALB*.
        self._ouvreur = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        self.captures: list[dict[str, Any]] = []

    def appeler(self, methode: str, chemin: str, corps: dict[str, Any] | None) -> tuple[int, Any]:
        charge = json.dumps(corps).encode() if corps is not None else None
        requete = urllib.request.Request(f"{self.base_url}{chemin}", data=charge, method=methode)
        requete.add_header("X-API-Key", self._api_key)
        if charge is not None:
            requete.add_header("Content-Type", "application/json")
        try:
            with self._ouvreur.open(requete, timeout=TIMEOUT_S) as reponse:
                statut, brut = int(reponse.status), reponse.read()
        except urllib.error.HTTPError as erreur:
            statut, brut = int(erreur.code), erreur.read()
        try:
            reponse_json: Any = json.loads(brut)
        except json.JSONDecodeError:
            reponse_json = {"_non_json": brut.decode("utf-8", "replace")[:2000]}
        # Expurgation §H4.6 : ni en-tête ni cookie ni clé — seuls méthode, chemin,
        # corps émis, statut et corps reçu entrent dans la capture.
        self.captures.append(
            {
                "method": methode,
                "path": chemin,
                "request": corps,
                "status": statut,
                "response": reponse_json,
            }
        )
        print(f"  {methode} {chemin} -> {statut}", flush=True)
        return statut, reponse_json


def _candidats(jeux: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Jeux candidats, cliquables d'abord, au moindre coût (critère générique)."""

    def cle(jeu: dict[str, Any]) -> tuple[int, int, int, int, str]:
        etiquettes = jeu.get("tags") or []
        cliquable = any("click" in etiquette for etiquette in etiquettes)
        pur_click = "click" in etiquettes
        return (
            0 if cliquable else 1,
            0 if pur_click else 1,
            sum(jeu.get("baseline_actions", [])),
            len(jeu.get("baseline_actions", [])),
            str(jeu.get("game_id")),
        )

    return sorted(jeux, key=cle)


def _actions_declarees(reponse: Any) -> list[int]:
    """Les commandes que la frame déclare (entiers 0–7, contrat mesuré)."""
    if isinstance(reponse, dict) and isinstance(reponse.get("available_actions"), list):
        return [int(action) for action in reponse["available_actions"]]
    return []


def _ecrire_captures(sonde: Sonde) -> None:
    DOSSIER_EPISODES.mkdir(parents=True, exist_ok=True)
    brut = DOSSIER_EPISODES / "sonde_u22_brut.json"
    brut.write_text(
        json.dumps(sonde.captures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    episode = DOSSIER_EPISODES / "sonde_u22.jsonl"
    lignes = [
        {
            "command": capture["path"].rsplit("/", 1)[-1],
            "request": capture["request"],
            "response": capture["response"],
        }
        for capture in sonde.captures
        if capture["path"].startswith("/api/cmd/") and capture["status"] == 200
    ]
    episode.write_text(
        "".join(json.dumps(ligne, ensure_ascii=False) + "\n" for ligne in lignes),
        encoding="utf-8",
    )
    print(f"capture complète : {brut.relative_to(RACINE)} ({len(sonde.captures)} échanges)")
    print(f"épisode rejouable : {episode.relative_to(RACINE)} ({len(lignes)} commandes)")


def main() -> int:
    config = charger(Mode.LIVE, racine=RACINE)
    if not config.arc_api_key:
        print("ARC_API_KEY absent : la sonde ne peut pas s'authentifier.", file=sys.stderr)
        return 2
    sonde = Sonde(config.arc_base_url, config.arc_api_key)
    print(f"Sonde U22 contre {config.arc_base_url} (scorecard étiqueté {ETIQUETTES_SONDE})")

    try:
        statut, jeux = sonde.appeler("GET", "/api/games", None)
        if statut != 200 or not isinstance(jeux, list):
            print(f"listing des jeux impossible (HTTP {statut}) : arrêt.", file=sys.stderr)
            return 1

        statut, ouverture = sonde.appeler("POST", "/api/scorecard/open", {"tags": ETIQUETTES_SONDE})
        card_id = ouverture.get("card_id") if isinstance(ouverture, dict) else None
        if statut != 200 or not card_id:
            print(f"ouverture du scorecard refusée (HTTP {statut}) : arrêt.", file=sys.stderr)
            return 1

        # RESET : les candidats dans l'ordre, car le backend de jeu ne sert pas
        # tous les jeux listés — chaque refus est capturé et fait partie de la mesure.
        frame: Any = None
        jeu_retenu: dict[str, Any] | None = None
        for jeu in _candidats(jeux)[:JEUX_CANDIDATS_MAX]:
            statut, frame = sonde.appeler(
                "POST",
                "/api/cmd/RESET",
                {"game_id": jeu["game_id"], "card_id": card_id},
            )
            if statut == 200 and isinstance(frame, dict) and frame.get("guid"):
                jeu_retenu = jeu
                break
        if jeu_retenu is None:
            print("aucun candidat jouable : refus capturés, arrêt.", file=sys.stderr)
            return 1
        guid = str(frame["guid"])
        game_id = str(jeu_retenu["game_id"])
        print(
            f"  jeu retenu : {game_id} {jeu_retenu.get('tags')} "
            f"baselines={jeu_retenu.get('baseline_actions')} guid={guid}"
        )

        # Quelques actions simples, prises parmi ce que la frame déclare.
        for _ in range(ACTIONS_SIMPLES_MAX):
            declarees = _actions_declarees(frame)
            simple = next((n for n in (1, 2, 3, 4, 5, 7) if n in declarees), None)
            if simple is None:
                break
            statut, frame = sonde.appeler(
                "POST", f"/api/cmd/ACTION{simple}", {"game_id": game_id, "guid": guid}
            )
            if statut != 200:
                break

        # ACTION6 : mesure de la convention de coordonnées (§A4.2). D'abord la
        # convention du client avant U22 (row/col), puis x/y — le refus mesuré
        # de la première fait partie de la capture.
        statut, reponse6 = sonde.appeler(
            "POST",
            "/api/cmd/ACTION6",
            {"game_id": game_id, "guid": guid, "row": 32, "col": 32},
        )
        if statut != 200:
            sonde.appeler(
                "POST",
                "/api/cmd/ACTION6",
                {"game_id": game_id, "guid": guid, "x": 32, "y": 32},
            )

        sonde.appeler("POST", "/api/scorecard/close", {"card_id": card_id})
        sonde.appeler("GET", f"/api/scorecard/{card_id}", None)
        print(f"scorecard de sonde : {card_id}")
        return 0
    finally:
        _ecrire_captures(sonde)


if __name__ == "__main__":
    sys.exit(main())
