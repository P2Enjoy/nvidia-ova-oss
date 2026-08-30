"""État d'exécution structuré (SKILL.state) : Σ typé, patch validé par le runtime.

@spec docs/BACKLOG.md U26 — Spécification H15 et runtime d'état structuré
@spec docs/SPEC_HARNAIS.md §H15.1 (contrat de pas, bloc JSON à deux clés),
      §H15.2 (opérateur ⊕, suppression par null), §H15.3 (schéma possédé par le
      runtime), §H15.4 (rollback-retry borné), §H15.5 (sérialisation aller-retour),
      §H15.6 (schéma ARC v1)

Module **pur** : aucune entrée-sortie, aucun réseau, aucun appel LLM. Il reçoit un
état et un texte de modèle, et rend soit un nouvel état et une action, soit une
erreur typée nommant le champ ou le défaut précis — jamais un état partiellement
appliqué (CLAUDE.md §18). Le branchement dans la boucle agent (relecture du texte du
modèle, nouvelle tentative sur échec) est le périmètre de U27, pas de ce module.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

#: Nombre de tentatives de patch autorisées pour un même pas avant l'erreur fatale
#: (§H15.4) — même principe que les deux 413 consécutifs de §H5.4 : jamais une boucle.
RETRIES_MAX: Final = 3

#: Schéma ARC v1 (§H15.6) : quatre champs fixes, toujours présents dans Σ. La valeur
#: associée à chaque champ est son défaut, appliqué à l'ouverture et sur `null`.
_DEFAUTS_ARC_V1: Final[Mapping[str, Any]] = MappingProxyType(
    {
        "position": None,
        "essai": 1,
        "hypotheses": (),
        "objets": (),
    }
)

_BLOC_JSON: Final = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


class EtatInvalide(ValueError):
    """Le patch viole le schéma ARC v1 : le message nomme toujours le champ fautif."""


class PatchMalforme(ValueError):
    """La réponse du modèle n'est pas un bloc ```json à deux clés `state_patch`/`action`."""


class RetriesEpuises(RuntimeError):
    """Le budget de tentatives de patch est épuisé sans qu'aucune n'ait été valide (§H15.4)."""


def _est_entier_strict(valeur: Any) -> bool:
    """`bool` est une sous-classe d'`int` en Python : jamais un entier valable ici."""
    return isinstance(valeur, int) and not isinstance(valeur, bool)


def _valider_position(valeur: Any) -> None:
    if valeur is None:
        return
    if not isinstance(valeur, Mapping) or set(valeur) != {"x", "y"}:
        raise EtatInvalide(f'position : {{"x": int, "y": int}} ou null attendu, reçu {valeur!r}')
    for cle in ("x", "y"):
        if not _est_entier_strict(valeur[cle]):
            raise EtatInvalide(f"position.{cle} : entier attendu, reçu {valeur[cle]!r}")


def _valider_essai(valeur: Any) -> None:
    if not _est_entier_strict(valeur) or valeur < 1:
        raise EtatInvalide(f"essai : entier ≥ 1 attendu, reçu {valeur!r}")


def _valider_hypotheses(valeur: Any) -> None:
    if not isinstance(valeur, (list, tuple)) or not all(isinstance(item, str) for item in valeur):
        raise EtatInvalide(f"hypotheses : liste de chaînes attendue, reçue {valeur!r}")


def _valider_objets(valeur: Any) -> None:
    if not isinstance(valeur, (list, tuple)):
        raise EtatInvalide(f"objets : liste attendue, reçue {valeur!r}")
    for index, objet in enumerate(valeur):
        if not isinstance(objet, Mapping) or "id" not in objet or "description" not in objet:
            raise EtatInvalide(
                f"objets[{index}] : dict avec au moins « id » et « description » attendu, "
                f"reçu {objet!r}"
            )
        if not isinstance(objet["id"], str) or not isinstance(objet["description"], str):
            raise EtatInvalide(
                f"objets[{index}] : « id » et « description » doivent être des chaînes"
            )


_VALIDATEURS: Final = {
    "position": _valider_position,
    "essai": _valider_essai,
    "hypotheses": _valider_hypotheses,
    "objets": _valider_objets,
}


def _figer(valeur: Any) -> Any:
    """Convertit récursivement listes/dicts en tuples/mappings immuables."""
    if isinstance(valeur, Mapping):
        return MappingProxyType({cle: _figer(sous_valeur) for cle, sous_valeur in valeur.items()})
    if isinstance(valeur, (list, tuple)):
        return tuple(_figer(element) for element in valeur)
    return valeur


def _degeler(valeur: Any) -> Any:
    """Inverse de `_figer` : mappings/tuples immuables vers dict/list JSON-sérialisables."""
    if isinstance(valeur, Mapping):
        return {cle: _degeler(sous_valeur) for cle, sous_valeur in valeur.items()}
    if isinstance(valeur, tuple):
        return [_degeler(element) for element in valeur]
    return valeur


