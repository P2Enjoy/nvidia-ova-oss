"""Remise du message `[SUPERVISEUR]` en mode `state` : une fois, au pas suivant.

@verifies docs/BACKLOG.md U35 — remise par mode (préalable mesuré le 2026-09-14 :
          l'injection dans le seul transcript rendait l'intervention invisible
          pour l'acteur en mode `state`)
@verifies docs/SPEC_HARNAIS.md §H10.3 (remise une-fois en tête du pas suivant,
          jamais ré-émise ; le transcript archivé porte aussi le message),
          §H10.4 (proposition jointe remise avec le message ; métrique
          `sonde_fraiche` de l'événement `superviseur`), §H15.7 (articulation)

Aucun réseau : client au transport scripté, environnement factice immobile qui
fait stagner la trajectoire jusqu'à l'intervention.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from avo.config import Config, Mode, charger
from avo.context.contexte import Contexte
from avo.context.etat import LISTE_CHAINES, ChampEtat, SchemaEtat
from avo.llm.client import LLMClient, ReponseHTTP
from avo.loop.boucle import BoucleAgent
from avo.loop.etats import Evenement
from avo.memory.notes import Notes
from avo.memory.workspace import Workspace
from avo.supervisor import BALISE, INTITULE_SONDE, Superviseur
from avo.tools.registre import Outil, RegistreOutils

_SCHEMA = SchemaEtat("test-remise-v1", (ChampEtat("hypotheses", LISTE_CHAINES, "acquis"),))


def _config(**env: str) -> Config:
    return charger(
        Mode.REJEU,
        env={
            "OLLAMA_HOST": "http://capture.invalide",
            "OLLAMA_API_KEY": "sk-cle-remise",
            "AVO_CONTEXT_MODE": "state",
            "AVO_GARDES": "false",
            "AVO_SUP_STALL_ACTIONS": "3",
            "AVO_SUP_COOLDOWN": "50",
            **env,
        },
        racine=Path("/inexistant"),
    )


@dataclass
class _Issue:
    observation: str
    evenement: Evenement
    refusee: bool = False


class _EnvironnementImmobile:
    """L'observation ne change jamais : la stagnation s'installe d'elle-même."""

    def __init__(self) -> None:
        self.jouees = 0
        self._derniere: _Issue | None = None

    def observation(self) -> str:
        return "observation-fixe"

    def actions_disponibles(self) -> list[str]:
        return ["avance"]

    def derniere_issue(self) -> _Issue | None:
        return self._derniere

    def etat_terminal(self) -> str | None:
        return None

    def jouer(self) -> str:
        self.jouees += 1
        self._derniere = _Issue("action jouée.", Evenement.PREDICTION_CONFIRMEE)
        return self._derniere.observation


def _pas() -> dict[str, Any]:
    bloc = json.dumps({"state_patch": {"hypotheses": ["h"]}, "action": "avance"})
    return {
        "message": {"role": "assistant", "content": f"```json\n{bloc}\n```"},
        "done_reason": "stop",
        "prompt_eval_count": 10,
        "eval_count": 5,
        "total_duration": 1_000_000,
    }


