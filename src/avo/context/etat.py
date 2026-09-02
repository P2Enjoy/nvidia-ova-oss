"""État d'exécution structuré (SKILL.state) : Σ typé, patch validé par le runtime.

@spec docs/BACKLOG.md U26 — Spécification H15 et runtime d'état structuré ;
      U31 — schéma de Σ déclaré par le domaine (H15.9)
@spec docs/SPEC_HARNAIS.md §H15.1 (contrat de pas, bloc JSON à deux clés),
      §H15.2 (opérateur ⊕, suppression par null), §H15.3 (schéma possédé par le
      runtime), §H15.4 (rollback-retry borné), §H15.5 (sérialisation aller-retour),
      §H15.6 (schéma ARC v1, défaut du noyau), §H15.9 (schéma déclaré par le
      domaine : genres génériques du noyau, champ commun `hypotheses`, fusion clé
      par clé du genre dictionnaire), §H16.1 (`hypotheses` ne se vide pas en
      cours de run)

Module **pur** : aucune entrée-sortie, aucun réseau, aucun appel LLM. Il reçoit un
état et un texte de modèle, et rend soit un nouvel état et une action, soit une
erreur typée nommant le champ ou le défaut précis — jamais un état partiellement
appliqué (CLAUDE.md §18). Le branchement dans la boucle agent (relecture du texte du
modèle, nouvelle tentative sur échec) est le périmètre de U27, pas de ce module.

Le noyau possède les GENRES de champ et leur validation ; la LISTE des champs est
une donnée du domaine (§H15.9), `arc-v1` restant le défaut sans déclaration.
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

#: Genres de champ du noyau (§H15.9) : les seuls validateurs qui existent. Un domaine
#: compose son schéma avec eux, jamais avec un validateur à lui.
POSITION: Final = "position"
ENTIER_POSITIF: Final = "entier_positif"
LISTE_CHAINES: Final = "liste_chaines"
LISTE_OBJETS: Final = "liste_objets"
DICTIONNAIRE: Final = "dictionnaire"

#: Champ commun exigé de tout schéma (§H15.9) : la garde documentaire du mode
#: `state` (§H16.1) y lit l'artefact « ce que je sais ».
CHAMP_HYPOTHESES: Final = "hypotheses"

_BLOC_JSON: Final = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


class EtatInvalide(ValueError):
    """Le patch viole le schéma de Σ : le message nomme toujours le champ fautif."""


class PatchMalforme(ValueError):
    """La réponse du modèle n'est pas un bloc ```json à deux clés `state_patch`/`action`."""


class RetriesEpuises(RuntimeError):
    """Le budget de tentatives de patch est épuisé sans qu'aucune n'ait été valide (§H15.4)."""


class SchemaInvalide(ValueError):
    """Le schéma déclaré viole les exigences du noyau (§H15.9) : le message dit laquelle."""


def _est_entier_strict(valeur: Any) -> bool:
    """`bool` est une sous-classe d'`int` en Python : jamais un entier valable ici."""
    return isinstance(valeur, int) and not isinstance(valeur, bool)


def _valider_position(nom: str, valeur: Any) -> None:
    if valeur is None:
        return
    if not isinstance(valeur, Mapping) or set(valeur) != {"x", "y"}:
        raise EtatInvalide(f'{nom} : {{"x": int, "y": int}} ou null attendu, reçu {valeur!r}')
    for cle in ("x", "y"):
        if not _est_entier_strict(valeur[cle]):
            raise EtatInvalide(f"{nom}.{cle} : entier attendu, reçu {valeur[cle]!r}")


def _valider_entier_positif(nom: str, valeur: Any) -> None:
    if not _est_entier_strict(valeur) or valeur < 1:
        raise EtatInvalide(f"{nom} : entier ≥ 1 attendu, reçu {valeur!r}")


def _valider_liste_chaines(nom: str, valeur: Any) -> None:
    if not isinstance(valeur, (list, tuple)) or not all(isinstance(item, str) for item in valeur):
        raise EtatInvalide(f"{nom} : liste de chaînes attendue, reçue {valeur!r}")


def _valider_liste_objets(nom: str, valeur: Any) -> None:
    if not isinstance(valeur, (list, tuple)):
        raise EtatInvalide(f"{nom} : liste attendue, reçue {valeur!r}")
    for index, objet in enumerate(valeur):
        if not isinstance(objet, Mapping) or "id" not in objet or "description" not in objet:
            raise EtatInvalide(
                f"{nom}[{index}] : dict avec au moins « id » et « description » attendu, "
                f"reçu {objet!r}"
            )
        if not isinstance(objet["id"], str) or not isinstance(objet["description"], str):
            raise EtatInvalide(
                f"{nom}[{index}] : « id » et « description » doivent être des chaînes"
            )


