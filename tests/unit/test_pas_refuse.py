"""Action refusée par l'environnement = patch annulé (mode `state`).

@verifies docs/BACKLOG.md U31 — amélioration générique sur mesures (journal
          2026-09-02, suite 24 : 9 des 10 refus du seed 1 portaient un patch
          inscrivant l'effet d'une action refusée, chaque faux fait causant
          l'erreur suivante)
@verifies docs/SPEC_HARNAIS.md §H15.8 (drapeau `refusee` de l'issue : patch du
          pas annulé, Σ et workspace revenus à l'avant-pas, archive `patch_annule`,
          environnement sans drapeau inchangé ; protocole engendré énonçant la
          règle), §H15.10 (archive des pas)
@verifies docs/SPEC_BANCS.md §S6.1 (l'adaptateur expose `refusee = not valide`)

Aucun réseau : client au transport scripté (forme des corps §H4.3), environnement
factice qui déclare — ou non — le drapeau `refusee`.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from avo.bancs.skillexec.adaptateur import EnvironnementBancEntrepot
from avo.bancs.skillexec.entrepot import EnvironnementEntrepot
from avo.bancs.skillexec.generation import generer_episode
from avo.config import Config, Mode, charger
from avo.context.contexte import Contexte
from avo.context.etat import LISTE_CHAINES, POSITION, ChampEtat, SchemaEtat
from avo.llm.client import LLMClient, ReponseHTTP
from avo.loop import prompts
from avo.loop.boucle import BoucleAgent
from avo.loop.etats import Evenement
from avo.memory.notes import Notes
from avo.memory.workspace import Workspace
from avo.tools.registre import Outil, RegistreOutils


def _config(**env: str) -> Config:
    return charger(
        Mode.REJEU,
        env={
            "OLLAMA_HOST": "http://capture.invalide",
            "OLLAMA_API_KEY": "sk-cle-pas-refuse",
            "AVO_CONTEXT_MODE": "state",
            "AVO_GARDES": "false",
            **env,
        },
        racine=Path("/inexistant"),
    )


@dataclass
class _IssueRefusable:
    observation: str
    evenement: Evenement
    refusee: bool = False


@dataclass
class _IssueSansDrapeau:
    """Contrat minimal d'avant §H15.8 : aucun attribut `refusee` déclaré."""

    observation: str
    evenement: Evenement


class _EnvironnementRefusant:
    """Environnement factice : refuse les actions selon un scénario, sans jeu."""

    def __init__(self, refus: list[bool], avec_drapeau: bool = True) -> None:
        self.refus = list(refus)
        self.avec_drapeau = avec_drapeau
        self.jouees: list[str] = []
        self._derniere: Any = None

    def observation(self) -> str:
        return f"observation-{len(self.jouees)}"

    def actions_disponibles(self) -> list[str]:
        return ["avance"]

    def derniere_issue(self) -> Any:
        return self._derniere

    def etat_terminal(self) -> str | None:
        return None

    def jouer(self) -> str:
        self.jouees.append("avance")
        refusee = self.refus[min(len(self.jouees) - 1, len(self.refus) - 1)]
        texte = "error: action refusée." if refusee else "action jouée."
        if self.avec_drapeau:
            self._derniere = _IssueRefusable(texte, Evenement.PREDICTION_CONFIRMEE, refusee)
        else:
            self._derniere = _IssueSansDrapeau(texte, Evenement.PREDICTION_CONFIRMEE)
        return texte


