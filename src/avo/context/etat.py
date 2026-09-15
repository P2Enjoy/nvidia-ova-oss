"""État d'exécution structuré (SKILL.state) : Σ typé, patch validé par le runtime.

@spec docs/BACKLOG.md U26 — Spécification H15 et runtime d'état structuré ;
      U31 — schéma de Σ déclaré par le domaine (H15.9) ;
      U37 — patron ledger : genre `liste_taches`, champ `plan`, dérivation de
      schéma et remplacement curé (§H18.1, §H18.3)
@spec docs/SPEC_HARNAIS.md §H15.1 (contrat de pas, bloc JSON à deux clés),
      §H15.2 (opérateur ⊕, suppression par null), §H15.3 (schéma possédé par le
      runtime), §H15.4 (rollback-retry borné), §H15.5 (sérialisation aller-retour),
      §H15.6 (schéma ARC v1, défaut du noyau), §H15.9 (schéma déclaré par le
      domaine : genres génériques du noyau, champ commun `hypotheses`, fusion clé
      par clé du genre dictionnaire), §H16.1 (`hypotheses` ne se vide pas en
      cours de run), §H18.1 (genre `liste_taches` : fusion par `id`, statuts,
      borne et purge des terminales ; dérivation `+plan`)

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
CHAINE: Final = "chaine"
LISTE_CHAINES: Final = "liste_chaines"
LISTE_OBJETS: Final = "liste_objets"
LISTE_TACHES: Final = "liste_taches"
DICTIONNAIRE: Final = "dictionnaire"

#: Champ commun exigé de tout schéma (§H15.9) : la garde documentaire du mode
#: `state` (§H16.1) y lit l'artefact « ce que je sais ».
CHAMP_HYPOTHESES: Final = "hypotheses"

#: Champ du ledger (§H18.1), ajouté par DÉRIVATION (`avec_plan`) — jamais déclaré
#: par un domaine : le plan curé vaut pour toute tâche, pas pour un schéma.
CHAMP_PLAN: Final = "plan"

#: Statuts admis d'une tâche du ledger (§H18.1) : la discipline de curation GVS5H
#: imposée par la structure — une tâche ne se retire pas, elle se clôt ou s'écarte.
STATUTS_TACHE: Final = ("a_faire", "en_cours", "fait", "ecartee")
STATUTS_TERMINAUX: Final = frozenset({"fait", "ecartee"})

#: Borne du ledger (§H18.1) : le papier amorce 3–6 tâches et borne les fichiers du
#: workspace (scaffold v2, §3). Au-delà, les terminales les plus anciennes sont
#: purgées ; des ouvertes seules au-delà de la borne refusent le patch.
PLAN_TACHES_MAX: Final = 12

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


def _valider_chaine(nom: str, valeur: Any) -> None:
    """Scalaire textuel (§H15.9, genre `chaine`) : le `working_dir` de la source."""
    if not isinstance(valeur, str):
        raise EtatInvalide(f"{nom} : chaîne attendue, reçue {valeur!r}")


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


def _valider_entree_tache(nom: str, index: int, tache: Any, complete: bool) -> None:
    """Une entrée de tâche du ledger (§H18.1) : `id` toujours ; le reste selon le cas.

    `complete` vrai = la tâche doit porter `description` et `statut` (tâche
    NOUVELLE, ou valeur entière du champ — Σ, sérialisation, remplacement curé) ;
    faux = patch d'une tâche EXISTANTE, fusion champ à champ : les clés fournies
    seules sont validées, les absentes sont conservées — clore s'écrit
    `{id, statut}` seul (mesure `u38-depot-s2`).
    """
    if not isinstance(tache, Mapping) or "id" not in tache:
        raise EtatInvalide(f"{nom}[{index}] : dict avec au moins « id » attendu, reçu {tache!r}")
    if not isinstance(tache["id"], str) or not tache["id"]:
        raise EtatInvalide(f"{nom}[{index}].id : chaîne non vide attendue")
    if complete and not {"description", "statut"} <= set(tache):
        raise EtatInvalide(
            f"{nom}[{index}] : tâche nouvelle « {tache['id']} » — « description » et "
            f"« statut » requis, reçu {tache!r}"
        )
    if "description" in tache and not isinstance(tache["description"], str):
        raise EtatInvalide(f"{nom}[{index}].description : chaîne attendue")
    if "statut" in tache and tache["statut"] not in STATUTS_TACHE:
        raise EtatInvalide(
            f"{nom}[{index}].statut : l'un de {list(STATUTS_TACHE)} attendu, "
            f"reçu {tache['statut']!r}"
        )


def _valider_liste_taches(nom: str, valeur: Any) -> None:
    """Tâches du ledger (§H18.1), forme COMPLÈTE : `id`, `description`, `statut`.

    C'est la forme du champ dans Σ, de sa sérialisation et du remplacement curé
    (H18.3). La fusion d'un patch (§H18.1) valide ses entrées elle-même, champ à
    champ selon que l'`id` existe — voir `Etat.fusionner`.
    """
    if not isinstance(valeur, (list, tuple)):
        raise EtatInvalide(f"{nom} : liste de tâches attendue, reçue {valeur!r}")
    vus: set[str] = set()
    for index, tache in enumerate(valeur):
        _valider_entree_tache(nom, index, tache, complete=True)
        if tache["id"] in vus:
            raise EtatInvalide(f"{nom} : tâche « {tache['id']} » présente deux fois")
        vus.add(tache["id"])


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
    CHAINE: _valider_chaine,
    LISTE_CHAINES: _valider_liste_chaines,
    LISTE_OBJETS: _valider_liste_objets,
    LISTE_TACHES: _valider_liste_taches,
    DICTIONNAIRE: _valider_dictionnaire,
}

#: Défaut de chaque genre, appliqué à l'ouverture de Σ et sur `null` (§H15.2).
_DEFAUTS_GENRE: Final[Mapping[str, Any]] = MappingProxyType(
    {
        POSITION: None,
        ENTIER_POSITIF: 1,
        CHAINE: "",
        LISTE_CHAINES: (),
        LISTE_OBJETS: (),
        LISTE_TACHES: (),
        DICTIONNAIRE: MappingProxyType({}),
    }
)

#: Forme de chaque genre, telle que le protocole la cite au modèle (§H15.8, §H15.9).
FORMES: Final[Mapping[str, str]] = MappingProxyType(
    {
        POSITION: '{"x": int, "y": int} ou null',
        ENTIER_POSITIF: "entier ≥ 1",
        CHAINE: "chaîne de caractères",
        LISTE_CHAINES: "liste de chaînes",
        LISTE_OBJETS: "liste d'objets avec au moins « id » et « description »",
        LISTE_TACHES: "liste de tâches {id, description, statut}, fusionnée par id",
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


def _borner_taches(nom: str, taches: list[Any]) -> tuple[list[Any], tuple[str, ...]]:
    """Applique la borne du ledger (§H18.1) : purge des terminales, refus sinon.

    Au-delà de `PLAN_TACHES_MAX`, les tâches TERMINALES (`fait`, `ecartee`) les
    plus anciennes sont purgées jusqu'à la borne — la purge est rendue à
    l'appelant pour être NOMMÉE (archive du pas, §H15.10 ; métrique de curation,
    §H18.5), jamais silencieuse. Si les tâches OUVERTES dépassent à elles seules
    la borne, le patch est refusé : la seule issue est de curer réellement.
    """
    if len(taches) <= PLAN_TACHES_MAX:
        return taches, ()
    ouvertes = sum(1 for tache in taches if tache["statut"] not in STATUTS_TERMINAUX)
    if ouvertes > PLAN_TACHES_MAX:
        raise EtatInvalide(
            f"{nom} : {ouvertes} tâches ouvertes pour une borne de {PLAN_TACHES_MAX} — "
            "fusionne les doublons ou écarte le périmé (statuts « fait »/« ecartee »)"
        )
    purgees: list[str] = []
    bornees: list[Any] = list(taches)
    for tache in taches:
        if len(bornees) <= PLAN_TACHES_MAX:
            break
        if tache["statut"] in STATUTS_TERMINAUX:
            bornees.remove(tache)
            purgees.append(tache["id"])
    return bornees, tuple(purgees)


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
            # run — le vidage (liste vide ou `null`) est SANS EFFET sur le champ,
            # le reste du patch s'applique. Refuser le patch entier en
            # `EtatInvalide` faisait mourir des runs en `RetriesEpuises` : dans un
            # mode sans mémoire, la relance n'enseigne rien d'un tour à l'autre.
            # L'ouverture (vide → vide) reste permise.
            if cle == CHAMP_HYPOTHESES and nouveaux[cle] and valeur in (None, [], ()):
                continue
            if valeur is None:
                nouveaux[cle] = _figer(_DEFAUTS_GENRE[champ.genre])
                continue
            if champ.genre == LISTE_TACHES:
                # §H18.1 : fusion par `id`, CHAMP À CHAMP — une tâche existante
                # reçoit les clés fournies et garde les absentes (clore s'écrit
                # `{id, statut}` seul — mesure u38-depot-s2 : exiger la tâche
                # complète recréait la réémission que la fusion doit éviter) ;
                # une tâche nouvelle s'ajoute, complète ; une absente reste.
                # Le modèle ne retire jamais une tâche : il la clôt ou l'écarte.
                if not isinstance(valeur, (list, tuple)):
                    raise EtatInvalide(f"{cle} : liste de tâches attendue, reçue {valeur!r}")
                taches = [dict(_degeler(tache)) for tache in nouveaux[cle]]
                index_par_id = {tache["id"]: rang for rang, tache in enumerate(taches)}
                vus: set[str] = set()
                for index, tache in enumerate(valeur):
                    if (
                        not isinstance(tache, Mapping)
                        or not isinstance(tache.get("id"), str)
                        or not tache.get("id")
                    ):
                        # Sans `id` lisible, l'entrée est invalide quelle que
                        # soit sa nature : le message complet la nomme.
                        _valider_entree_tache(cle, index, tache, complete=True)
                    ident = str(tache["id"])
                    if ident in vus:
                        raise EtatInvalide(f"{cle} : tâche « {ident} » présente deux fois")
                    vus.add(ident)
                    rang = index_par_id.get(ident)
                    _valider_entree_tache(cle, index, tache, complete=rang is None)
                    if rang is None:
                        taches.append(dict(tache))
                        index_par_id[ident] = len(taches) - 1
                    else:
                        taches[rang] = {**taches[rang], **dict(tache)}
                bornees, _purgees = _borner_taches(cle, taches)
                nouveaux[cle] = _figer(bornees)
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


#: Rôle du champ `plan`, cité par le protocole engendré (§H15.9, §H18.1). Fixé par
#: le noyau : le ledger vaut pour tout domaine, aucun schéma ne le déclare.
ROLE_PLAN: Final = "ton plan de travail, curé"


def avec_plan(schema: SchemaEtat) -> SchemaEtat:
    """Dérive le schéma effectif du ledger (§H18.1) : les champs déclarés + `plan`.

    Le schéma dérivé se nomme `<nom>+plan`. Un schéma qui déclare déjà un champ
    `plan` est refusé — jamais silencieusement écrasé. À interrupteur inactif,
    l'appelant garde le schéma déclaré : protocole et cassettes inchangés.
    """
    if schema.champ(CHAMP_PLAN) is not None:
        raise SchemaInvalide(
            f"schéma {schema.nom} : le champ « {CHAMP_PLAN} » est réservé à la "
            "dérivation du ledger (§H18.1) — un domaine ne le déclare jamais"
        )
    return SchemaEtat(
        f"{schema.nom}+{CHAMP_PLAN}",
        schema.champs + (ChampEtat(CHAMP_PLAN, LISTE_TACHES, ROLE_PLAN),),
    )


def remplacer_taches(etat: Etat, taches: Any) -> tuple[Etat, tuple[str, ...]]:
    """Remplace le ledger ENTIER par une liste curée (§H18.3) — le geste de manager.

    C'est le remplacement qui permet de fusionner les doublons, ce que la fusion
    par `id` du patch d'acteur ne peut pas faire. La liste est validée comme
    n'importe quelle valeur `liste_taches` (genre, statuts, borne — purge des
    terminales rendue à l'appelant pour être nommée) ; aucun autre champ n'est
    touché. Lève `EtatInvalide` nommée sur toute liste invalide, sans modifier
    `etat`.
    """
    champ = etat.schema.champ(CHAMP_PLAN)
    if champ is None or champ.genre != LISTE_TACHES:
        raise EtatInvalide(
            f"« {CHAMP_PLAN} » : le schéma {etat.schema.nom} ne porte pas le ledger "
            "(§H18.1) — la curation exige un schéma dérivé par avec_plan"
        )
    _valider_liste_taches(CHAMP_PLAN, taches)
    bornees, purgees = _borner_taches(CHAMP_PLAN, [dict(tache) for tache in taches])
    nouveaux = dict(etat.champs)
    nouveaux[CHAMP_PLAN] = _figer(bornees)
    return Etat(champs=MappingProxyType(nouveaux), schema=etat.schema), purgees


def taches_purgees(avant: Etat, patch: Mapping[str, Any], apres: Etat) -> tuple[str, ...]:
    """Les `id` purgés par la borne lors d'une fusion (§H18.1), pour l'archive du pas.

    Purgés = présents avant ou apportés par le patch, absents après. Calcul pur,
    sans canal de sortie caché dans `fusionner` : l'appelant compare les états
    qu'il détient déjà.
    """
    champ = avant.schema.champ(CHAMP_PLAN)
    if champ is None or champ.genre != LISTE_TACHES or CHAMP_PLAN not in patch:
        return ()
    valeur_patch = patch[CHAMP_PLAN]
    if not isinstance(valeur_patch, (list, tuple)):
        # `null` réinitialise le champ (§H15.2) : un choix explicite du modèle,
        # pas une purge de borne — rien à nommer ici.
        return ()
    ids_patch = {tache["id"] for tache in valeur_patch}
    ids_avant = {tache["id"] for tache in avant.champs[CHAMP_PLAN]}
    ids_apres = {tache["id"] for tache in apres.champs[CHAMP_PLAN]}
    return tuple(sorted((ids_avant | ids_patch) - ids_apres))