@dataclass(frozen=True, slots=True)
class Etat:
    """Σ : état d'exécution structuré, toujours conforme au schéma ARC v1 (§H15.6)."""

    champs: Mapping[str, Any]

    @classmethod
    def initial(cls) -> Etat:
        """Σ₀ : les quatre champs du schéma à leur défaut."""
        return cls(champs=_figer(_DEFAUTS_ARC_V1))

    def fusionner(self, patch: Mapping[str, Any]) -> Etat:
        """Σₜ₊₁ = Σₜ ⊕ ΔΣₜ (§H15.2). Rend un NOUVEL état ; ne mute jamais celui-ci.

        Une clé absente du patch laisse le champ correspondant inchangé. Une clé
        présente avec `null` réinitialise le champ à son défaut plutôt que de le
        retirer : Σ reste toujours conforme à son schéma. Un patch qui échoue à la
        validation n'atteint jamais Σ (§H15.3) : soit l'état rendu est complet et
        valide, soit une exception est levée et `self` reste inchangé.
        """
        for cle in patch:
            if cle not in _DEFAUTS_ARC_V1:
                raise EtatInvalide(
                    f"« {cle} » : clé inconnue du schéma arc-v1 ({sorted(_DEFAUTS_ARC_V1)})"
                )
        nouveaux = dict(self.champs)
        for cle, valeur in patch.items():
            if valeur is None:
                nouveaux[cle] = _figer(_DEFAUTS_ARC_V1[cle])
                continue
            _VALIDATEURS[cle](valeur)
            nouveaux[cle] = _figer(valeur)
        return Etat(champs=MappingProxyType(nouveaux))

    def en_dict(self) -> dict[str, Any]:
        """Forme sérialisable : dict/list ordinaires, sans mapping ni tuple figés."""
        return {cle: _degeler(valeur) for cle, valeur in self.champs.items()}

    def vers_json(self) -> str:
        """Sérialisation persistée dans le workspace du run (§H15.5)."""
        return json.dumps(self.en_dict(), sort_keys=True, ensure_ascii=False)

    @classmethod
    def depuis_dict(cls, donnees: Mapping[str, Any]) -> Etat:
        """Reconstruit un état depuis sa forme sérialisée, en le validant (§H15.5)."""
        return cls.initial().fusionner(dict(donnees))

    @classmethod
    def depuis_json(cls, texte: str) -> Etat:
        """Inverse de `vers_json` : aller-retour à l'identique (§H15.5)."""
        try:
            donnees = json.loads(texte)
        except json.JSONDecodeError as erreur:
            raise EtatInvalide(f"état sérialisé illisible : {erreur}") from erreur
        if not isinstance(donnees, Mapping):
            raise EtatInvalide(f"état sérialisé : objet JSON attendu, reçu {donnees!r}")
        return cls.depuis_dict(donnees)


@dataclass(frozen=True, slots=True)
class Pas:
    """Sortie d'un tour en mode `state` (§H15.1) : patch et action, sans le raisonnement."""

    patch: Mapping[str, Any]
    action: str


def decoder_pas(texte: str) -> Pas:
    """Extrait `(state_patch, action)` du bloc JSON attendu (annexe A.4 SKILL.state).

    Le raisonnement qui précède le bloc n'est jamais retourné : il est déjà jeté à ce
    stade (§H15.1). Toute déviation du contrat — bloc absent, JSON illisible, clés
    manquantes ou en trop, types incorrects — lève `PatchMalforme` en la nommant.
    """
    correspondance = _BLOC_JSON.search(texte)
    if correspondance is None:
        raise PatchMalforme(
            "aucun bloc ```json contenant « state_patch »/« action » dans la réponse : "
            f"{texte[:200]!r}"
        )
    try:
        bloc = json.loads(correspondance.group(1))
    except json.JSONDecodeError as erreur:
        raise PatchMalforme(f"bloc JSON illisible : {erreur}") from erreur
    if not isinstance(bloc, Mapping) or set(bloc) != {"state_patch", "action"}:
        cles = sorted(bloc) if isinstance(bloc, Mapping) else bloc
        raise PatchMalforme(
            "le bloc JSON doit avoir exactement les clés « state_patch » et « action », "
            f"reçu {cles!r}"
        )
    patch, action = bloc["state_patch"], bloc["action"]
    if not isinstance(patch, Mapping):
        raise PatchMalforme(f"« state_patch » : objet attendu, reçu {patch!r}")
    if not isinstance(action, str) or not action:
        raise PatchMalforme(f"« action » : chaîne non vide attendue, reçue {action!r}")
    return Pas(patch=patch, action=action)


def appliquer(etat: Etat, texte: str) -> tuple[Etat, str]:
    """Décode puis fusionne un pas : rend `(Σₜ₊₁, action)`.

    Lève `PatchMalforme` ou `EtatInvalide` sur tout écart au contrat, sans jamais
    modifier `etat`. Ne gère PAS la nouvelle tentative : c'est au tour de la boucle
    (U27) de rejouer l'appel LLM sur échec, budgété par `CompteurRetries` — ce module
    reste sans effet de bord et ne connaît rien du client d'inférence.
    """
    pas = decoder_pas(texte)
    return etat.fusionner(pas.patch), pas.action


@dataclass(frozen=True, slots=True)
class CompteurRetries:
    """Budget de tentatives de patch restant pour le pas courant (§H15.4)."""

    plafond: int = RETRIES_MAX
    consommees: int = 0

    @property
    def epuise(self) -> bool:
        return self.consommees >= self.plafond

    def echec(self) -> CompteurRetries:
        """Consomme une tentative après un patch refusé. Rend un NOUVEAU compteur.

        Lève `RetriesEpuises` si le budget était déjà épuisé : l'appelant doit tester
        `epuise` avant de retenter, jamais découvrir l'épuisement après coup.
        """
        if self.epuise:
            raise RetriesEpuises(
                f"{self.plafond} tentative(s) de patch épuisée(s) sans état valide (§H15.4)"
            )
        return CompteurRetries(plafond=self.plafond, consommees=self.consommees + 1)
