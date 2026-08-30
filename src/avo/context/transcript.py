"""Transcript append-only : l'historique envoyé au modèle ne se réécrit jamais.

@spec docs/BACKLOG.md U9 — Transcript append-only
@spec docs/SPEC_HARNAIS.md §H5.1 (structure immuable en tête, empreinte de préfixe),
      §H5.2 (comptabilité), §H1.3.1 (le préremplissage domine le coût)

Motif mesuré, et c'est le cœur de la conception : le préremplissage domine le coût
(≈493 tokens/s le 2026-08-27, contre un rejeu quasi instantané des mêmes préfixes le
2026-08-28). Un historique dont la tête change invalide le cache de préfixe du serveur
et fait repayer l'intégralité du contexte à chaque tour.

La structure est donc **fonctionnelle** : `ajouter` rend un NOUVEAU transcript qui
partage le préfixe, au lieu de muter celui qui existe. Aucune méthode ne permet
d'insérer, de retirer ni de remplacer un message déjà envoyé — c'est vérifié par un
test de surface du module.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

#: Méthodes dont l'ABSENCE fait la garantie : aucune ne doit exister sur Transcript.
#: Le test de surface s'appuie sur cette liste (§H5.1).
MUTATIONS_INTERDITES = frozenset(
    {
        "append",
        "extend",
        "insert",
        "remove",
        "pop",
        "clear",
        "sort",
        "reverse",
        "__setitem__",
        "__delitem__",
        "__iadd__",
        "tronquer",
        "remplacer",
        "vider",
    }
)


class PrefixeRompu(RuntimeError):
    """Le préfixe déjà envoyé a changé : le cache serait invalidé (§H5.1).

    Levée plutôt qu'absorbée : un préfixe rompu ne se voit pas dans les résultats,
    seulement dans la facture de temps. Le signaler tôt est la seule protection.
    """


@dataclass(frozen=True, slots=True)
class Message:
    """Un message de l'historique. Figé une fois créé."""

    role: str
    content: str = ""
    tool_calls: tuple[Mapping[str, Any], ...] = ()
    tool_name: str | None = None

    def en_dict(self) -> dict[str, Any]:
        """Forme envoyée à l'API : les champs vides ne sont pas émis."""
        charge: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            charge["tool_calls"] = [dict(appel) for appel in self.tool_calls]
        if self.tool_name is not None:
            charge["name"] = self.tool_name
        return charge


def _canoniser(messages: Sequence[Message]) -> bytes:
    return json.dumps(
        [message.en_dict() for message in messages],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()


@dataclass(frozen=True, slots=True)
class Transcript:
    """Historique d'un segment, figé en tête (§H5.1).

    `ajouter` rend un nouveau transcript ; l'instance existante n'est jamais modifiée.
    Le message système est posé à l'ouverture du segment et ne bouge plus.
    """

    messages: tuple[Message, ...] = ()

    # ------------------------------------------------------------- construction
    @classmethod
    def ouvrir(cls, systeme: str | None = None) -> Transcript:
        """Ouvre un segment. Le message système, s'il existe, est figé en tête."""
        if systeme is None:
            return cls()
        return cls((Message(role="system", content=systeme),))

    def ajouter(self, message: Message) -> Transcript:
        """Rend un NOUVEAU transcript prolongeant celui-ci."""
        return Transcript(self.messages + (message,))

    def ajouter_tous(self, messages: Iterable[Message]) -> Transcript:
        return Transcript(self.messages + tuple(messages))

    def utilisateur(self, contenu: str) -> Transcript:
        return self.ajouter(Message(role="user", content=contenu))

    def assistant(self, contenu: str, tool_calls: Iterable[Mapping[str, Any]] = ()) -> Transcript:
        return self.ajouter(
            Message(role="assistant", content=contenu, tool_calls=tuple(tool_calls))
        )

    def outil(self, nom: str, resultat: str) -> Transcript:
        """Résultat d'outil, rendu au modèle comme un message à part entière (§H7.2)."""
        return self.ajouter(Message(role="tool", content=resultat, tool_name=nom))

    # ---------------------------------------------------------------- empreintes
    def empreinte(self) -> str:
        """Empreinte de l'historique entier."""
        return hashlib.sha256(_canoniser(self.messages)).hexdigest()

    def empreinte_prefixe(self, longueur: int) -> str:
        """Empreinte des `longueur` premiers messages.

        C'est l'outil de la garantie : le préfixe déjà envoyé doit rendre la même
        empreinte au tour suivant, sans quoi le cache du serveur est invalidé.
        """
        if longueur < 0 or longueur > len(self.messages):
            raise ValueError(
                f"préfixe de longueur {longueur} demandé sur {len(self.messages)} messages"
            )
        return hashlib.sha256(_canoniser(self.messages[:longueur])).hexdigest()

    def prolonge(self, precedent: Transcript) -> bool:
        """Ce transcript prolonge-t-il `precedent` sans en changer une virgule ?"""
        if len(precedent) > len(self):
            return False
        return self.empreinte_prefixe(len(precedent)) == precedent.empreinte()

    def verifier_prolonge(self, precedent: Transcript) -> None:
        """Comme `prolonge`, mais lève `PrefixeRompu` au lieu de rendre False."""
        if not self.prolonge(precedent):
            raise PrefixeRompu(
                f"le préfixe de {len(precedent)} message(s) déjà envoyé a changé : "
                "le cache de préfixe du serveur serait invalidé et le contexte entier "
                "repayé (docs/SPEC_HARNAIS.md §H5.1). L'historique est append-only."
            )

    # --------------------------------------------------------------- utilisation
    def pour_api(self) -> list[dict[str, Any]]:
        """Messages sous la forme attendue par le client d'inférence (§H4.2)."""
        return [message.en_dict() for message in self.messages]

    def texte_integral(self) -> str:
        """Concaténation servant à l'estimation de tokens (§H5.2)."""
        return "\n".join(f"{message.role}: {message.content}" for message in self.messages)

    def resume(self) -> dict[str, Any]:
        """Résumé journalisable : des compteurs, aucun contenu (§H4.6)."""
        roles: dict[str, int] = {}
        for message in self.messages:
            roles[message.role] = roles.get(message.role, 0) + 1
        return {
            "messages": len(self.messages),
            "roles": roles,
            "caracteres": sum(len(message.content) for message in self.messages),
            "empreinte": self.empreinte()[:12],
        }

    def __len__(self) -> int:
        return len(self.messages)

    def __iter__(self) -> Iterator[Message]:
        return iter(self.messages)
