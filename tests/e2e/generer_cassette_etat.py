"""Générateur déterministe de la cassette E2E « victoire » du mode `state` (U27).

@spec docs/BACKLOG.md U27 — A/B sur rejeu, mode `state` vs `transcript`
@spec docs/SPEC_HARNAIS.md §H15.0 (le départage se fait par la mesure), §H15.1
      (bloc ```` ```json ```` à deux clés), §H15.8 (un pas = un tour : un appel LLM
      joue exactement une action, sans les phases P/I/E/B du mode `transcript`)
@spec docs/SPEC_ARCAGI3.md §A8.5 (capture en deux passes, régénération identique)

Même principe que `generer_cassettes.py` (mode `transcript`) : une première passe
capture les corps de requête réellement émis contre un rejeu ARC en mémoire, une
seconde passe apparie ces corps à la réponse scriptée. La politique est plus simple
qu'en mode `transcript` : un tour = un appel = une action du chemin parfait, jamais
un constat textuel intermédiaire (§H15.8).
"""

from __future__ import annotations

import copy
import json
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from arc_replay.serveur import creer_serveur as creer_serveur_arc
from avo.arc.campagne import Plafonds, executer_campagne
from avo.config import Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP
from avo.memory.workspace import Workspace
from llm_replay.cassette import AUTH_VALIDE, Cassette, Exchange, RequestRecord, ResponseRecord
from tests.e2e.scenarios import ENV_EPINGLE, JETON, JEU, actions_victoire, gabarit_reponse

#: Horodatage fixe : la régénération est identique octet à octet (§A8.5).
HORODATAGE = "2026-08-30T00:00:00+00:00"

#: Plafonds de la capture, identiques à ceux du scénario `transcript` (§A8.5).
PLAFONDS = Plafonds(actions_niveau=100, actions_jeu=200, tours_max=120)

CASSETTE_NOM = "e2e_etat_victoire.jsonl"
DOSSIER_CASSETTES = Path("tests/fixtures/llm/cassettes")

#: Partie parfaite : mêmes baselines que le scénario `transcript` (§A3.2).
ACTIONS_ATTENDUES = 76
NIVEAUX_ATTENDUS = (39, 19, 18)


def _action_texte(nom: str, arguments: dict[str, Any]) -> str:
    """Forme textuelle du champ `action` (§H15.8) : nom, puis valeurs requises,
    dans l'ordre du schéma de l'outil — ici `row, col` pour `action6` seulement."""
    if not arguments:
        return nom
    valeurs = ", ".join(str(arguments[cle]) for cle in ("row", "col") if cle in arguments)
    return f"{nom} {valeurs}"


def actions_texte() -> tuple[str, ...]:
    """Le chemin parfait du jeu `cible`, traduit en textes d'action du mode `state`."""
    return tuple(_action_texte(nom, arguments) for nom, arguments in actions_victoire())


def _environnement(hote_llm: str, base_arc: str) -> dict[str, str]:
    return {
        **ENV_EPINGLE,
        "AVO_CONTEXT_MODE": "state",
        "AVO_NUM_PREDICT": "4096",
        "OLLAMA_HOST": hote_llm,
        "OLLAMA_API_KEY": JETON,
        "ARC_BASE_URL": base_arc,
    }


def _repondre(gabarit: dict[str, Any], rang: int) -> dict[str, Any]:
    """Un pas = un tour (§H15.8) : le rang de l'appel EST le rang de l'action."""
    reponse = copy.deepcopy(gabarit)
    actions = actions_texte()
    action = actions[min(rang, len(actions) - 1)]
    charge = {"state_patch": {}, "action": action}
    reponse["message"]["content"] = (
        "je joue la commande prévue par le scénario\n```json\n" + json.dumps(charge) + "\n```"
    )
    reponse["message"].pop("tool_calls", None)
    return reponse


def _capturer_corps(gabarit: dict[str, Any]) -> list[dict[str, Any]]:
    """Première passe : joue la campagne et relève les corps réellement émis."""
    serveur: ThreadingHTTPServer = creer_serveur_arc(port=0, niveaux=3)
    hote, port = serveur.server_address[0], serveur.server_address[1]
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    try:
        environnement = _environnement("http://capture.invalide", f"http://{hote!s}:{port}")
        config = charger(Mode.REJEU, env=environnement, racine=Path("/inexistant"))

        corps_emis: list[dict[str, Any]] = []

        def transport(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
            charge = json.loads(corps)
            corps_emis.append(charge)
            reponse = _repondre(gabarit, len(corps_emis) - 1)
            return ReponseHTTP(200, json.dumps(reponse).encode())

        with tempfile.TemporaryDirectory() as dossier:
            resultat = executer_campagne(
                config,
                Workspace.ouvrir(config, "capture-etat-victoire", racine=Path(dossier)),
                PLAFONDS,
                jeux=[JEU],
                client_llm=LLMClient(config, transport=transport, dormir=lambda _: None),
            )
        jeu = resultat.jeux[0]
        if jeu.niveaux_completes != 3 or jeu.actions != ACTIONS_ATTENDUES:
            raise AssertionError(
                f"scénario état-victoire : attendu 3 niveaux en {ACTIONS_ATTENDUES} actions, "
                f"obtenu {jeu.niveaux_completes} niveaux en {jeu.actions} actions"
            )
        return corps_emis
    finally:
        serveur.shutdown()
        serveur.server_close()
        fil.join(timeout=5)


def _cassette(gabarit: dict[str, Any], corps: list[dict[str, Any]]) -> str:
    """Seconde passe : apparie chaque corps émis à la réponse de la politique."""
    cassette = Cassette()
    for rang, charge in enumerate(corps):
        reponse = _repondre(gabarit, rang)
        cassette.ajouter(
            Exchange(
                request=RequestRecord.depuis("POST", "/api/chat", AUTH_VALIDE, charge),
                response=ResponseRecord(
                    status=200, headers={"content-type": "application/json"}, body=reponse
                ),
                recorded_at=HORODATAGE,
                duration_ms=1,
            )
        )
    return "".join(json.dumps(echange.en_json(), ensure_ascii=False) + "\n" for echange in cassette)


def generer() -> str:
    """Génère deux fois, compare, et rend le contenu unique du scénario."""
    gabarit = gabarit_reponse()
    premiere = _cassette(gabarit, _capturer_corps(gabarit))
    seconde = _cassette(gabarit, _capturer_corps(gabarit))
    if premiere != seconde:
        raise AssertionError(
            "scénario état-victoire : deux générations diffèrent — le décor n'est pas "
            "déterministe, la cassette ne peut pas être seedée (§A8.5)"
        )
    return premiere


def main() -> int:
    contenu = generer()
    chemin = DOSSIER_CASSETTES / CASSETTE_NOM
    chemin.write_text(contenu, encoding="utf-8")
    print(f"  {CASSETTE_NOM} : {contenu.count(chr(10))} échanges, régénération vérifiée")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
