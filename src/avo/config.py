"""Configuration du harnais : environnement, `.env`, validation, budgets.

@spec docs/BACKLOG.md U6 — Configuration `avo.config`
@spec docs/SPEC_HARNAIS.md §H3.1 (variables), §H3.2 (budget utile), §H3.3 (validation),
      §H3.4 (modes replay/live)
@spec docs/SPEC_HARNAIS.md §H4.6 (aucun secret journalisé)
@spec docs/BACKLOG.md U27 — `AVO_CONTEXT_MODE` (§H15.7, §H15.8)

Deux principes gouvernent ce module :

1. **Une configuration fausse s'arrête tout de suite, en nommant la variable.** Aucune
   valeur par défaut silencieuse ne comble un secret manquant (§H3.3).
2. **Un secret ne sort jamais d'ici.** La représentation textuelle et le résumé
   destiné aux journaux masquent la clé (§H4.6).
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

#: Marge appliquée par le proxy d'authentification à sa propre estimation de tokens
#: avant comparaison au plafond par clé. Mesurée le 2026-08-27 : le corps du refus
#: `413` donnait 286124 / 248803 = 1,15 (docs/JOURNAL.md).
MARGE_PROXY: Final = 1.15

#: Endpoints servis par la pile locale de rejeu (docs/SPEC_HARNAIS.md §H2.4).
HOTE_REJEU: Final = "http://127.0.0.1:11435"
ARC_REJEU: Final = "http://127.0.0.1:8765"

#: Jeton employé en mode rejeu. Ce n'est PAS un secret : le rejoueur ne distingue
#: que la présence d'un en-tête d'autorisation lorsqu'aucune clé ne lui est fournie.
JETON_REJEU: Final = "rejeu-sans-secret"

#: Plancher de budget de sortie imposé lorsque le raisonnement natif est actif
#: (§H12.1) : le raisonnement consomme `num_predict` AVANT tout contenu, si bien
#: qu'un budget court rend une réponse vide avec `finish_reason: length` — mesuré
#: le 2026-08-27 avec 64 tokens.
NUM_PREDICT_MIN_AVEC_THINK: Final = 8192

#: Fenêtre de contexte demandée par défaut en mode rejeu, où aucun serveur réel
#: n'impose de plafond. En mode live la variable est requise, sans valeur implicite.
CONTEXTE_DEFAUT_REJEU: Final = 131072

_VRAI = frozenset({"1", "true", "vrai", "oui", "yes", "on"})
_FAUX = frozenset({"0", "false", "faux", "non", "no", "off"})


class Mode(StrEnum):
    """Mode d'exécution (§H3.4). `StrEnum` : la valeur est directement le texte."""

    REJEU = "replay"
    LIVE = "live"


class ModeContexte(StrEnum):
    """Mode de composition du contexte (§H15.7, §H15.8). Exclusif par segment/run.

    `TRANSCRIPT` (défaut) : historique append-only (§H5). `ETAT` : état structuré Σ,
    prompt borné en O(1) par tour (§H15).
    """

    TRANSCRIPT = "transcript"
    ETAT = "state"


class ConfigInvalide(ValueError):
    """Configuration inutilisable. Le message nomme toujours la variable fautive."""


def lire_fichier_env(chemin: Path) -> dict[str, str]:
    """Analyse un fichier `.env` minimal : `CLE=valeur`, `#` en commentaire.

    Une ligne non vide qui n'est pas un commentaire et ne contient pas `=` est une
    erreur nommée, jamais une ligne silencieusement ignorée (CLAUDE.md §18).
    """
    valeurs: dict[str, str] = {}
    if not chemin.exists():
        return valeurs
    for numero, ligne_brute in enumerate(chemin.read_text(encoding="utf-8").splitlines(), start=1):
        ligne = ligne_brute.strip()
        if not ligne or ligne.startswith("#"):
            continue
        if ligne.startswith("export "):
            ligne = ligne.removeprefix("export ").strip()
        if "=" not in ligne:
            raise ConfigInvalide(
                f"{chemin} ligne {numero} : ligne ininterprétable, « CLE=valeur » attendu."
            )
        cle, _, valeur = ligne.partition("=")
        valeur = valeur.strip()
        if len(valeur) >= 2 and valeur[0] == valeur[-1] and valeur[0] in {'"', "'"}:
            valeur = valeur[1:-1]
        valeurs[cle.strip()] = valeur
    return valeurs


