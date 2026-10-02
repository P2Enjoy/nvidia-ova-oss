"""Le détecteur de cycle du superviseur juge l'état observable, pas la comptabilité.

@verifies docs/BACKLOG.md U31 — trajectoire du superviseur sur l'empreinte
          d'observation (mesuré le 2026-10-02 : détecteur de cycle structurellement
          muet, zéro déclenchement sur tous les rapports de campagne)
@verifies docs/SPEC_HARNAIS.md §H10.2 (« sans changement de frame » : empreinte
          d'observation de l'environnement quand elle est déclarée, observation
          rendue sinon), §H11.2 (même contenu que la mesure de non-progrès)

Aucun réseau : client au transport scripté. L'environnement rend une observation
dont un compteur de présentation change à chaque action, sous une frame qui ne
bouge jamais — exactement la ligne d'état ARC (§A4.1), sans en nommer le jeu.
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
from avo.supervisor import FENETRE_CYCLE, Superviseur
from avo.tools.registre import Outil, RegistreOutils

_SCHEMA = SchemaEtat("test-cycle-v1", (ChampEtat("hypotheses", LISTE_CHAINES, "acquis"),))


def _config() -> Config:
    # Le seuil de stagnation est placé hors de portée : seul le détecteur de cycle
    # (fenêtre fixe §H10.2) peut faire intervenir le superviseur dans ces tours.
    return charger(
        Mode.REJEU,
        env={
            "OLLAMA_HOST": "http://capture.invalide",
            "OLLAMA_API_KEY": "sk-cle-cycle",
            "AVO_CONTEXT_MODE": "state",
            "AVO_GARDES": "false",
            "AVO_SUP_STALL_ACTIONS": "1000",
            "AVO_SUP_COOLDOWN": "1000",
            "AVO_SUP_SONDE_FRAICHE": "false",
        },
        racine=Path("/inexistant"),
    )


@dataclass
class _Issue:
    observation: str
    evenement: Evenement
    refusee: bool = False


class _EnvironnementCompteur:
    """Frame immobile, observation qui porte un compteur de présentation."""

    def __init__(self) -> None:
        self.jouees = 0
        self._derniere: _Issue | None = None

    def observation(self) -> str:
        return f"frame-fixe\nactions_niveau={self.jouees}"

    def actions_disponibles(self) -> list[str]:
        return ["avance"]

    def derniere_issue(self) -> _Issue | None:
        return self._derniere

    def etat_terminal(self) -> str | None:
        return None

    def jouer(self) -> str:
        self.jouees += 1
        self._derniere = _Issue(self.observation(), Evenement.PREDICTION_CONFIRMEE)
        return self._derniere.observation


class _EnvironnementCompteurAvecEmpreinte(_EnvironnementCompteur):
    """Même environnement, qui déclare l'état observable sans son compteur (§H11.2)."""

    def empreinte_observation(self) -> str:
        return "frame-fixe"


# Le premier pas d'un run est l'idéation d'ouverture (§H18.2), sans action jouée :
# il faut FENETRE_CYCLE + 1 tours pour remplir la fenêtre du détecteur.
TOURS_FENETRE = FENETRE_CYCLE + 1


def _pas() -> dict[str, Any]:
    bloc = json.dumps({"state_patch": {"hypotheses": ["h"]}, "action": "avance"})
    return {
        "message": {"role": "assistant", "content": f"```json\n{bloc}\n```"},
        "done_reason": "stop",
        "prompt_eval_count": 10,
        "eval_count": 5,
        "total_duration": 1_000_000,
    }


class TestCycleSurEmpreinte(unittest.TestCase):
    """§H10.2 : le cycle se détecte sur l'empreinte, jamais sur le compteur."""

    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)
        self.addCleanup(self._dossier.cleanup)

    def _executer(
        self, environnement: _EnvironnementCompteur, tours: int
    ) -> tuple[BoucleAgent, Any]:
        def transport(url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
            return ReponseHTTP(200, json.dumps(_pas()).encode())

        config = _config()
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
        workspace = Workspace.ouvrir(config, "cycle", racine=self.racine)
        client = LLMClient(config, transport=transport, dormir=lambda _: None)
        boucle = BoucleAgent(
            config,
            client,
            registre,
            environnement,
            Notes(workspace.notes),
            contexte=Contexte(config=config, systeme="ÉNONCÉ", schema_etat=_SCHEMA),
            workspace=workspace,
            superviseur=Superviseur(config, client),
        )
        boucle.executer(tours)
        return boucle, workspace

    def test_avec_empreinte_le_cycle_se_declenche_malgre_le_compteur(self) -> None:
        boucle, workspace = self._executer(_EnvironnementCompteurAvecEmpreinte(), TOURS_FENETRE)
        self.assertEqual(boucle.bilan.interventions, 1)
        evenements = [
            ligne for ligne in workspace.lire_metriques() if ligne.get("type") == "superviseur"
        ]
        self.assertEqual(len(evenements), 1)
        self.assertIn("cycle improductif", evenements[0]["motif"])
        self.assertIn("avance", evenements[0]["motif"])

    def test_la_trajectoire_porte_une_empreinte_constante(self) -> None:
        """Les frames identiques ont la même empreinte, quel que soit le compteur."""
        boucle, _ = self._executer(_EnvironnementCompteurAvecEmpreinte(), 4)
        assert boucle.superviseur is not None
        empreintes = {pas.empreinte for pas in boucle.superviseur.trajectoire.pas}
        self.assertEqual(len(boucle.superviseur.trajectoire.pas), 3)
        self.assertEqual(len(empreintes), 1)

    def test_sans_empreinte_l_observation_rendue_fait_foi(self) -> None:
        """Comportement inchangé pour un environnement qui ne déclare rien :
        l'observation rendue, compteur compris, reste la base de comparaison."""
        boucle, _ = self._executer(_EnvironnementCompteur(), TOURS_FENETRE)
        self.assertEqual(boucle.bilan.interventions, 0)
        assert boucle.superviseur is not None
        empreintes = {pas.empreinte for pas in boucle.superviseur.trajectoire.pas}
        self.assertEqual(len(empreintes), FENETRE_CYCLE)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