def _valider_dictionnaire(nom: str, valeur: Any) -> None:
    """Objet clé → valeur JSON (§H15.9) : clés chaînes, valeurs sérialisables."""
    if not isinstance(valeur, Mapping):
        raise EtatInvalide(f"{nom} : objet clé → valeur attendu, reçu {valeur!r}")
    for cle, sous_valeur in valeur.items():
        if not isinstance(cle, str):
            raise EtatInvalide(f"{nom} : clé chaîne attendue, reçue {cle!r}")
        try:
            json.dumps(sous_valeur)
        except (TypeError, ValueError) as erreur:
            raise EtatInvalide(
                f"{nom}.{cle} : valeur JSON attendue, reçue {sous_valeur!r}"
            ) from erreur


_VALIDATEURS: Final = {
    POSITION: _valider_position,
    ENTIER_POSITIF: _valider_entier_positif,
    LISTE_CHAINES: _valider_liste_chaines,
    LISTE_OBJETS: _valider_liste_objets,
    DICTIONNAIRE: _valider_dictionnaire,
}

#: Défaut de chaque genre, appliqué à l'ouverture de Σ et sur `null` (§H15.2).
_DEFAUTS_GENRE: Final[Mapping[str, Any]] = MappingProxyType(
    {
        POSITION: None,
        ENTIER_POSITIF: 1,
        LISTE_CHAINES: (),
        LISTE_OBJETS: (),
        DICTIONNAIRE: MappingProxyType({}),
    }
)

#: Forme de chaque genre, telle que le protocole la cite au modèle (§H15.8, §H15.9).
FORMES: Final[Mapping[str, str]] = MappingProxyType(
    {
        POSITION: '{"x": int, "y": int} ou null',
        ENTIER_POSITIF: "entier ≥ 1",
        LISTE_CHAINES: "liste de chaînes",
        LISTE_OBJETS: "liste d'objets avec au moins « id » et « description »",
        DICTIONNAIRE: "objet clé → valeur, fusionné clé par clé",
    }
)


@dataclass(frozen=True)
class ChampEtat:
    """Un champ de Σ : son nom, son genre du noyau, et le rôle que le protocole cite.

    `role` vide pour le schéma ARC v1 (§H15.6) : ses champs se suffisent.
    """

    nom: str
    genre: str
    role: str = ""


@dataclass(frozen=True)
class SchemaEtat:
    """Schéma de Σ, déclaré une fois par domaine (§H15.9), validé ici à sa construction."""

    nom: str
    champs: tuple[ChampEtat, ...]

    def __post_init__(self) -> None:
        if not self.nom:
            raise SchemaInvalide("schéma de Σ : nom vide")
        if not self.champs:
            raise SchemaInvalide(f"schéma {self.nom} : aucun champ déclaré")
        vus: set[str] = set()
        for champ in self.champs:
            if champ.genre not in _VALIDATEURS:
                raise SchemaInvalide(
                    f"schéma {self.nom}, champ « {champ.nom} » : genre inconnu "
                    f"{champ.genre!r} (genres du noyau : {sorted(_VALIDATEURS)})"
                )
            if champ.nom in vus:
                raise SchemaInvalide(f"schéma {self.nom} : champ « {champ.nom} » déclaré deux fois")
            vus.add(champ.nom)
        commun = self.champ(CHAMP_HYPOTHESES)
        if commun is None or commun.genre != LISTE_CHAINES:
            raise SchemaInvalide(
                f"schéma {self.nom} : le champ commun « {CHAMP_HYPOTHESES} » "
                f"({LISTE_CHAINES}) est obligatoire (§H15.9, §H16.1)"
            )

    @property
    def noms(self) -> tuple[str, ...]:
        return tuple(champ.nom for champ in self.champs)

    def champ(self, nom: str) -> ChampEtat | None:
        for champ in self.champs:
            if champ.nom == nom:
                return champ
        return None

    def defauts(self) -> dict[str, Any]:
        """Σ₀ du schéma : chaque champ à son défaut de genre."""
        return {champ.nom: _DEFAUTS_GENRE[champ.genre] for champ in self.champs}


