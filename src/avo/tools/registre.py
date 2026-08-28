"""Registre d'outils : déclaration, exposition au modèle, routage des appels.

@spec docs/BACKLOG.md U12 — Registre d'outils et dispatch
@spec docs/SPEC_HARNAIS.md §H7.1 (registre, outils selon l'état de la boucle),
      §H7.2 (exécution séquentielle, message `role: tool`, garde par tour),
      §H7.4 (erreurs d'outil rendues au modèle), §H5.1 (transcript append-only)

Principe directeur : **rien de ce que fait un outil ne doit pouvoir interrompre le
run**. Un nom inconnu, des arguments malformés, une fonction qui lève — tout revient
au modèle sous forme de texte diagnostiquable, pour qu'il se corrige au tour suivant.
Les seules exceptions sont celles que la spécification nomme : le double dépassement
de contexte et le refus d'authentification, qui ne concernent pas les outils.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from avo.context.transcript import Transcript
from avo.llm.client import ToolCall

_journal = logging.getLogger("avo.outils")

#: Préfixe de toute erreur d'outil rendue au modèle (§H7.4).
PREFIXE_ERREUR = "error"

#: Correspondance entre les types du schéma JSON et les types Python acceptés.
_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}


class OutilInconnu(KeyError):
    """Nom d'outil absent du registre. Converti en texte avant d'atteindre la boucle."""


@dataclass(frozen=True)
class Outil:
    """Un outil : nom, description, schéma des paramètres, fonction (§H7.1)."""

    nom: str
    description: str
    parametres: Mapping[str, Any]
    fonction: Callable[..., str]
    #: Étiquettes de groupe, pour n'exposer que les outils permis à l'état courant
    #: de la boucle (§H7.1) : par exemple « action » n'est offert qu'au moment d'agir.
    etiquettes: frozenset[str] = frozenset()

    def schema(self) -> dict[str, Any]:
        """Forme attendue dans le tableau `tools` de l'appel (§H4.2)."""
        return {
            "type": "function",
            "function": {
                "name": self.nom,
                "description": self.description,
                "parameters": dict(self.parametres),
            },
        }

    def valider_arguments(self, arguments: Mapping[str, Any]) -> str | None:
        """Rend un message d'erreur, ou `None` si les arguments conviennent.

        Validation volontairement minimale — champs requis, types, énumérations —
        car le harnais n'a aucune dépendance d'exécution (§H2.1). Elle suffit à
        rendre au modèle un diagnostic exploitable plutôt qu'une trace Python.
        """
        proprietes = self.parametres.get("properties", {})
        for requis in self.parametres.get("required", []):
            if requis not in arguments:
                return f"argument obligatoire « {requis} » absent"
        for nom, valeur in arguments.items():
            attendu = proprietes.get(nom)
            if attendu is None:
                return f"argument « {nom} » inconnu pour l'outil {self.nom}"
            type_attendu = _TYPES.get(str(attendu.get("type", "")))
            if type_attendu is not None and not isinstance(valeur, type_attendu):
                return (
                    f"argument « {nom} » : type {attendu.get('type')} attendu, "
                    f"reçu {type(valeur).__name__}"
                )
            enum = attendu.get("enum")
            if enum is not None and valeur not in enum:
                return f"argument « {nom} » : valeur attendue parmi {enum}, reçue {valeur!r}"
        return None


@dataclass
class ResultatOutils:
    """Ce qu'un tour d'exécution d'outils a produit (§H7.2)."""

    transcript: Transcript
    executes: int = 0
    garde_franchie: bool = False


