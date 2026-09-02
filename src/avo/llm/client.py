"""Client d'inférence : surface native Ollama `/api/chat`.

@spec docs/BACKLOG.md U7 — Client d'inférence
@spec docs/SPEC_HARNAIS.md §H4.1 (surface native, interface remplaçable), §H4.2 (requête),
      §H4.3 (réponse typée), §H4.4 (erreurs typées), §H4.5 (retries), §H4.6 (sans secret)
@spec docs/SPEC_HARNAIS.md §H12 (politique de raisonnement, via la configuration)

Le client ne connaît ni la boucle agent ni les outils : il traduit un échange de
messages en un appel HTTP et rend un résultat typé. Le transport est injectable, ce
qui permet de l'éprouver contre le rejeu des échanges RÉELS enregistrés (§H4.7).
"""

from __future__ import annotations

import http.client
import json
import logging
import random
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from avo.config import Config
from avo.transport import attente, avec_retries

_journal = logging.getLogger("avo.llm")

# La politique de retry (attentes, jitter) vit dans `avo.transport` : elle est
# partagée avec le client ARC (§A2.1), afin que « mêmes règles » reste vrai dans le
# temps et pas seulement le jour où on l'écrit.


class LLMError(Exception):
    """Erreur d'inférence. Base de toutes les erreurs typées du client (§H4.4)."""


class AuthError(LLMError):
    """401 ou 403 : la clé est refusée. FATALE — jamais retentée (§H4.4)."""


class ContextOverflow(LLMError):
    """413 : contexte trop grand pour la clé. Porte les champs du corps réel (§H4.4).

    Déclenche la continuation en contexte frais (§H5.4) et l'apprentissage du plafond
    (§H3.2). Ce n'est donc PAS une erreur fatale mais un cas nominal.
    """

    def __init__(
        self,
        message: str,
        tokens_estimated: int | None = None,
        max_context_tokens: int | None = None,
    ) -> None:
        super().__init__(message)
        self.tokens_estimated = tokens_estimated
        self.max_context_tokens = max_context_tokens


class ServerError(LLMError):
    """5xx : panne côté serveur. Retentée (§H4.5)."""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


class TransportError(LLMError):
    """Réseau injoignable ou délai dépassé. Retentée (§H4.5)."""


class ProtocolError(LLMError):
    """Réponse 2xx inexploitable (JSON invalide, champs absents). Non retentée."""


@dataclass(frozen=True)
class ToolCall:
    """Appel d'outil demandé par le modèle (§H4.3).

    Des arguments non-JSON ne lèvent PAS d'exception : ils sont conservés bruts et
    signalés, pour que la boucle rende au modèle une erreur d'outil exploitable
    (§H7.4) plutôt que d'interrompre le run.
    """

    nom: str
    arguments: dict[str, Any] = field(default_factory=dict)
    identifiant: str | None = None
    arguments_bruts: str | None = None
    erreur_arguments: str | None = None

    @property
    def valide(self) -> bool:
        return self.erreur_arguments is None


@dataclass(frozen=True)
class ChatResult:
    """Réponse d'inférence normalisée (§H4.3)."""

    content: str
    reasoning: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    done_reason: str | None = None
    prompt_eval_count: int = 0
    eval_count: int = 0
    total_duration_ms: int = 0
    prompt_eval_duration_ms: int = 0
    eval_duration_ms: int = 0
    modele: str = ""

    @property
    def demande_outil(self) -> bool:
        """Le modèle demande-t-il un appel d'outil ?

        La détection se fait sur la PRÉSENCE de `message.tool_calls`, jamais sur
        `done_reason` : mesuré le 2026-08-28 sur le serveur réel, la surface native
        rend `done_reason: "stop"` même lorsqu'elle demande un outil — `tool_calls`
        est une convention de la surface compatible OpenAI, pas de celle-ci.
        """
        return bool(self.tool_calls)

    @property
    def tronquee(self) -> bool:
        """La génération s'est-elle arrêtée sur la limite de sortie ?

        Symptôme mesuré du raisonnement qui dévore `num_predict` (§H12.1).
        """
        return self.done_reason == "length"

    def resume(self) -> dict[str, Any]:
        """Résumé journalisable : compteurs et durées, aucun contenu (§H4.6)."""
        return {
            "modele": self.modele,
            "done_reason": self.done_reason,
            "prompt_eval_count": self.prompt_eval_count,
            "eval_count": self.eval_count,
            "total_duration_ms": self.total_duration_ms,
            "tool_calls": len(self.tool_calls),
            "content_chars": len(self.content),
            "reasoning_chars": len(self.reasoning),
        }


