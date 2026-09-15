"""Générateur déterministe de la cassette E2E « victoire » du harnais ENRICHI (U37).

@spec docs/BACKLOG.md U37 — A/B en rejeu : harnais enrichi contre harnais nu,
      même mode `state` (patron U27)
@spec docs/SPEC_HARNAIS.md §H18.1 (schéma dérivé `+plan`, protocole engendré),
      §H18.2 (pas d'idéation d'ouverture : premier appel sans action jouée),
      §H18.6 (A/B en rejeu sur cassettes générées)
@spec docs/SPEC_ARCAGI3.md §A8.5 (capture en deux passes, régénération identique)

Même décor et même chemin parfait que `generer_cassette_etat.py` (le harnais nu) ;
seule différence : les mécanismes H18 actifs — le premier appel est le pas
d'idéation (patch : approches dans `hypotheses`, tâches d'amorce dans `plan` ;
action non jouée), puis chaque appel joue une action du chemin parfait. La
curation (§H18.3) reste inactive ici : le chemin parfait ne stagne jamais, le
superviseur n'interviendrait pas — elle est prouvée par ses unitaires.
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
from avo.arc.campagne import executer_campagne
from avo.config import Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP
from avo.memory.workspace import Workspace
from llm_replay.cassette import AUTH_VALIDE, Cassette, Exchange, RequestRecord, ResponseRecord
from tests.e2e.generer_cassette_etat import ACTIONS_ATTENDUES, PLAFONDS, actions_texte
from tests.e2e.scenarios import ENV_EPINGLE, JETON, JEU, gabarit_reponse

#: Horodatage fixe : la régénération est identique octet à octet (§A8.5).
HORODATAGE = "2026-09-15T00:00:00+00:00"

CASSETTE_NOM = "e2e_ledger_victoire.jsonl"
DOSSIER_CASSETTES = Path("tests/fixtures/llm/cassettes")


def _environnement(hote_llm: str, base_arc: str) -> dict[str, str]:
    """L'environnement épinglé, mécanismes H18 ACTIFS (harnais enrichi, §H18.4)."""
    return {
        **ENV_EPINGLE,
        "AVO_CONTEXT_MODE": "state",
        "AVO_NUM_PREDICT": "4096",
        "AVO_PLAN_LEDGER": "true",
        "AVO_IDEATION_OUVERTURE": "true",
        "OLLAMA_HOST": hote_llm,
        "OLLAMA_API_KEY": JETON,
        "ARC_BASE_URL": base_arc,
    }


def _repondre(gabarit: dict[str, Any], rang: int) -> dict[str, Any]:
    """Politique du harnais enrichi : appel 0 = idéation, appel n = action n−1.

    Le pas d'idéation (§H18.2) écrit deux approches distinctes dans `hypotheses`
    et deux tâches d'amorce dans `plan` ; son action n'est pas jouée. Les pas
    suivants satisfont les gardes (§H16) comme dans la cassette du harnais nu,
    avec un patch stable — Σ constant, génération déterministe.
    """
    reponse = copy.deepcopy(gabarit)
    if rang == 0:
        charge: dict[str, Any] = {
            "state_patch": {
                "hypotheses": [
                    "explorer les commandes une à une pour cartographier leurs effets",
                    "chercher d'abord ce que l'observation change entre deux actions",
                ],
                "plan": [
                    {
                        "id": "cartographier",
                        "description": "jouer chaque commande et noter son effet",
                        "statut": "en_cours",
                    },
                    {
                        "id": "terminer-niveau",
                        "description": "exploiter la carte des effets pour finir le niveau",
                        "statut": "a_faire",
                    },
                ],
            },
            "action": "aucune",
        }
        reponse["message"]["content"] = (
            "deux approches réellement distinctes, et leurs premières étapes\n"
            "```json\n" + json.dumps(charge) + "\n```"
        )
    else:
        actions = actions_texte()
        action = actions[min(rang - 1, len(actions) - 1)]
        charge = {
            "state_patch": {"hypotheses": ["les effets des commandes restent à découvrir"]},
            "action": action,
        }
        reponse["message"]["content"] = (
            "je joue la commande prévue par le scénario\n"
            "PREDICTION: je m'attends à un changement visible de la grille\n"
            "VERDICT: confirmee\n"
            "```json\n" + json.dumps(charge) + "\n```"
        )
    reponse["message"].pop("tool_calls", None)
    return reponse


def _capturer_corps(gabarit: dict[str, Any]) -> list[dict[str, Any]]:
    """Première passe : joue la campagne enrichie et relève les corps émis."""
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
                Workspace.ouvrir(config, "capture-ledger-victoire", racine=Path(dossier)),
                PLAFONDS,
                jeux=[JEU],
                client_llm=LLMClient(config, transport=transport, dormir=lambda _: None),
            )
        jeu = resultat.jeux[0]
        if jeu.niveaux_completes != 3 or jeu.actions != ACTIONS_ATTENDUES:
            raise AssertionError(
                f"scénario ledger-victoire : attendu 3 niveaux en {ACTIONS_ATTENDUES} actions, "
                f"obtenu {jeu.niveaux_completes} niveaux en {jeu.actions} actions"
            )
        if jeu.ideations != 1:
            raise AssertionError(
                f"scénario ledger-victoire : attendu 1 pas d'idéation (§H18.2), "
                f"obtenu {jeu.ideations}"
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
            "scénario ledger-victoire : deux générations diffèrent — le décor n'est pas "
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
