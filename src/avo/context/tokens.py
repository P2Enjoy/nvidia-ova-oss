"""Comptabilité des tokens : estimation locale, correction par le réel.

@spec docs/BACKLOG.md U8 — Comptabilité, journalisation, workspace de run
@spec docs/SPEC_HARNAIS.md §H5.2 (estimation corrigée par `prompt_eval_count`)

L'estimation sert aux SEUILS — décider quand basculer en contexte frais avant que le
serveur ne refuse. Le compte réel rendu par le serveur fait foi dans les MÉTRIQUES, et
sert à recalibrer l'estimation : le rapport chars/token dépend du contenu, et une
valeur figée dériverait sur des grilles de chiffres comme sur de la prose.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

#: Rapport initial caractères/token. Mesuré le 2026-08-27 : un prompt de contenu
#: numérique dense a rendu 2,34 car/token, un contenu de prose davantage. La valeur
#: de départ est volontairement prudente ; la calibration corrige dès le premier
#: échange réel.
CARACTERES_PAR_TOKEN = 3.4


def estimer_tokens(texte: str, caracteres_par_token: float = CARACTERES_PAR_TOKEN) -> int:
    """Estime le nombre de tokens d'un texte. Toujours au moins 1 si non vide."""
    if not texte:
        return 0
    return max(1, round(len(texte) / caracteres_par_token))


def estimer_messages(
    messages: Iterable[Mapping[str, Any]], caracteres_par_token: float = CARACTERES_PAR_TOKEN
) -> int:
    """Estime le coût d'une liste de messages, rôles compris."""
    total = 0
    for message in messages:
        for valeur in message.values():
            total += estimer_tokens(str(valeur), caracteres_par_token)
    return total


@dataclass
class TokenLedger:
    """Suit l'estimation face au réel et se recalibre (§H5.2)."""

    caracteres_par_token: float = CARACTERES_PAR_TOKEN
    estime_cumule: int = 0
    reel_cumule: int = 0
    sortie_cumulee: int = 0
    appels: int = 0
    ecarts: list[float] = field(default_factory=list)

    def estimer(self, texte: str) -> int:
        """Estimation courante, avec le rapport calibré à ce jour."""
        return estimer_tokens(texte, self.caracteres_par_token)

    def estimer_messages(self, messages: Iterable[Mapping[str, Any]]) -> int:
        return estimer_messages(messages, self.caracteres_par_token)

    def enregistrer(self, estime: int, prompt_eval_count: int, eval_count: int = 0) -> None:
        """Enregistre un échange et recalibre le rapport caractères/token.

        La recalibration n'a lieu que si les deux comptes sont exploitables : un
        serveur qui ne rendrait pas ses compteurs ne doit pas dérégler l'estimation.
        """
        self.appels += 1
        self.estime_cumule += estime
        self.reel_cumule += prompt_eval_count
        self.sortie_cumulee += eval_count
        if estime > 0 and prompt_eval_count > 0:
            rapport = prompt_eval_count / estime
            self.ecarts.append(rapport)
            self.caracteres_par_token = self.caracteres_par_token / rapport

    @property
    def facteur_correction(self) -> float:
        """Rapport cumulé réel/estimé. 1.0 tant qu'aucun échange n'est enregistré."""
        if self.estime_cumule <= 0:
            return 1.0
        return self.reel_cumule / self.estime_cumule

    @property
    def total_tokens(self) -> int:
        """Tokens réellement consommés, entrée et sortie."""
        return self.reel_cumule + self.sortie_cumulee

    def resume(self) -> dict[str, Any]:
        """Résumé journalisable : des compteurs, aucun contenu."""
        return {
            "appels": self.appels,
            "prompt_estime_cumule": self.estime_cumule,
            "prompt_reel_cumule": self.reel_cumule,
            "sortie_cumulee": self.sortie_cumulee,
            "total_tokens": self.total_tokens,
            "facteur_correction": round(self.facteur_correction, 4),
            "caracteres_par_token": round(self.caracteres_par_token, 3),
        }
