"""Générateur déterministe des cassettes E2E des bancs (Entrepôt, Dépôt, CTF).

@verifies docs/BACKLOG.md U29a2 — adaptateur harnais + CLI `banc` ; U29a4 —
          branchement du Dépôt logiciel (cassette E2E du dépôt) ; U29b2 —
          cassette E2E du banc CTF
@verifies docs/SPEC_BANCS.md §S6.4 (E2E : scénario rejoué par cassette, épisode
          court, score attendu exact), §S12.5 (E2E du banc b : capture
          attendue), §S1.4 (déterminisme : double génération comparée)
@verifies docs/SPEC_ARCAGI3.md §A8.5 (capture en deux passes, régénération
          identique octet à octet)

Même principe que `generer_cassette_etat.py` : une première passe capture les
corps réellement émis par la boucle complète sous gardes (transport scripté), la
seconde apparie chaque corps à la réponse de la politique parfaite. L'enveloppe
de réponse est celle réellement enregistrée sur le vrai endpoint (§H4.7).
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from avo.bancs.ctf.adaptateur import EXECUTEUR_PROCESSUS, jouer_episode_ctf
from avo.bancs.ctf.defis import generer_defi
from avo.bancs.skillexec.adaptateur import jouer_episode
from avo.bancs.skillexec.depot import generer_episode_depot
from avo.bancs.skillexec.generation import generer_episode
from avo.config import Mode, charger
from avo.llm.client import LLMClient, ReponseHTTP
from avo.memory.workspace import Workspace
from llm_replay.cassette import AUTH_VALIDE, Cassette, Exchange, RequestRecord, ResponseRecord
from tests.e2e.scenarios_banc import (
    ENV_EPINGLE_BANC,
    HYPOTHESE_CTF,
    HYPOTHESE_DEPOT,
    JETON,
    actions_parfaites,
    actions_parfaites_ctf,
    actions_parfaites_depot,
    gabarit_reponse,
    reponse_pas,
)

#: Horodatage fixe : la régénération est identique octet à octet (§A8.5).
HORODATAGE = "2026-09-01T00:00:00+00:00"

DOSSIER_CASSETTES = Path("tests/fixtures/llm/cassettes")

#: Hypothèse par défaut des pas de l'Entrepôt — celle du décor (`contenu_pas`).
HYPOTHESE_ENTREPOT = "je tiens l'état exact de l'entrepôt"


@dataclass(frozen=True)
class ScenarioBanc:
    """Un scénario E2E du banc : environnement, épisode court, jeu parfait (§S6.4)."""

    environnement: str
    cassette: str
    seed: int
    horizon: int
    hypothese: str

    def actions(self) -> list[str]:
        if self.environnement == "entrepot":
            return actions_parfaites(generer_episode(self.seed, self.horizon))
        return actions_parfaites_depot(generer_episode_depot(self.seed, self.horizon))


#: Paramètres des scénarios (§S2.2) — courts, score attendu exact 1.00. Le dépôt
#: couvre les quatre types d'événements et DEUX demandes jugées (seed 6, relevé
#: du générateur), résolution attendue 1.0.
SCENARIO_ENTREPOT = ScenarioBanc("entrepot", "e2e_banc_entrepot.jsonl", 42, 6, HYPOTHESE_ENTREPOT)
SCENARIO_DEPOT = ScenarioBanc("depot", "e2e_banc_depot.jsonl", 6, 8, HYPOTHESE_DEPOT)
SCENARIOS = (SCENARIO_ENTREPOT, SCENARIO_DEPOT)

#: Compatibilité de lecture pour les preuves de l'Entrepôt (U29a2).
CASSETTE_NOM = SCENARIO_ENTREPOT.cassette
SEED = SCENARIO_ENTREPOT.seed
HORIZON = SCENARIO_ENTREPOT.horizon


@dataclass(frozen=True)
class ScenarioCtf:
    """Le scénario E2E du banc b (§S12.5) : famille `fouille`, capture en deux
    actions par le recouvrement canonique — exécuteur `processus` (§S10.3 :
    réservé aux preuves et au rejeu ; les suites tournent déjà en conteneur)."""

    cassette: str
    seed: int
    horizon: int

    def actions(self) -> list[str]:
        return actions_parfaites_ctf(generer_defi(self.seed, "fouille"))


SCENARIO_CTF = ScenarioCtf("e2e_banc_ctf.jsonl", 5, 4)


def _capturer_corps_ctf(gabarit: dict[str, Any]) -> list[dict[str, Any]]:
    """Première passe du banc b : joue le défi et relève les corps émis."""
    actions = SCENARIO_CTF.actions()
    corps_emis: list[dict[str, Any]] = []

    def transport(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
        corps_emis.append(json.loads(corps))
        reponse = reponse_pas(gabarit, actions[len(corps_emis) - 1], HYPOTHESE_CTF)
        return ReponseHTTP(200, json.dumps(reponse).encode())

    environnement = {
        **ENV_EPINGLE_BANC,
        "OLLAMA_HOST": "http://capture.invalide",
        "OLLAMA_API_KEY": JETON,
    }
    config = charger(Mode.REJEU, env=environnement, racine=Path("/inexistant"))
    with tempfile.TemporaryDirectory() as dossier:
        espace = Workspace.ouvrir(config, "capture-banc-ctf", racine=Path(dossier))
        releve = jouer_episode_ctf(
            config,
            espace,
            seed=SCENARIO_CTF.seed,
            horizon=SCENARIO_CTF.horizon,
            famille="fouille",
            executeur=EXECUTEUR_PROCESSUS,
            client_llm=LLMClient(config, transport=transport, dormir=lambda _: None),
        )
    if not releve.reussi or releve.actions != len(actions):
        raise AssertionError(
            f"scénario banc (ctf) : capture attendue en {len(actions)} actions, "
            f"obtenu reussi={releve.reussi} en {releve.actions} actions"
        )
    return corps_emis


def _cassette_ctf(gabarit: dict[str, Any], corps_emis: list[dict[str, Any]]) -> str:
    """Seconde passe du banc b : apparie chaque corps à la réponse scriptée."""
    actions = SCENARIO_CTF.actions()
    cassette = Cassette()
    for rang, corps in enumerate(corps_emis):
        cassette.ajouter(
            Exchange(
                request=RequestRecord.depuis("POST", "/api/chat", AUTH_VALIDE, corps),
                response=ResponseRecord(
                    status=200,
                    headers={"content-type": "application/json"},
                    body=reponse_pas(gabarit, actions[rang], HYPOTHESE_CTF),
                ),
                recorded_at=HORODATAGE,
                duration_ms=1,
            )
        )
    return "".join(json.dumps(echange.en_json(), ensure_ascii=False) + "\n" for echange in cassette)


def generer_ctf() -> str:
    """Génère deux fois la cassette du banc b, compare, rend le contenu (§A8.5)."""
    gabarit = gabarit_reponse()
    premiere = _cassette_ctf(gabarit, _capturer_corps_ctf(gabarit))
    seconde = _cassette_ctf(gabarit, _capturer_corps_ctf(gabarit))
    if premiere != seconde:
        raise AssertionError(
            "scénario banc (ctf) : deux générations diffèrent — le décor n'est "
            "pas déterministe, la cassette ne peut pas être seedée (§A8.5, §S1.4)"
        )
    return premiere


def _capturer_corps(scenario: ScenarioBanc, gabarit: dict[str, Any]) -> list[dict[str, Any]]:
    """Première passe : joue l'épisode et relève les corps réellement émis."""
    actions = scenario.actions()
    corps_emis: list[dict[str, Any]] = []

    def transport(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
        corps_emis.append(json.loads(corps))
        reponse = reponse_pas(gabarit, actions[len(corps_emis) - 1], scenario.hypothese)
        return ReponseHTTP(200, json.dumps(reponse).encode())

    environnement = {
        **ENV_EPINGLE_BANC,
        "OLLAMA_HOST": "http://capture.invalide",
        "OLLAMA_API_KEY": JETON,
    }
    config = charger(Mode.REJEU, env=environnement, racine=Path("/inexistant"))
    with tempfile.TemporaryDirectory() as dossier:
        espace = Workspace.ouvrir(config, "capture-banc", racine=Path(dossier))
        releve = jouer_episode(
            config,
            espace,
            seed=scenario.seed,
            horizon=scenario.horizon,
            client_llm=LLMClient(config, transport=transport, dormir=lambda _: None),
            environnement=scenario.environnement,
        )
    if releve.score != 1.0 or releve.correctes != scenario.horizon:
        raise AssertionError(
            f"scénario banc ({scenario.environnement}) : attendu "
            f"{scenario.horizon}/{scenario.horizon} correctes (score 1.00), "
            f"obtenu {releve.correctes} correctes (score {releve.score:.2f})"
        )
    return corps_emis


def _cassette(
    scenario: ScenarioBanc, gabarit: dict[str, Any], corps_emis: list[dict[str, Any]]
) -> str:
    """Seconde passe : apparie chaque corps émis à la réponse de la politique."""
    actions = scenario.actions()
    cassette = Cassette()
    for rang, corps in enumerate(corps_emis):
        cassette.ajouter(
            Exchange(
                request=RequestRecord.depuis("POST", "/api/chat", AUTH_VALIDE, corps),
                response=ResponseRecord(
                    status=200,
                    headers={"content-type": "application/json"},
                    body=reponse_pas(gabarit, actions[rang], scenario.hypothese),
                ),
                recorded_at=HORODATAGE,
                duration_ms=1,
            )
        )
    return "".join(json.dumps(echange.en_json(), ensure_ascii=False) + "\n" for echange in cassette)


def generer(scenario: ScenarioBanc) -> str:
    """Génère deux fois, compare, et rend le contenu unique du scénario (§A8.5)."""
    gabarit = gabarit_reponse()
    premiere = _cassette(scenario, gabarit, _capturer_corps(scenario, gabarit))
    seconde = _cassette(scenario, gabarit, _capturer_corps(scenario, gabarit))
    if premiere != seconde:
        raise AssertionError(
            f"scénario banc ({scenario.environnement}) : deux générations diffèrent "
            "— le décor n'est pas déterministe, la cassette ne peut pas être "
            "seedée (§A8.5, §S1.4)"
        )
    return premiere


def main() -> int:
    for scenario in SCENARIOS:
        contenu = generer(scenario)
        chemin = DOSSIER_CASSETTES / scenario.cassette
        chemin.write_text(contenu, encoding="utf-8")
        print(f"  {scenario.cassette} : {contenu.count(chr(10))} échanges, régénération vérifiée")
    contenu = generer_ctf()
    chemin = DOSSIER_CASSETTES / SCENARIO_CTF.cassette
    chemin.write_text(contenu, encoding="utf-8")
    print(f"  {SCENARIO_CTF.cassette} : {contenu.count(chr(10))} échanges, régénération vérifiée")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
