"""Générateur déterministe des cassettes de scénario E2E (`make seed-e2e`).

@spec docs/BACKLOG.md U21
@spec docs/SPEC_ARCAGI3.md §A8.5 (capture en deux passes, régénération identique)
@spec docs/SPEC_HARNAIS.md §H4.7 (enveloppe réelle, appariement par empreinte)

Capture en deux passes : la campagne joue d'abord avec un transport injecté qui
répond selon la politique scriptée et relève les corps exacts émis ; la cassette
apparie ensuite ces corps aux mêmes réponses. Le générateur s'auto-contrôle deux
fois : le scénario aboutit bien à l'issue attendue, et deux générations complètes
produisent le même contenu octet à octet (horodatage fixe).
"""

from __future__ import annotations

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
from tests.e2e.scenarios import DOSSIER_CASSETTES, JEU, SCENARIOS, Scenario, gabarit_reponse, repondre

#: Horodatage fixe : la régénération est identique octet à octet (§A8.5).
HORODATAGE = "2026-08-30T00:00:00+00:00"

#: Plafonds de la capture, identiques à ceux de la CLI E2E (§A8.5).
PLAFONDS = Plafonds(actions_niveau=100, actions_jeu=200, tours_max=120)


def _capturer_corps(scenario: Scenario, gabarit: dict[str, Any]) -> list[dict[str, Any]]:
    """Première passe : joue la campagne et relève les corps réellement émis."""
    serveur: ThreadingHTTPServer = creer_serveur_arc(port=0, niveaux=3)
    hote, port = serveur.server_address[0], serveur.server_address[1]
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    try:
        environnement = scenario.environnement(
            hote_llm="http://capture.invalide", base_arc=f"http://{hote!s}:{port}"
        )
        config = charger(Mode.REJEU, env=environnement, racine=Path("/inexistant"))

        corps_emis: list[dict[str, Any]] = []
        rang = 0

        def transport(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
            nonlocal rang
            charge = json.loads(corps)
            corps_emis.append(charge)
            reponse, avance = repondre(gabarit, charge, rang, scenario)
            if avance:
                rang += 1
            return ReponseHTTP(200, json.dumps(reponse).encode())

        with tempfile.TemporaryDirectory() as dossier:
            resultat = executer_campagne(
                config,
                Workspace.ouvrir(config, f"capture-{scenario.nom}", racine=Path(dossier)),
                PLAFONDS,
                jeux=[JEU],
                client_llm=LLMClient(config, transport=transport, dormir=lambda _: None),
            )
        jeu = resultat.jeux[0]
        if jeu.niveaux_completes != 3 or jeu.actions != scenario.actions_attendues:
            raise AssertionError(
                f"scénario « {scenario.nom} » : attendu 3 niveaux en "
                f"{scenario.actions_attendues} actions, obtenu {jeu.niveaux_completes} "
                f"niveaux en {jeu.actions} actions"
            )
        return corps_emis
    finally:
        serveur.shutdown()
        serveur.server_close()
        fil.join(timeout=5)


def _cassette(scenario: Scenario, gabarit: dict[str, Any], corps: list[dict[str, Any]]) -> str:
    """Seconde passe : apparie chaque corps émis à la réponse de la politique."""
    cassette = Cassette()
    rang = 0
    for charge in corps:
        reponse, avance = repondre(gabarit, charge, rang, scenario)
        if avance:
            rang += 1
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


def generer(scenario: Scenario) -> str:
    """Génère deux fois, compare, et rend le contenu unique du scénario."""
    gabarit = gabarit_reponse()
    premiere = _cassette(scenario, gabarit, _capturer_corps(scenario, gabarit))
    seconde = _cassette(scenario, gabarit, _capturer_corps(scenario, gabarit))
    if premiere != seconde:
        raise AssertionError(
            f"scénario « {scenario.nom} » : deux générations diffèrent — le décor "
            "n'est pas déterministe, la cassette ne peut pas être seedée (§A8.5)"
        )
    return premiere


def main() -> int:
    for scenario in SCENARIOS:
        contenu = generer(scenario)
        chemin = DOSSIER_CASSETTES / scenario.cassette
        chemin.write_text(contenu, encoding="utf-8")
        print(f"  {scenario.cassette} : {contenu.count(chr(10))} échanges, régénération vérifiée")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