#: Schéma ARC v1 (§H15.6) : quatre champs fixes, défaut du noyau sans déclaration.
ARC_V1: Final = SchemaEtat(
    "arc-v1",
    (
        ChampEtat("position", POSITION),
        ChampEtat("essai", ENTIER_POSITIF),
        ChampEtat(CHAMP_HYPOTHESES, LISTE_CHAINES),
        ChampEtat("objets", LISTE_OBJETS),
    ),
)


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
    """Σ : état d'exécution structuré, toujours conforme à son schéma (§H15.6, §H15.9)."""

    champs: Mapping[str, Any]
    schema: SchemaEtat = ARC_V1

    @classmethod
    def initial(cls, schema: SchemaEtat = ARC_V1) -> Etat:
        """Σ₀ : les champs du schéma à leur défaut."""
        return cls(champs=_figer(schema.defauts()), schema=schema)

    def fusionner(self, patch: Mapping[str, Any]) -> Etat:
        """Σₜ₊₁ = Σₜ ⊕ ΔΣₜ (§H15.2). Rend un NOUVEL état ; ne mute jamais celui-ci.

        Une clé absente du patch laisse le champ correspondant inchangé. Une clé
        présente avec `null` réinitialise le champ à son défaut plutôt que de le
        retirer : Σ reste toujours conforme à son schéma. Un champ de genre
        dictionnaire fusionne CLÉ PAR CLÉ (§H15.9) : entrée remplacée, retirée sur
        `null`, laissée si absente. Un patch qui échoue à la validation n'atteint
        jamais Σ (§H15.3) : soit l'état rendu est complet et valide, soit une
        exception est levée et `self` reste inchangé.
        """
        for cle in patch:
            if self.schema.champ(cle) is None:
                raise EtatInvalide(
                    f"« {cle} » : clé inconnue du schéma {self.schema.nom} "
                    f"({sorted(self.schema.noms)})"
                )
        nouveaux = dict(self.champs)
        for cle, valeur in patch.items():
            champ = self.schema.champ(cle)
            assert champ is not None
            # §H16.1 : le champ commun `hypotheses` ne se vide pas en cours de
            # run — une hypothèse périmée se remplace par sa révision. Vider par
            # liste vide ou par `null` réarmait la garde documentaire au pas
            # suivant (mesuré : jusqu'à 11 refus sur 25 appels d'un même run).
            # L'ouverture (vide → vide) reste permise.
            if cle == CHAMP_HYPOTHESES and nouveaux[cle] and valeur in (None, [], ()):
                raise EtatInvalide(
                    f"« {CHAMP_HYPOTHESES} » : ce champ ne se vide pas — remplace ou "
                    "révise tes hypothèses au lieu de les retirer (§H16.1)"
                )
            if valeur is None:
                nouveaux[cle] = _figer(_DEFAUTS_GENRE[champ.genre])
                continue
            _VALIDATEURS[champ.genre](cle, valeur)
            if champ.genre == DICTIONNAIRE:
                fusion = dict(nouveaux[cle])
                for sous_cle, sous_valeur in valeur.items():
                    if sous_valeur is None:
                        fusion.pop(sous_cle, None)
                    else:
                        fusion[sous_cle] = _figer(sous_valeur)
                nouveaux[cle] = MappingProxyType(fusion)
            else:
                nouveaux[cle] = _figer(valeur)
        return Etat(champs=MappingProxyType(nouveaux), schema=self.schema)

    def en_dict(self) -> dict[str, Any]:
        """Forme sérialisable : dict/list ordinaires, sans mapping ni tuple figés."""
        return {cle: _degeler(valeur) for cle, valeur in self.champs.items()}

    def vers_json(self) -> str:
        """Sérialisation persistée dans le workspace du run (§H15.5)."""
        return json.dumps(self.en_dict(), sort_keys=True, ensure_ascii=False)

    @classmethod
    def depuis_dict(cls, donnees: Mapping[str, Any], schema: SchemaEtat = ARC_V1) -> Etat:
        """Reconstruit un état depuis sa forme sérialisée, en le validant (§H15.5)."""
        return cls.initial(schema).fusionner(dict(donnees))

    @classmethod
    def depuis_json(cls, texte: str, schema: SchemaEtat = ARC_V1) -> Etat:
        """Inverse de `vers_json` : aller-retour à l'identique (§H15.5), sous le
        schéma qui a produit l'état (§H15.9)."""
        try:
            donnees = json.loads(texte)
        except json.JSONDecodeError as erreur:
            raise EtatInvalide(f"état sérialisé illisible : {erreur}") from erreur
        if not isinstance(donnees, Mapping):
            raise EtatInvalide(f"état sérialisé : objet JSON attendu, reçu {donnees!r}")
        return cls.depuis_dict(donnees, schema)


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