@dataclass(frozen=True)
class ReponseHTTP:
    """Réponse brute rendue par un transport."""

    status: int
    body: bytes


class Transport(Protocol):
    """Contrat minimal d'un transport HTTP, pour rendre le client éprouvable."""

    def __call__(
        self, url: str, corps: bytes, entetes: Mapping[str, str], timeout: float
    ) -> ReponseHTTP: ...


def transport_urllib(
    url: str,
    corps: bytes,
    entetes: Mapping[str, str],
    timeout: float,
    methode: str = "POST",
) -> ReponseHTTP:
    """Transport par défaut, bibliothèque standard (§H2.1)."""
    requete = urllib.request.Request(  # noqa: S310
        url, data=corps or None, method=methode
    )
    for nom, valeur in entetes.items():
        requete.add_header(nom, valeur)
    try:
        with urllib.request.urlopen(requete, timeout=timeout) as reponse:  # noqa: S310
            return ReponseHTTP(int(reponse.status), reponse.read())
    except urllib.error.HTTPError as erreur:
        return ReponseHTTP(int(erreur.code), erreur.read())
    except urllib.error.URLError as erreur:
        raise TransportError(f"endpoint injoignable : {erreur.reason}") from erreur
    except TimeoutError as erreur:
        raise TransportError(f"délai dépassé après {timeout} s") from erreur
    except (http.client.HTTPException, OSError) as erreur:
        # Mesuré (2026-09-01, relevé live du banc) : un pont qui coupe APRÈS
        # l'envoi de la requête mais AVANT les premiers en-têtes lève
        # `RemoteDisconnected` (ou un `ConnectionResetError` nu) que `urllib`
        # n'enveloppe pas en `URLError`. C'est une panne de transport comme les
        # autres (§H4.4) : typée, donc retentée selon §H4.5 — jamais un arrêt
        # brut du run.
        raise TransportError(f"connexion interrompue : {erreur!r}") from erreur


def construire_corps(
    config: Config,
    messages: Sequence[Mapping[str, Any]],
    tools: Sequence[Mapping[str, Any]] | None = None,
    *,
    num_ctx: int | None = None,
    num_predict: int | None = None,
    temperature: float | int | None = None,
) -> dict[str, Any]:
    """Construit le corps de la requête `/api/chat` (§H4.2).

    Les surcharges servent aux scénarios d'enregistrement du contrat (§H4.7), qui
    doivent produire EXACTEMENT le corps que le client émettra ensuite : c'est ce qui
    garantit qu'une cassette s'apparie au client sans divergence de sérialisation.
    """
    corps: dict[str, Any] = {
        "model": config.modele,
        # `stream: true` est un cadrage HTTP, pas une API incrémentale (§H4.2) :
        # le pont 443 coupe à 40 s sans premiers en-têtes, et en mode non streamé
        # l'origine ne les rend qu'à la FIN de la génération — toute génération
        # longue mourait en 500. Le transport lit toujours le corps jusqu'au bout.
        "stream": True,
        "think": config.think,
        "options": {
            "num_ctx": config.contexte_demande if num_ctx is None else num_ctx,
            "num_predict": config.num_predict if num_predict is None else num_predict,
            "temperature": config.temperature if temperature is None else temperature,
        },
        "messages": [dict(message) for message in messages],
    }
    if tools:
        corps["tools"] = [dict(outil) for outil in tools]
    return corps


def _analyser_tool_calls(brut: Any) -> tuple[ToolCall, ...]:
    if not isinstance(brut, list):
        return ()
    appels: list[ToolCall] = []
    for entree in brut:
        if not isinstance(entree, dict):
            continue
        fonction = entree.get("function") or {}
        nom = str(fonction.get("name", ""))
        arguments = fonction.get("arguments")
        if isinstance(arguments, dict):
            appels.append(
                ToolCall(nom=nom, arguments=dict(arguments), identifiant=entree.get("id"))
            )
            continue
        texte = arguments if isinstance(arguments, str) else json.dumps(arguments)
        try:
            decode = json.loads(texte)
        except (json.JSONDecodeError, TypeError) as erreur:
            appels.append(
                ToolCall(
                    nom=nom,
                    identifiant=entree.get("id"),
                    arguments_bruts=texte,
                    erreur_arguments=f"arguments JSON invalides : {erreur}",
                )
            )
            continue
        if isinstance(decode, dict):
            appels.append(ToolCall(nom=nom, arguments=decode, identifiant=entree.get("id")))
        else:
            appels.append(
                ToolCall(
                    nom=nom,
                    identifiant=entree.get("id"),
                    arguments_bruts=texte,
                    erreur_arguments="arguments JSON valides mais non objet",
                )
            )
    return tuple(appels)