class RegistreOutils:
    """Déclare les outils, les expose au modèle et route ses appels (§H7.1)."""

    def __init__(self, outils: Iterable[Outil] = ()) -> None:
        self._outils: dict[str, Outil] = {}
        for outil in outils:
            self.enregistrer(outil)

    def enregistrer(self, outil: Outil) -> None:
        if outil.nom in self._outils:
            raise ValueError(f"outil « {outil.nom} » déjà enregistré")
        self._outils[outil.nom] = outil

    def __contains__(self, nom: object) -> bool:
        return nom in self._outils

    def __len__(self) -> int:
        return len(self._outils)

    @property
    def noms(self) -> tuple[str, ...]:
        return tuple(sorted(self._outils))

    def schemas(self, etiquettes: Iterable[str] | None = None) -> list[dict[str, Any]]:
        """Tableau `tools` de l'appel, filtré par étiquettes (§H7.1).

        Sans filtre, tous les outils sont exposés. Avec filtre, seuls ceux qui
        portent au moins une des étiquettes demandées : c'est ainsi que les outils
        d'action restent invisibles hors de l'état où agir est permis.
        """
        if etiquettes is None:
            choisis = list(self._outils.values())
        else:
            demandees = set(etiquettes)
            choisis = [outil for outil in self._outils.values() if outil.etiquettes & demandees]
        return [outil.schema() for outil in sorted(choisis, key=lambda outil: outil.nom)]

    # ------------------------------------------------------------------ routage
    def router(self, appel: ToolCall) -> str:
        """Exécute un appel et rend son résultat, ou un texte d'erreur (§H7.4)."""
        if appel.erreur_arguments is not None:
            return f"{PREFIXE_ERREUR}: arguments: {appel.erreur_arguments}"
        outil = self._outils.get(appel.nom)
        if outil is None:
            disponibles = ", ".join(self.noms) or "(aucun)"
            return (
                f"{PREFIXE_ERREUR}: outil_inconnu: « {appel.nom} » n'existe pas. "
                f"Outils disponibles : {disponibles}."
            )
        probleme = outil.valider_arguments(appel.arguments)
        if probleme is not None:
            return f"{PREFIXE_ERREUR}: arguments: {probleme}"
        try:
            return outil.fonction(**appel.arguments)
        except Exception as erreur:  # noqa: BLE001 — §H7.4 : rendu au modèle, jamais fatal
            _journal.info(
                "erreur d'outil rendue au modèle",
                extra={"outil": appel.nom, "type": type(erreur).__name__},
            )
            return f"{PREFIXE_ERREUR}: {type(erreur).__name__}: {erreur}"

    def executer(
        self,
        appels: Sequence[ToolCall],
        transcript: Transcript,
        tool_steps_max: int,
        deja_executes: int = 0,
    ) -> ResultatOutils:
        """Exécute les appels séquentiellement et ajoute les résultats (§H7.2).

        Chaque résultat devient un message `role: tool` ajouté en fin d'historique :
        l'ordre des appels est donc celui des messages, et la tête reste intacte.
        Au-delà de la garde, le tour est clos par un message explicite plutôt que
        silencieusement tronqué.
        """
        resultat = ResultatOutils(transcript=transcript, executes=deja_executes)
        for appel in appels:
            if resultat.executes >= tool_steps_max:
                resultat.garde_franchie = True
                resultat.transcript = resultat.transcript.utilisateur(
                    f"Garde atteinte : {tool_steps_max} appels d'outils pour ce tour "
                    "(AVO_TOOL_STEPS_MAX). Le tour est clos ; agis ou conclus au "
                    "tour suivant."
                )
                _journal.info(
                    "garde d'appels d'outils franchie",
                    extra={"tool_steps_max": tool_steps_max, "restants": len(appels)},
                )
                break
            sortie = self.router(appel)
            resultat.transcript = resultat.transcript.outil(appel.nom, sortie)
            resultat.executes += 1
        return resultat


def outil_depuis_schema(
    schema: Mapping[str, Any],
    fonction: Callable[..., str],
    etiquettes: Iterable[str] = (),
) -> Outil:
    """Construit un `Outil` depuis un schéma déjà déclaré ailleurs.

    Évite de redéclarer nom, description et paramètres là où ils existent déjà —
    les outils de notes (§H7.3) portent les leurs dans `avo.memory.notes`.
    """
    fonction_schema = schema["function"]
    return Outil(
        nom=str(fonction_schema["name"]),
        description=str(fonction_schema.get("description", "")),
        parametres=fonction_schema.get("parameters", {}),
        fonction=fonction,
        etiquettes=frozenset(etiquettes),
    )