class _TransportScripte:
    def __init__(self, reponses: list[dict[str, Any]]) -> None:
        self.reponses = list(reponses)

    def __call__(self, url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
        if not self.reponses:
            raise AssertionError("plus de réponse scriptée : appel LLM de trop")
        return ReponseHTTP(200, json.dumps(self.reponses.pop(0)).encode())


def _pas(patch: dict[str, Any], action: str = "avance") -> dict[str, Any]:
    bloc = json.dumps({"state_patch": patch, "action": action})
    return {
        "message": {"role": "assistant", "content": f"```json\n{bloc}\n```"},
        "done_reason": "stop",
        "prompt_eval_count": 10,
        "eval_count": 5,
        "total_duration": 1_000_000,
    }


#: Schéma minimal : le champ commun plus un champ dont on suit la valeur.
_SCHEMA = SchemaEtat(
    "test-refus-v1",
    (
        ChampEtat("hypotheses", LISTE_CHAINES, "ce que tu tiens pour vrai"),
        ChampEtat("position", POSITION, "où tu en es"),
    ),
)


class TestPatchAnnuleSousActionRefusee(unittest.TestCase):
    """§H15.8 : le patch d'un pas dont l'action est refusée n'atteint pas Σ."""

    def setUp(self) -> None:
        self._dossier = tempfile.TemporaryDirectory()
        self.racine = Path(self._dossier.name)

    def tearDown(self) -> None:
        self._dossier.cleanup()

    def _boucle(
        self, environnement: _EnvironnementRefusant, reponses: list[dict[str, Any]]
    ) -> tuple[BoucleAgent, Workspace]:
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
        workspace = Workspace.ouvrir(config, "run-test", racine=self.racine)
        client = LLMClient(config, transport=_TransportScripte(reponses), dormir=lambda _: None)
        contexte = Contexte(config=config, systeme=prompts.SYSTEME, schema_etat=_SCHEMA)
        boucle = BoucleAgent(
            config,
            client,
            registre,
            environnement,
            Notes(self.racine / "notes"),
            contexte=contexte,
            workspace=workspace,
        )
        return boucle, workspace

    def _pas_archives(self, workspace: Workspace) -> list[dict[str, Any]]:
        chemin = workspace.chemin / "state" / "pas.jsonl"
        return [json.loads(ligne) for ligne in chemin.read_text().splitlines()]

    def test_le_patch_d_une_action_refusee_est_annule(self) -> None:
        environnement = _EnvironnementRefusant(refus=[True])
        boucle, workspace = self._boucle(
            environnement,
            [_pas({"hypotheses": ["h"], "position": {"x": 3, "y": 4}})],
        )
        tour = boucle.jouer_tour(1)
        self.assertEqual(tour.action, "avance", "l'action est jouée : l'événement se consomme")
        assert boucle.etat is not None
        self.assertIsNone(
            boucle.etat.champs["position"],
            "le patch de l'action refusée n'atteint pas Σ (§H15.8)",
        )
        etat_disque = json.loads((workspace.chemin / "state" / "etat.json").read_text())
        self.assertIsNone(etat_disque["position"], "le workspace revient à l'avant-pas")
        annulations = [p for p in self._pas_archives(workspace) if p.get("patch_annule")]
        self.assertEqual(len(annulations), 1, "l'archive porte l'annulation (§H15.10)")
        self.assertEqual(annulations[0]["patch"]["position"], {"x": 3, "y": 4})

    def test_le_patch_d_une_action_acceptee_est_conserve(self) -> None:
        environnement = _EnvironnementRefusant(refus=[False])
        boucle, workspace = self._boucle(
            environnement,
            [_pas({"hypotheses": ["h"], "position": {"x": 1, "y": 2}})],
        )
        boucle.jouer_tour(1)
        assert boucle.etat is not None
        self.assertEqual(dict(boucle.etat.champs["position"]), {"x": 1, "y": 2})
        annulations = [p for p in self._pas_archives(workspace) if p.get("patch_annule")]
        self.assertEqual(annulations, [], "aucune annulation sur une action acceptée")

    def test_un_environnement_sans_drapeau_se_comporte_comme_avant(self) -> None:
        environnement = _EnvironnementRefusant(refus=[True], avec_drapeau=False)
        boucle, _workspace = self._boucle(
            environnement,
            [_pas({"hypotheses": ["h"], "position": {"x": 5, "y": 6}})],
        )
        boucle.jouer_tour(1)
        assert boucle.etat is not None
        self.assertEqual(
            dict(boucle.etat.champs["position"]),
            {"x": 5, "y": 6},
            "sans drapeau déclaré, le patch est conservé : comportement inchangé",
        )

    def test_le_protocole_engendre_enonce_la_regle(self) -> None:
        self.assertIn(
            "refuse ton action",
            prompts.protocole_etat(_SCHEMA),
            "le protocole énonce l'annulation du patch sous action refusée (§H15.8)",
        )


class TestAdaptateurExposeRefusee(unittest.TestCase):
    """§S6.1 : l'issue du banc porte `refusee = not valide`."""

    def _environnement(self) -> EnvironnementBancEntrepot:
        moteur = EnvironnementEntrepot(generer_episode(seed=3, horizon=4, bruit=0))
        return EnvironnementBancEntrepot(moteur)

    def test_une_action_invalide_est_refusee(self) -> None:
        environnement = self._environnement()
        outils = {outil.nom: outil for outil in environnement.outils()}
        # Expédier un article inconnu est refusé par §S3.2 quel que soit l'état.
        observation = outils["ship"].fonction("article_inconnu", "etagere_0")
        self.assertTrue(str(observation).startswith("error:"))
        issue = environnement.derniere_issue()
        assert issue is not None
        self.assertTrue(issue.refusee)

    def test_wait_est_toujours_accepte(self) -> None:
        environnement = self._environnement()
        outils = {outil.nom: outil for outil in environnement.outils()}
        outils["wait"].fonction()
        issue = environnement.derniere_issue()
        assert issue is not None
        self.assertFalse(issue.refusee)


if __name__ == "__main__":
    unittest.main()