def analyser_corps_chat(reponse: ReponseHTTP) -> ChatResult:
    """Assemble un corps 2xx de `/api/chat` en `ChatResult` (§H4.3).

    Le corps admet DEUX formes : un objet JSON unique (réponse non streamée) ou
    une suite de lignes NDJSON (réponse streamée) — `content` et `reasoning` se
    concatènent, `tool_calls` se collectent, le fragment final `done: true` porte
    compteurs et durées. Un flux sans fragment final est une réponse tronquée :
    `TransportError`, retentée (§H4.5) ; un fragment portant `error` est une
    panne serveur en cours de flux : `ServerError`, retentée.
    """
    lignes = [ligne for ligne in reponse.body.splitlines() if ligne.strip()]
    if not lignes:
        raise ProtocolError(f"réponse HTTP {reponse.status} vide")
    fragments: list[dict[str, Any]] = []
    for indice, ligne in enumerate(lignes):
        try:
            charge = json.loads(ligne)
        except json.JSONDecodeError as erreur:
            if indice == 0:
                raise ProtocolError(
                    f"réponse HTTP {reponse.status} non JSON : {erreur}"
                ) from erreur
            raise TransportError(
                "flux interrompu : fragment JSON incomplet en fin de corps"
            ) from erreur
        if not isinstance(charge, dict):
            raise ProtocolError(f"réponse HTTP {reponse.status} : objet JSON attendu")
        if charge.get("error"):
            raise ServerError(
                f"erreur serveur en cours de flux : {charge['error']}", status=reponse.status
            )
        fragments.append(charge)
    if len(fragments) == 1:
        return analyser_reponse(fragments[0])
    if not fragments[-1].get("done"):
        raise TransportError("flux interrompu avant le fragment final (done absent)")
    return analyser_reponse(fusionner_fragments(fragments))


