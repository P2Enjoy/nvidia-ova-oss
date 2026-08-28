"""Budget de contexte et continuation en contexte frais.

@spec docs/BACKLOG.md U10 — Budget et continuation en contexte frais
@spec docs/SPEC_HARNAIS.md §H5.3 (continuation, mécanisme VISTA), §H5.4 (`413` nominal),
      §H3.2 (budget utile et plafond appris), §H5.1 (segments append-only)

Deux mécanismes, un seul objet. Le premier est **préventif** : quand l'estimation
approche du budget, l'agent est invité à écrire un état de continuation, puis un
segment frais démarre. Le second est **curatif** : si le serveur refuse malgré tout,
le `413` n'est pas une panne mais un cas nominal — il apprend le vrai plafond et
déclenche la même continuation, sans jamais rejouer sur le segment plein.

Ce qui survit à une continuation : les notes et la mémoire de jeu. Ce qui est
renouvelé : le seul contexte conversationnel.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from avo.config import Config
from avo.context.tokens import TokenLedger
from avo.context.transcript import Transcript
from avo.llm.client import ChatResult, ContextOverflow

_journal = logging.getLogger("avo.contexte")

#: Invitation envoyée à l'agent pour qu'il écrive son état de continuation (§H5.3).
#: Volontairement brève : elle consomme le budget qu'elle cherche à préserver.
INVITATION_CONTINUATION = (
    "Le contexte approche de sa limite. Écris maintenant un état de continuation "
    "concis : ce que tu as compris, où tu en es, et ce que tu comptes faire ensuite. "
    "Il sera le seul souvenir conversationnel que tu garderas."
)

#: Nombre de dépassements consécutifs au-delà duquel la configuration est jugée
#: incohérente (§H5.4). Le premier déclenche une continuation ; le second survient
#: sur le segment frais que cette continuation vient de créer, donc aucune
#: continuation supplémentaire ne peut aider.
DEPASSEMENTS_AVANT_ABANDON = 2


def appels_en_api(resultat: ChatResult) -> list[dict[str, object]]:
    """Rend les appels d'outils sous la forme attendue dans l'historique (§H4.2).

    L'historique doit refléter fidèlement ce que le modèle a demandé : sans cela, un
    tour suivant lui présenterait une conversation dont il ne reconnaîtrait pas ses
    propres actes.
    """
    appels: list[dict[str, object]] = []
    for appel in resultat.tool_calls:
        charge: dict[str, object] = {
            "function": {"name": appel.nom, "arguments": dict(appel.arguments)}
        }
        if appel.identifiant is not None:
            charge["id"] = appel.identifiant
        appels.append(charge)
    return appels


class BudgetIncoherent(RuntimeError):
    """Un segment frais dépasse déjà le contexte : rien ne peut plus être tenté (§H5.4)."""


@dataclass
class Contexte:
    """Suit le budget d'un segment et pilote les continuations (§H5.3, §H5.4)."""

    config: Config
    systeme: str
    registre: TokenLedger = field(default_factory=TokenLedger)
    transcript: Transcript = field(init=False)
    segment: int = 1
    segments_archives: list[Transcript] = field(default_factory=list)
    depassements_consecutifs: int = 0

    def __post_init__(self) -> None:
        self.transcript = Transcript.ouvrir(self.systeme)

    # ------------------------------------------------------------------- budget
    @property
    def budget_prompt(self) -> int:
        """Tokens de prompt disponibles, marge du proxy comprise (§H3.2)."""
        return self.config.budget_prompt

    @property
    def seuil(self) -> int:
        """Seuil de déclenchement de la continuation (§H5.3)."""
        return int(self.config.ratio_continuation * self.budget_prompt)

    def estimation(self) -> int:
        """Estimation courante du prompt, avec le rapport calibré (§H5.2)."""
        return self.registre.estimer(self.transcript.texte_integral())

    def seuil_atteint(self) -> bool:
        """L'estimation dépasse-t-elle le seuil ? C'est le déclencheur préventif."""
        return self.estimation() > self.seuil

    # -------------------------------------------------------------- déroulement
    def ajouter_observation(self, observation: str) -> None:
        """Ajoute l'observation courante. Append-only (§H5.1)."""
        self.transcript = self.transcript.utilisateur(observation)

    def enregistrer_reponse(self, resultat: ChatResult) -> None:
        """Enregistre la réponse : transcript, comptabilité, et série de dépassements.

        Un échange abouti remet la série de dépassements à zéro : ce sont les
        dépassements **consécutifs** qui signalent une configuration incohérente.
        """
        estime = self.estimation()
        self.transcript = self.transcript.assistant(resultat.content, appels_en_api(resultat))
        self.registre.enregistrer(estime, resultat.prompt_eval_count, resultat.eval_count)
        self.depassements_consecutifs = 0

    def continuer(self, etat_continuation: str, notes: str, observation: str) -> Transcript:
        """Ouvre un segment frais : système + continuation + notes + observation (§H5.3).

        L'ancien segment est archivé, pas effacé : il reste dans les artefacts du run.
        L'ordre des quatre éléments est celui de la spécification, et il est vérifié
        par test — un segment frais mal composé perdrait la mémoire du run.
        """
        self.segments_archives.append(self.transcript)
        ancien = self.segment
        self.segment += 1
        self.transcript = (
            Transcript.ouvrir(self.systeme)
            .utilisateur(etat_continuation)
            .utilisateur(notes)
            .utilisateur(observation)
        )
        _journal.info(
            "continuation en contexte frais",
            extra={
                "segment_clos": ancien,
                "segment_ouvert": self.segment,
                "messages_archives": len(self.segments_archives[-1]),
                "budget_prompt": self.budget_prompt,
            },
        )
        return self.transcript

    # ------------------------------------------------------------ dépassements
    def absorber_depassement(self, erreur: ContextOverflow) -> None:
        """Traite un `413` comme un cas nominal (§H5.4).

        Apprend le plafond réel s'il est fourni, puis compte le dépassement. Au
        deuxième consécutif, la configuration est incohérente : on lève plutôt que
        de boucler. Aucun nouvel appel n'est fait sur le segment plein.
        """
        self.depassements_consecutifs += 1
        if erreur.max_context_tokens:
            avant = self.config.contexte_demande
            self.config = self.config.avec_plafond_appris(erreur.max_context_tokens)
            if self.config.contexte_demande != avant:
                _journal.info(
                    "plafond de contexte appris depuis un refus du serveur",
                    extra={
                        "contexte_avant": avant,
                        "contexte_appris": self.config.contexte_demande,
                        "budget_prompt": self.budget_prompt,
                        "tokens_estimes_par_le_serveur": erreur.tokens_estimated,
                    },
                )
        if self.depassements_consecutifs >= DEPASSEMENTS_AVANT_ABANDON:
            raise BudgetIncoherent(
                f"{self.depassements_consecutifs} dépassements de contexte consécutifs : "
                "le segment frais issu de la continuation dépasse lui aussi la limite. "
                f"Aucune continuation ne peut y remédier (budget {self.budget_prompt} "
                f"tokens pour un contexte de {self.config.contexte_demande}). "
                "Vérifier OLLAMA_CONTEXT_LENGTH et AVO_NUM_PREDICT "
                "(docs/SPEC_HARNAIS.md §H5.4)."
            )
        _journal.info(
            "dépassement de contexte absorbé, continuation requise",
            extra={"depassements_consecutifs": self.depassements_consecutifs},
        )

    def resume(self) -> dict[str, object]:
        """Résumé journalisable : des compteurs, aucun contenu (§H4.6)."""
        return {
            "segment": self.segment,
            "segments_archives": len(self.segments_archives),
            "messages": len(self.transcript),
            "estimation": self.estimation(),
            "seuil": self.seuil,
            "budget_prompt": self.budget_prompt,
            "depassements_consecutifs": self.depassements_consecutifs,
        }
