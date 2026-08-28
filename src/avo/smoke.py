"""Fumée manuelle contre le VRAI endpoint : `make smoke-live`.

@spec docs/BACKLOG.md U8 — Comptabilité, journalisation, workspace de run
@spec docs/SPEC_HARNAIS.md §H4.8 (version, modèles, complétion courte, tool-call)

Hors campagne : exige `.env`, appelle réellement l'endpoint, et n'est exécutée ni par
les tests ni par le worker planifié. Chaque contrôle dit ce qu'il a obtenu ; un échec
n'interrompt pas la série, pour que la fumée rende un bilan complet.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import TextIO

from avo.config import Config, Mode, charger
from avo.llm.client import LLMClient

#: Outil minimal employé pour éprouver l'appel d'outil (§H4.8).
OUTIL_FUMEE = {
    "type": "function",
    "function": {
        "name": "run_shell",
        "description": "Exécute une commande shell et renvoie sa sortie",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
}


@dataclass
class Controle:
    """Résultat d'un contrôle de fumée."""

    libelle: str
    reussi: bool
    detail: str


def _executer(libelle: str, action: Callable[[], str]) -> Controle:
    try:
        return Controle(libelle, True, action())
    except Exception as erreur:  # noqa: BLE001 — la fumée rapporte, elle n'interprète pas
        return Controle(libelle, False, f"{type(erreur).__name__}: {erreur}")


def controles(client: LLMClient) -> list[Controle]:
    """Exécute la série de fumée et rend les résultats, sans lever."""
    resultats = [
        _executer("version du serveur", client.version),
        _executer("modèles servis", lambda: ", ".join(client.modeles()) or "(aucun)"),
    ]

    def completion() -> str:
        resultat = client.chat(
            [{"role": "user", "content": "Réponds exactement par le jeton : OK-AVO"}],
            num_predict=512,
            temperature=0,
        )
        return f"{resultat.content.strip()[:40]!r} ({resultat.eval_count} tokens)"

    def appel_outil() -> str:
        resultat = client.chat(
            [{"role": "user", "content": "Liste /tmp en utilisant l'outil disponible."}],
            [OUTIL_FUMEE],
            num_predict=512,
            temperature=0,
        )
        if not resultat.demande_outil:
            raise AssertionError("aucun appel d'outil demandé par le modèle")
        appel = resultat.tool_calls[0]
        return f"{appel.nom}({appel.arguments})"

    resultats.append(_executer("complétion courte", completion))
    resultats.append(_executer("appel d'outil", appel_outil))
    return resultats


def executer(config: Config | None = None, sortie: TextIO | None = None) -> int:
    """Lance la fumée et rend le code de sortie du processus."""
    flux = sortie if sortie is not None else sys.stdout
    resolue = config if config is not None else charger(Mode.LIVE)
    print(f"fumée contre l'endpoint configuré (mode {resolue.mode.value})", file=flux)
    resultats = controles(LLMClient(resolue))
    for controle in resultats:
        marque = "OK   " if controle.reussi else "ECHEC"
        print(f"  {marque} {controle.libelle:24s} {controle.detail}", file=flux)
    echecs = [controle for controle in resultats if not controle.reussi]
    if echecs:
        print(f"fumée : {len(echecs)} contrôle(s) en échec", file=flux)
        return 1
    print("fumée : TOUT VERT", file=flux)
    return 0