def fusionner_fragments(fragments: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Fusionne les fragments NDJSON d'un flux `/api/chat` en l'enveloppe de
    l'objet unique (§H4.3) : `content` et `reasoning` concaténés, `tool_calls`
    collectés, le fragment final porte compteurs, durées et `done_reason`.

    Seule implémentation de l'assemblage : le rejeu (§H4.7) la réutilise pour
    lire une cassette streamée sous la même forme que le client.
    """
    final = fragments[-1]
    contenu: list[str] = []
    raisonnement: list[str] = []
    appels: list[Any] = []
    for fragment in fragments:
        message = fragment.get("message")
        if not isinstance(message, dict):
            continue
        contenu.append(str(message.get("content") or ""))
        raisonnement.append(str(message.get("reasoning") or message.get("thinking") or ""))
        brut = message.get("tool_calls")
        if isinstance(brut, list):
            appels.extend(brut)
    fusion = dict(final)
    fusion["message"] = {
        "content": "".join(contenu),
        "reasoning": "".join(raisonnement),
        "tool_calls": appels,
    }
    return fusion


def analyser_reponse(charge: Mapping[str, Any]) -> ChatResult:
    """Normalise une réponse `/api/chat` en `ChatResult` (§H4.3)."""
    message = charge.get("message")
    if not isinstance(message, dict):
        raise ProtocolError("réponse sans objet « message » exploitable")
    return ChatResult(
        content=str(message.get("content") or ""),
        reasoning=str(message.get("reasoning") or message.get("thinking") or ""),
        tool_calls=_analyser_tool_calls(message.get("tool_calls")),
        done_reason=charge.get("done_reason"),
        prompt_eval_count=int(charge.get("prompt_eval_count") or 0),
        eval_count=int(charge.get("eval_count") or 0),
        total_duration_ms=int(charge.get("total_duration") or 0) // 1_000_000,
        prompt_eval_duration_ms=int(charge.get("prompt_eval_duration") or 0) // 1_000_000,
        eval_duration_ms=int(charge.get("eval_duration") or 0) // 1_000_000,
        modele=str(charge.get("model") or ""),
    )


class LLMClient:
    """Client d'inférence (§H4.1).

    `transport`, `dormir` et `alea` sont injectables : les tests éprouvent la
    politique de retry sans attendre réellement et sans réseau.
    """

    def __init__(
        self,
        config: Config,
        transport: Transport | None = None,
        dormir: Callable[[float], None] = time.sleep,
        alea: Callable[[], float] = random.random,
    ) -> None:
        self.config = config
        self._transport: Transport = transport or transport_urllib
        self._dormir = dormir
        self._alea = alea

    @property
    def url_chat(self) -> str:
        return f"{self.config.ollama_host}/api/chat"

    def _entetes(self) -> dict[str, str]:
        """En-têtes de la requête. La clé n'est JAMAIS journalisée (§H4.6)."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.ollama_api_key}",
        }

    def _attente(self, tentative: int) -> float:
        """Attente avec jitter borné à ±25 % (§H4.5)."""
        return attente(tentative, self._alea)

    def _classer(self, reponse: ReponseHTTP) -> ChatResult:
        if reponse.status in (401, 403):
            raise AuthError(
                f"authentification refusée par l'endpoint (HTTP {reponse.status}) — "
                "vérifier OLLAMA_API_KEY"
            )
        if reponse.status == 413:
            corps = self._corps_json(reponse, tolerant=True)
            raise ContextOverflow(
                str(corps.get("error") or "contexte de la requête trop grand"),
                tokens_estimated=_entier_ou_none(corps.get("tokens_estimated")),
                max_context_tokens=_entier_ou_none(corps.get("max_context_tokens")),
            )
        if reponse.status >= 500:
            raise ServerError(f"erreur serveur HTTP {reponse.status}", status=reponse.status)
        if reponse.status >= 400:
            corps = self._corps_json(reponse, tolerant=True)
            raise ProtocolError(
                f"requête refusée (HTTP {reponse.status}) : {corps.get('error') or 'sans détail'}"
            )
        return analyser_corps_chat(reponse)

    @staticmethod
    def _corps_json(reponse: ReponseHTTP, tolerant: bool) -> dict[str, Any]:
        try:
            charge = json.loads(reponse.body)
        except json.JSONDecodeError as erreur:
            if tolerant:
                return {}
            raise ProtocolError(f"réponse HTTP {reponse.status} non JSON : {erreur}") from erreur
        if not isinstance(charge, dict):
            if tolerant:
                return {}
            raise ProtocolError(f"réponse HTTP {reponse.status} : objet JSON attendu")
        return charge

    def _lire(self, chemin: str) -> dict[str, Any]:
        """GET authentifié sur une route de lecture (§H4.8).

        Sert la fumée manuelle : version du serveur et modèles servis. Ne passe pas
        par la politique de retry, une fumée devant échouer vite et clairement.
        """
        reponse = transport_urllib(
            f"{self.config.ollama_host}{chemin}", b"", self._entetes(), self.config.timeout_s, "GET"
        )
        if reponse.status in (401, 403):
            raise AuthError(f"authentification refusée sur {chemin} (HTTP {reponse.status})")
        if reponse.status >= 400:
            raise ProtocolError(f"{chemin} : HTTP {reponse.status}")
        return self._corps_json(reponse, tolerant=False)

    def version(self) -> str:
        """Version du serveur d'inférence (§H4.8)."""
        return str(self._lire("/api/version").get("version", ""))

    def modeles(self) -> list[str]:
        """Noms des modèles servis (§H4.8)."""
        charge = self._lire("/api/tags")
        modeles = charge.get("models")
        if not isinstance(modeles, list):
            return []
        return [str(entree.get("name", "")) for entree in modeles if isinstance(entree, dict)]

    def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] | None = None,
        *,
        num_ctx: int | None = None,
        num_predict: int | None = None,
        temperature: float | int | None = None,
    ) -> ChatResult:
        """Envoie un échange et rend la réponse normalisée (§H4.2, §H4.5).

        Retente uniquement les pannes serveur et de transport, jamais un refus 4xx.
        """
        corps = json.dumps(
            construire_corps(
                self.config,
                messages,
                tools,
                num_ctx=num_ctx,
                num_predict=num_predict,
                temperature=temperature,
            )
        ).encode()
        entetes = self._entetes()

        def tenter() -> ChatResult:
            debut = time.monotonic()
            reponse = self._transport(self.url_chat, corps, entetes, self.config.timeout_s)
            resultat = self._classer(reponse)
            _journal.info(
                "inférence aboutie",
                extra={"duree_s": round(time.monotonic() - debut, 3), **resultat.resume()},
            )
            return resultat

        return avec_retries(
            tenter,
            (ServerError, TransportError),
            dormir=self._dormir,
            alea=self._alea,
            journal=_journal,
        )


def _entier_ou_none(valeur: Any) -> int | None:
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None