class TestRemiseSuperviseurEnModeState(unittest.TestCase):
    """§H10.3 : le message atteint l'acteur au pas suivant, une seule fois."""

    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        self.addCleanup(self._dossier.cleanup)

    def _executer(self, tours: int, **env: str) -> tuple[BoucleAgent, list[dict[str, Any]], Any]:
        corps_emis: list[dict[str, Any]] = []

        def transport(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
            corps_emis.append(json.loads(corps))
            return ReponseHTTP(200, json.dumps(_pas()).encode())

        config = _config(**env)
        environnement = _EnvironnementImmobile()
        registre = RegistreOutils(
            [
                Outil(
                    nom="avance",
                    description="Joue une action d'environnement.",
                    parametres={"type": "object", "properties": {}},
                    fonction=environnement.jouer,
                    etiquettes=frozenset({"action"}),
                )
            ]
        )
        workspace = Workspace.ouvrir(config, "remise", racine=self.racine)
        client = LLMClient(config, transport=transport, dormir=lambda _: None)
        boucle = BoucleAgent(
            config,
            client,
            registre,
            environnement,
            Notes(workspace.notes),
            contexte=Contexte(config=config, systeme="ÉNONCÉ DE LA TÂCHE", schema_etat=_SCHEMA),
            workspace=workspace,
            superviseur=Superviseur(config, client),
        )
        boucle.executer(tours)
        return boucle, corps_emis, workspace

    @staticmethod
    def _pas_porteurs(corps_emis: list[dict[str, Any]]) -> list[int]:
        return [
            index
            for index, corps in enumerate(corps_emis)
            if corps["messages"][0]["content"].startswith("ÉNONCÉ")
            and any(BALISE in message["content"] for message in corps["messages"])
        ]

    def test_le_message_est_remis_une_fois_au_pas_suivant(self) -> None:
        boucle, corps_emis, _ = self._executer(6)
        self.assertEqual(boucle.bilan.interventions, 1)
        porteurs = self._pas_porteurs(corps_emis)
        self.assertEqual(len(porteurs), 1, "le message se remet UNE fois, jamais ré-émis")
        contenu = corps_emis[porteurs[0]]["messages"][1]["content"]
        self.assertTrue(contenu.startswith(BALISE), "remise en tête du pas suivant")
        self.assertIn(INTITULE_SONDE, contenu, "la proposition de la sonde est jointe (§H10.4)")

    def test_la_sonde_recoit_l_enonce_sans_l_etat_ni_les_notes(self) -> None:
        """§H10.4 : le contexte de la sonde se réduit à l'énoncé et l'observation."""
        _, corps_emis, _ = self._executer(5)
        sondes = [
            corps
            for corps in corps_emis
            if "Aucun travail antérieur" in corps["messages"][0]["content"]
        ]
        self.assertEqual(len(sondes), 1)
        corps_texte = json.dumps(sondes[0], ensure_ascii=False)
        self.assertIn("ÉNONCÉ DE LA TÂCHE", corps_texte)
        # La dernière observation est celle de l'issue de l'action qui a déclenché
        # l'intervention — la même que celle passée au diagnostic (§H10.3).
        self.assertIn("action jouée.", corps_texte)
        self.assertNotIn("GUIDE", corps_texte)
        self.assertNotIn("state_patch", corps_texte)
        self.assertNotIn("stagnation", corps_texte)

    def test_le_transcript_archive_porte_aussi_le_message(self) -> None:
        """§H10.3 : la trace d'exécution reste complète (§H11.3)."""
        boucle, _, _ = self._executer(5)
        contenu = json.dumps(boucle.contexte.transcript.pour_api(), ensure_ascii=False)
        self.assertIn(BALISE, contenu)

    def test_la_metrique_superviseur_porte_sonde_fraiche(self) -> None:
        _, _, workspace = self._executer(5)
        evenements = [
            ligne for ligne in workspace.lire_metriques() if ligne.get("type") == "superviseur"
        ]
        self.assertEqual(len(evenements), 1)
        self.assertTrue(evenements[0]["sonde_fraiche"])

    def test_l_interrupteur_coupe_la_jonction_sans_couper_la_remise(self) -> None:
        """§H10.4 : sonde à `false`, l'intervention se remet comme avant, sans elle."""
        boucle, corps_emis, workspace = self._executer(5, AVO_SUP_SONDE_FRAICHE="false")
        self.assertEqual(boucle.bilan.interventions, 1)
        self.assertFalse(
            any(
                "Aucun travail antérieur" in corps["messages"][0]["content"] for corps in corps_emis
            ),
            "aucun appel de sonde ne part quand l'interrupteur est à false",
        )
        porteurs = self._pas_porteurs(corps_emis)
        self.assertEqual(len(porteurs), 1)
        self.assertNotIn(INTITULE_SONDE, corps_emis[porteurs[0]]["messages"][1]["content"])
        evenements = [
            ligne for ligne in workspace.lire_metriques() if ligne.get("type") == "superviseur"
        ]
        self.assertFalse(evenements[0]["sonde_fraiche"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