class _Source:
    """Environnement d'abord, `.env` en repli (§H3.1)."""

    def __init__(self, env: Mapping[str, str], fichier: Mapping[str, str]) -> None:
        self._env = env
        self._fichier = fichier

    def brut(self, nom: str) -> str | None:
        valeur = self._env.get(nom)
        if valeur is None or valeur == "":
            valeur = self._fichier.get(nom)
        return valeur if valeur else None

    def texte(self, nom: str, defaut: str) -> str:
        return self.brut(nom) or defaut

    def entier(self, nom: str, defaut: int) -> int:
        brut = self.brut(nom)
        if brut is None:
            return defaut
        try:
            valeur = int(brut)
        except ValueError as erreur:
            raise ConfigInvalide(f"{nom} : entier attendu, valeur reçue « {brut} ».") from erreur
        if valeur <= 0:
            raise ConfigInvalide(f"{nom} : entier strictement positif attendu, reçu {valeur}.")
        return valeur

    def reel(self, nom: str, defaut: float, mini: float, maxi: float) -> float:
        brut = self.brut(nom)
        if brut is None:
            return defaut
        try:
            valeur = float(brut)
        except ValueError as erreur:
            raise ConfigInvalide(f"{nom} : nombre attendu, valeur reçue « {brut} ».") from erreur
        if not mini <= valeur <= maxi:
            raise ConfigInvalide(f"{nom} : valeur attendue entre {mini} et {maxi}, reçue {valeur}.")
        return valeur

    def booleen(self, nom: str, defaut: bool) -> bool:
        brut = self.brut(nom)
        if brut is None:
            return defaut
        normalise = brut.strip().lower()
        if normalise in _VRAI:
            return True
        if normalise in _FAUX:
            return False
        raise ConfigInvalide(f"{nom} : booléen attendu (true/false), valeur reçue « {brut} ».")


def _valider_url(nom: str, valeur: str) -> str:
    """Vérifie une URL de base et retire un éventuel slash final."""
    if not valeur.startswith(("http://", "https://")):
        raise ConfigInvalide(f"{nom} : URL http(s) attendue, valeur reçue « {valeur} ».")
    reste = valeur.split("://", 1)[1]
    if not reste or reste.startswith("/"):
        raise ConfigInvalide(f"{nom} : hôte manquant dans « {valeur} ».")
    return valeur.rstrip("/")


def _valider_contexte_mode(valeur: str) -> ModeContexte:
    """Valide `AVO_CONTEXT_MODE` (§H3.1, §H15.7) : jamais une valeur devinée."""
    try:
        return ModeContexte(valeur)
    except ValueError as erreur:
        valeurs = ", ".join(mode.value for mode in ModeContexte)
        raise ConfigInvalide(
            f"AVO_CONTEXT_MODE : une valeur parmi {valeurs} attendue, reçue « {valeur} »."
        ) from erreur


@dataclass(frozen=True)
class Config:
    """Configuration résolue et validée du harnais (§H3)."""

    mode: Mode
    ollama_host: str
    ollama_api_key: str
    contexte_demande: int
    modele: str
    think: bool
    num_predict: int
    temperature: float
    timeout_s: int
    ratio_continuation: float
    tool_steps_max: int
    actions_max_niveau: int
    actions_max_jeu: int
    sup_stall_actions: int
    sup_cooldown: int
    runs_dir: Path
    arc_api_key: str | None
    arc_base_url: str
    contexte_mode: ModeContexte

    @property
    def budget_prompt(self) -> int:
        """Tokens de prompt réellement disponibles (§H3.2).

        `floor(contexte / marge du proxy) − budget de sortie`. La marge reproduit
        celle que le proxy applique à sa propre estimation : viser le plafond nominal
        déclenche un `413`.
        """
        return math.floor(self.contexte_demande / MARGE_PROXY) - self.num_predict

    def avec_plafond_appris(self, max_context_tokens: int) -> Config:
        """Rejoue le budget sur un plafond appris d'un `413` (§H3.2).

        Le plafond n'est abaissé que s'il est réellement inférieur : un `413` ne peut
        pas élargir silencieusement une fenêtre configurée plus étroite.
        """
        if max_context_tokens <= 0:
            raise ConfigInvalide(
                "max_context_tokens : entier strictement positif attendu, "
                f"reçu {max_context_tokens}."
            )
        if max_context_tokens >= self.contexte_demande:
            return self
        return replace(self, contexte_demande=max_context_tokens)

    def resume(self) -> dict[str, Any]:
        """Résumé journalisable : AUCUN secret n'y figure (§H4.6)."""
        return {
            "mode": self.mode.value,
            "ollama_host": self.ollama_host,
            "modele": self.modele,
            "contexte_demande": self.contexte_demande,
            "budget_prompt": self.budget_prompt,
            "num_predict": self.num_predict,
            "think": self.think,
            "temperature": self.temperature,
            "timeout_s": self.timeout_s,
            "ratio_continuation": self.ratio_continuation,
            "tool_steps_max": self.tool_steps_max,
            "actions_max_niveau": self.actions_max_niveau,
            "actions_max_jeu": self.actions_max_jeu,
            "sup_stall_actions": self.sup_stall_actions,
            "sup_cooldown": self.sup_cooldown,
            "runs_dir": str(self.runs_dir),
            "arc_base_url": self.arc_base_url,
            "contexte_mode": self.contexte_mode.value,
            "ollama_api_key": "<masquée>",
            "arc_api_key": "<masquée>" if self.arc_api_key else None,
        }

    def __repr__(self) -> str:
        """Représentation sans secret : un objet Config peut atterrir dans un log."""
        return f"Config({self.resume()})"


