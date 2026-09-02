"""Format de cassette : échanges HTTP réels, expurgés, appariables.

@spec docs/BACKLOG.md U4
@spec docs/SPEC_HARNAIS.md §H4.7 (enregistrement, expurgation, clé d'appariement)
@spec docs/SPEC_HARNAIS.md §H4.6 (aucun secret journalisé ni persisté)

Une cassette est un fichier JSONL : un échange par ligne. L'appariement repose sur
une empreinte du corps de requête canonisé, ce qui rend toute divergence détectable
plutôt que silencieusement absorbée.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from avo.llm.client import fusionner_fragments

#: Au-delà de cette taille, le corps de requête n'est pas stocké : seule son
#: empreinte l'est. Évite d'alourdir le dépôt avec les prompts volumineux (le
#: scénario de dépassement de contexte pèse près d'un mégaoctet).
TAILLE_CORPS_MAX = 8192

#: En-têtes de réponse conservés. Liste blanche : tout le reste est écarté, ce qui
#: exclut par construction les en-têtes d'authentification et d'infrastructure.
ENTETES_RETENUS = ("content-type",)

#: Natures d'authentification enregistrables. La clé elle-même n'est JAMAIS écrite.
AUTH_ABSENTE = "absente"
AUTH_VALIDE = "bearer_valide"
AUTH_INVALIDE = "bearer_invalide"


def canoniser(corps: Any) -> bytes:
    """Sérialise un corps JSON de façon stable (clés triées, séparateurs fixes)."""
    return json.dumps(corps, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def empreinte(corps: Any) -> str:
    """Empreinte stable d'un corps de requête, utilisée pour l'appariement."""
    return hashlib.sha256(canoniser(corps)).hexdigest()


@dataclass(frozen=True)
class RequestRecord:
    """Requête telle qu'elle a été envoyée au vrai serveur, expurgée."""

    method: str
    path: str
    auth: str
    body_sha256: str
    body_bytes: int
    body: Any | None = None

    @classmethod
    def depuis(cls, method: str, path: str, auth: str, body: Any) -> RequestRecord:
        brut = canoniser(body) if body is not None else b""
        stocke = body if len(brut) <= TAILLE_CORPS_MAX else None
        return cls(
            method=method.upper(),
            path=path,
            auth=auth,
            body_sha256=empreinte(body) if body is not None else empreinte(None),
            body_bytes=len(brut),
            body=stocke,
        )

    @property
    def cle(self) -> str:
        """Clé d'appariement : méthode, chemin, nature d'auth, empreinte du corps."""
        return f"{self.method} {self.path} auth={self.auth} sha256={self.body_sha256}"


@dataclass(frozen=True)
class ResponseRecord:
    """Réponse telle que le vrai serveur l'a rendue."""

    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: Any | None = None
    text: str | None = None

    def corps_octets(self) -> bytes:
        if self.body is not None:
            return canoniser(self.body)
        return (self.text or "").encode()


@dataclass(frozen=True)
class Exchange:
    """Un aller-retour HTTP complet, tel qu'il a réellement eu lieu."""

    request: RequestRecord
    response: ResponseRecord
    recorded_at: str
    duration_ms: int

    def en_json(self) -> dict[str, Any]:
        requete: dict[str, Any] = {
            "method": self.request.method,
            "path": self.request.path,
            "auth": self.request.auth,
            "body_sha256": self.request.body_sha256,
            "body_bytes": self.request.body_bytes,
        }
        if self.request.body is not None:
            requete["body"] = self.request.body
        reponse: dict[str, Any] = {"status": self.response.status, "headers": self.response.headers}
        if self.response.body is not None:
            reponse["body"] = self.response.body
        if self.response.text is not None:
            reponse["text"] = self.response.text
        return {
            "request": requete,
            "response": reponse,
            "recorded_at": self.recorded_at,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def depuis_json(cls, donnees: dict[str, Any]) -> Exchange:
        q = donnees["request"]
        r = donnees["response"]
        return cls(
            request=RequestRecord(
                method=q["method"],
                path=q["path"],
                auth=q["auth"],
                body_sha256=q["body_sha256"],
                body_bytes=q["body_bytes"],
                body=q.get("body"),
            ),
            response=ResponseRecord(
                status=r["status"],
                headers=dict(r.get("headers", {})),
                body=r.get("body"),
                text=r.get("text"),
            ),
            recorded_at=donnees["recorded_at"],
            duration_ms=donnees["duration_ms"],
        )


def enveloppe_conversation(echange: Exchange) -> dict[str, Any] | None:
    """Enveloppe d'objet unique d'une réponse de conversation 200, ou `None`.

    Un corps enregistré en objet JSON est rendu tel quel ; un corps streamé
    (NDJSON, §H4.2) est assemblé par `fusionner_fragments` — l'assemblage MÊME
    du client (§H4.3), jamais une seconde implémentation. Sert de moule aux
    décors de test qui scriptent des réponses sous l'enveloppe réelle.
    """
    if echange.response.status != 200:
        return None
    corps = echange.response.body
    if isinstance(corps, dict):
        return copy.deepcopy(corps) if "message" in corps else None
    texte = echange.response.text
    if not texte:
        return None
    try:
        fragments = [json.loads(ligne) for ligne in texte.splitlines() if ligne.strip()]
    except json.JSONDecodeError:
        return None
    if not fragments or not isinstance(fragments[-1], dict) or not fragments[-1].get("done"):
        return None
    fusion = fusionner_fragments(fragments)
    return fusion if "message" in fusion else None


def premiere_conversation(cassette: Cassette) -> dict[str, Any]:
    """Première réponse de conversation 200 de la cassette, en objet unique.

    Lève une erreur explicite plutôt que d'inventer une forme (§H4.7) : la
    cassette du contrat se régénère par « make record-llm », jamais à la main.
    """
    for echange in cassette:
        enveloppe = enveloppe_conversation(echange)
        if enveloppe is not None:
            return enveloppe
    raise RequeteInconnue(
        "aucune réponse de conversation dans la cassette — lancer « make record-llm » "
        "plutôt que d'inventer une réponse (docs/SPEC_HARNAIS.md §H4.7)."
    )


class RequeteInconnue(LookupError):
    """Aucune entrée de cassette ne correspond à la requête reçue.

    Levée volontairement plutôt que de fabriquer une réponse : un test doit rougir
    de façon lisible quand le contrat change (H4.7).
    """


@dataclass
class Cassette:
    """Collection d'échanges enregistrés, appariables par clé."""

    echanges: list[Exchange] = field(default_factory=list)

    def ajouter(self, echange: Exchange) -> None:
        self.echanges.append(echange)

    def apparier(self, method: str, path: str, auth: str, body: Any) -> Exchange:
        recherchee = RequestRecord.depuis(method, path, auth, body)
        for echange in self.echanges:
            if echange.request.cle == recherchee.cle:
                return echange
        connues = "\n".join(f"  - {e.request.cle}" for e in self.echanges) or "  (cassette vide)"
        raise RequeteInconnue(
            f"aucun échange enregistré ne correspond à :\n  - {recherchee.cle}\n"
            f"entrées disponibles :\n{connues}\n"
            "Enregistrez le scénario avec « make record-llm » plutôt que d'inventer "
            "une réponse (docs/SPEC_HARNAIS.md §H4.7)."
        )

    def ecrire(self, chemin: Path) -> None:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        with chemin.open("w", encoding="utf-8") as flux:
            for echange in self.echanges:
                flux.write(json.dumps(echange.en_json(), ensure_ascii=False) + "\n")

    @classmethod
    def lire(cls, chemin: Path) -> Cassette:
        cassette = cls()
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            if ligne.strip():
                cassette.ajouter(Exchange.depuis_json(json.loads(ligne)))
        return cassette

    @classmethod
    def lire_dossier(cls, dossier: Path) -> Cassette:
        cassette = cls()
        for fichier in sorted(dossier.glob("*.jsonl")):
            cassette.echanges.extend(cls.lire(fichier).echanges)
        return cassette

    def __iter__(self) -> Iterator[Exchange]:
        return iter(self.echanges)

    def __len__(self) -> int:
        return len(self.echanges)