def charger(
    mode: Mode | str = Mode.REJEU,
    env: Mapping[str, str] | None = None,
    racine: Path | None = None,
) -> Config:
    """Résout la configuration depuis l'environnement puis `.env` (§H3.1).

    En mode rejeu, aucun secret n'est requis : les valeurs pointent vers la pile
    locale. En mode live, l'absence d'un secret est une erreur nommée — jamais une
    valeur par défaut (§H3.3, §H3.4).
    """
    mode_resolu = Mode(mode) if not isinstance(mode, Mode) else mode
    environnement = os.environ if env is None else env
    fichier = lire_fichier_env((racine or Path()) / ".env")
    source = _Source(environnement, fichier)
    live = mode_resolu is Mode.LIVE

    if live:
        hote = source.brut("OLLAMA_HOST")
        if hote is None:
            raise ConfigInvalide(
                "OLLAMA_HOST : requis en mode live, absent de l'environnement et de .env."
            )
        cle = source.brut("OLLAMA_API_KEY")
        if cle is None:
            raise ConfigInvalide(
                "OLLAMA_API_KEY : requis en mode live, absent de l'environnement et de .env."
            )
        contexte_brut = source.brut("OLLAMA_CONTEXT_LENGTH")
        if contexte_brut is None:
            raise ConfigInvalide(
                "OLLAMA_CONTEXT_LENGTH : requis en mode live, absent de l'environnement et de .env."
            )
        contexte = source.entier("OLLAMA_CONTEXT_LENGTH", 0)
        arc = source.brut("ARC_API_KEY")
        if arc is None:
            raise ConfigInvalide(
                "ARC_API_KEY : requis en mode live, absent de l'environnement et de .env."
            )
    else:
        hote = source.texte("OLLAMA_HOST", HOTE_REJEU)
        cle = source.texte("OLLAMA_API_KEY", JETON_REJEU)
        contexte = source.entier("OLLAMA_CONTEXT_LENGTH", CONTEXTE_DEFAUT_REJEU)
        arc = source.brut("ARC_API_KEY")

    config = Config(
        mode=mode_resolu,
        ollama_host=_valider_url("OLLAMA_HOST", hote),
        ollama_api_key=cle,
        contexte_demande=contexte,
        modele=source.texte("AVO_MODEL", "qwen3.6:35b"),
        think=source.booleen("AVO_THINK", False),
        num_predict=source.entier("AVO_NUM_PREDICT", 4096),
        temperature=source.reel("AVO_TEMPERATURE", 0.7, 0.0, 2.0),
        timeout_s=source.entier("AVO_TIMEOUT_S", 900),
        ratio_continuation=source.reel("AVO_CONTEXT_SOFT_RATIO", 0.85, 0.05, 1.0),
        tool_steps_max=source.entier("AVO_TOOL_STEPS_MAX", 40),
        actions_max_niveau=source.entier("AVO_ACTIONS_MAX_NIVEAU", 1000),
        actions_max_jeu=source.entier("AVO_ACTIONS_MAX_JEU", 5000),
        sup_stall_actions=source.entier("AVO_SUP_STALL_ACTIONS", 60),
        sup_cooldown=source.entier("AVO_SUP_COOLDOWN", 30),
        runs_dir=Path(source.texte("AVO_RUNS_DIR", "runs")),
        arc_api_key=arc,
        # En mode rejeu, la base ARC pointe la pile locale : le mode ne requiert
        # aucun secret et ne doit surtout atteindre aucun service qui publierait
        # (§H3.4, §A2.3).
        arc_base_url=_valider_url(
            "ARC_BASE_URL",
            source.texte("ARC_BASE_URL", "https://three.arcprize.org" if live else ARC_REJEU),
        ),
        contexte_mode=_valider_contexte_mode(
            source.texte("AVO_CONTEXT_MODE", ModeContexte.TRANSCRIPT.value)
        ),
    )

    if config.think and config.num_predict < NUM_PREDICT_MIN_AVEC_THINK:
        raise ConfigInvalide(
            f"AVO_NUM_PREDICT : avec AVO_THINK=true, un budget de sortie d'au moins "
            f"{NUM_PREDICT_MIN_AVEC_THINK} tokens est imposé (docs/SPEC_HARNAIS.md §H12.1) — "
            f"reçu {config.num_predict}. Le raisonnement natif consomme ce budget avant "
            "tout contenu : une valeur plus courte rend une réponse vide."
        )

    if config.budget_prompt <= 0:
        raise ConfigInvalide(
            "AVO_NUM_PREDICT : budget de sortie trop grand pour la fenêtre demandée — "
            f"contexte {config.contexte_demande} avec la marge de {MARGE_PROXY} laisse "
            f"{math.floor(config.contexte_demande / MARGE_PROXY)} tokens, "
            f"dont {config.num_predict} réservés à la sortie."
        )
    return config
