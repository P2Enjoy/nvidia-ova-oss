"""Environnement Dépôt logiciel : demandes, branches, PR, CI, générateur, résolution.

@spec docs/BACKLOG.md U29a3 — environnement Dépôt logiciel du banc a ; U29a4 —
      branchement à l'adaptateur (le numéro de PR de `merge` arrive en texte)
      et dérive d'état de la condition 3
@spec docs/SPEC_BANCS.md §S4.1 (état de vérité : master, branches, PR, CI,
      demandes — jamais montré à l'agent), §S4.2 (actions, validité, effets ;
      une action invalide rend une erreur nommée et ne change pas l'état ;
      `merge` sur CI rouge est valide et casse la CI), §S4.3 (cycle d'une
      demande, générateur nominal seedé, bruit C.3), §S4.4 (score continu
      inchangé + résolution B.1 au relevé), §S4.5 (obligation d'un événement,
      évaluée sur l'état RÉEL, divergence → `wait`), §S4.6 (une action consomme
      l'événement, fin d'épisode), §S4.7 (dérive d'état : CI cassée par un
      commit direct externe, événement `ci_verte` périmé forcé, alerte),
      §S5.5 (mesure de récupération au relevé)

L'état de vérité appartient à l'environnement et évolue exclusivement par les
actions VALIDES de l'agent. L'agent ne voit que `observation()` et les issues.
`IssueBanc` et le motif de fin sont ceux de l'Entrepôt : §S3.7 et §S5.2
s'appliquent tels quels au Dépôt logiciel (§S4.6).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Final

from avo.bancs.skillexec.entrepot import MOTIF_EPUISE, IssueBanc
from avo.bancs.skillexec.generation import ENTETE_ALERTE, ENTETE_TELEMETRIE
from avo.bancs.skillexec.score import Releve

#: Types d'événements actionnables du cycle d'une demande (§S4.3).
AFFECTATION: Final = "affectation"
REVUE: Final = "revue"
ECHEC_CI: Final = "echec_ci"
CI_VERTE: Final = "ci_verte"

#: Statuts CI d'une branche (§S4.1).
ROUGE: Final = "rouge"
VERTE: Final = "verte"


def nom_demande(indice: int) -> str:
    """Nom public d'une demande de fonctionnalité (§S4.3)."""
    return f"demande_{indice}"


def nom_fichier(indice: int) -> str:
    """Fichier porté par la demande d'indice donné (§S4.3)."""
    return f"fichier_{indice}"


def nom_branche(indice: int) -> str:
    """Branche de fonctionnalité de la demande d'indice donné (§S4.3)."""
    return f"branche_{indice}"


@dataclass(frozen=True)
class EvenementDepot:
    """Un événement actionnable, tel que l'agent l'observe (§S4.3, §S4.5).

    `pr` n'est renseigné que pour `echec_ci` et `ci_verte` ; c'est le numéro de
    PR NOMINAL (§S4.3) — celui du jeu parfait, pas nécessairement celui de
    l'agent (§S3.4 s'applique).
    """

    type: str
    demande: int
    pr: int | None
    observation: str


@dataclass(frozen=True)
class DeriveDepot:
    """La dérive d'état de la condition 3 au dépôt, figée à la génération (§S4.7).

    `demande` et `pr` sont NOMINAUX ; l'application à l'état réel (CI de la
    branche cassée si elle est réellement verte) appartient à l'environnement.
    """

    evenement: int
    demande: int
    pr: int
    alerte: str


@dataclass(frozen=True)
class EpisodeDepot:
    """Un épisode entier, figé à la génération (§S1.4).

    `defauts[d]` dit si la demande d'indice d porte le défaut tiré (§S4.3) : la
    CI du premier commit réel de sa branche sera `rouge`. `telemetrie[i]` porte
    les lignes de bruit accompagnant `evenements[i]` ; `derive` porte l'unique
    dérive de la condition 3 (§S4.7), None sans elle.
    """

    seed: int
    horizon: int
    bruit: int
    evenements: tuple[EvenementDepot, ...]
    telemetrie: tuple[tuple[str, ...], ...]
    defauts: tuple[bool, ...]
    derive: DeriveDepot | None = None


def _ligne_telemetrie(rng: random.Random) -> str:
    """Une ligne de bruit strictement hors sujet (§S4.3, distracteurs C.3)."""
    return (
        f"[Syslog] Serveur-{rng.randint(1, 99)} — "
        f"charge CPU : {rng.randint(1, 100)} %, "
        f"RAM : {rng.randint(10, 95)} %"
    )


@dataclass
class _DemandeNominale:
    """Avancement nominal d'une demande en vie chez le générateur (§S4.3)."""

    indice: int
    defaut: bool
    prochain: str
    pr: int | None = None


def generer_episode_depot(
    seed: int, horizon: int, bruit: int = 0, derive: bool = False
) -> EpisodeDepot:
    """Engendre l'épisode complet sur l'état nominal (§S4.3, §S3.4 appliqué).

    À chaque pas, les candidats sont construits dans un ordre fixe — une
    affectation neuve (toujours faisable), puis le prochain événement nominal de
    chaque demande en vie dans l'ordre des indices — et `rng.choice` tranche.
    Le générateur applique la réponse parfaite à chaque événement émis. Avec
    `derive`, l'unique dérive de §S4.7 se place au premier pas `d ≥ horizon // 2`
    offrant un candidat (demande en vie prête à fusionner), sur un rng séparé :
    le rng principal n'est pas consommé à ce pas, et la génération à `derive`
    inactif reste inchangée octet pour octet.
    """
    if horizon < 0:
        raise ValueError(f"horizon négatif : {horizon}")
    if bruit < 0:
        raise ValueError(f"bruit négatif : {bruit}")
    rng = random.Random(seed)
    #: Flux séparé pour la télémétrie (§S3.6 s'applique) : le niveau de bruit ne
    #: change jamais la suite d'événements.
    rng_bruit = random.Random(f"bruit-{seed}")
    rng_derive = random.Random(f"derive-{seed}")
    derive_posee: DeriveDepot | None = None
    vivantes: list[_DemandeNominale] = []
    defauts: list[bool] = []
    evenements: list[EvenementDepot] = []
    telemetrie: list[tuple[str, ...]] = []
    prochaine_demande = 0
    prochaine_pr = 1
    for pas in range(horizon):
        if derive and derive_posee is None and pas >= horizon // 2:
            pretes = [v for v in vivantes if v.prochain == CI_VERTE and v.pr is not None]
            if pretes:
                #: Dérive (§S4.7) : un commit direct externe casse la CI de la
                #: demande tirée ; l'événement forcé est la notification
                #: `ci_verte` périmée, partie avant la casse — seule l'alerte dit
                #: la vérité, et l'obligation réelle du pas est `wait` (§S4.5).
                choix_derive = rng_derive.choice(pretes)
                numero_pr = choix_derive.pr or 0
                evenements.append(
                    EvenementDepot(
                        CI_VERTE,
                        choix_derive.indice,
                        numero_pr,
                        f"CI verte pour PR #{numero_pr} "
                        f"({nom_branche(choix_derive.indice)}) : prête à fusionner.",
                    )
                )
                derive_posee = DeriveDepot(
                    evenement=pas,
                    demande=choix_derive.indice,
                    pr=numero_pr,
                    alerte=f"[Alerte] Commit direct sur {nom_branche(choix_derive.indice)} : "
                    "sa CI est repassée au rouge.",
                )
                #: Résolution nominale du pas forcé : l'agent parfait lit
                #: l'alerte et attend ; la CI nominale étant rouge, le cycle de
                #: la demande reprend à `echec_ci` (§S4.7).
                choix_derive.prochain = ECHEC_CI
                telemetrie.append(tuple(_ligne_telemetrie(rng_bruit) for _ in range(bruit)))
                continue
        candidats: list[_DemandeNominale | None] = [None]
        candidats.extend(vivantes)
        choix = rng.choice(candidats)
        if choix is None:
            indice = prochaine_demande
            prochaine_demande += 1
            defaut = rng.random() < 0.5
            defauts.append(defaut)
            evenements.append(
                EvenementDepot(
                    AFFECTATION,
                    indice,
                    None,
                    f"Issue affectée : {nom_demande(indice)} — "
                    f"écrire {nom_fichier(indice)} sur {nom_branche(indice)}.",
                )
            )
            #: Réponse parfaite : commit joué, la branche nominale existe.
            vivantes.append(_DemandeNominale(indice, defaut, prochain=REVUE))
        elif choix.prochain == REVUE:
            evenements.append(
                EvenementDepot(
                    REVUE,
                    choix.indice,
                    None,
                    f"Revue approuvée pour {nom_branche(choix.indice)} : la PR peut être ouverte.",
                )
            )
            #: Réponse parfaite : PR nominale ouverte, numéro croissant depuis 1.
            choix.pr = prochaine_pr
            prochaine_pr += 1
            choix.prochain = ECHEC_CI if choix.defaut else CI_VERTE
        elif choix.prochain == ECHEC_CI:
            evenements.append(
                EvenementDepot(
                    ECHEC_CI,
                    choix.indice,
                    choix.pr,
                    f"CI en échec pour PR #{choix.pr} "
                    f"({nom_branche(choix.indice)}) : erreur de lint.",
                )
            )
            #: Réponse parfaite : défaut corrigé, la CI nominale repasse verte.
            choix.prochain = CI_VERTE
        else:
            evenements.append(
                EvenementDepot(
                    CI_VERTE,
                    choix.indice,
                    choix.pr,
                    f"CI verte pour PR #{choix.pr} "
                    f"({nom_branche(choix.indice)}) : prête à fusionner.",
                )
            )
            #: Réponse parfaite : fusion jouée, la demande nominale est close.
            vivantes.remove(choix)
        telemetrie.append(tuple(_ligne_telemetrie(rng_bruit) for _ in range(bruit)))
    if derive and derive_posee is None:
        raise ValueError(
            f"aucun candidat de dérive au seed {seed} (horizon {horizon}) : "
            "aucun pas ≥ horizon // 2 n'offre une demande prête à fusionner — "
            "prendre un autre seed (§S4.7)."
        )
    return EpisodeDepot(
        seed=seed,
        horizon=horizon,
        bruit=bruit,
        evenements=tuple(evenements),
        telemetrie=tuple(telemetrie),
        defauts=tuple(defauts),
        derive=derive_posee,
    )


class EnvironnementDepot:
    """État de vérité et règles du dépôt logiciel (§S4).

    Chaque action — valide ou non — consomme l'événement courant (§S4.6) et
    compte au relevé (§S5.2) : un événement reçoit exactement une action.
    """

    def __init__(self, episode: EpisodeDepot) -> None:
        self._episode = episode
        self._index = 0
        #: Dernier indice d'événement dont l'arrivée a été appliquée (§S4.1).
        self._prepare_index = -1
        #: Demandes annoncées (affectation observée), jamais retirées (§S4.2 :
        #: `commit` reste valide tant que la branche n'est pas fusionnée).
        self._annoncees: set[int] = set()
        self._master: dict[str, str] = {}
        #: Fichiers des branches réelles existantes (créées par un commit).
        self._branches: dict[str, dict[str, str]] = {}
        self._ci: dict[str, str] = {}
        #: PR ouvertes : numéro réel croissant depuis 1 → branche (§S4.1).
        self._prs: dict[int, str] = {}
        self._pr_suivante = 1
        self._fusionnees: set[str] = set()
        #: Par fichier de master : la fusion qui l'a (dernièrement) écrit
        #: était-elle propre — CI verte (§S4.4) ?
        self._fusion_propre: dict[str, bool] = {}
        #: Mesure de récupération (§S5.5) : événements consommés depuis la dérive
        #: avant la première action correcte, None tant qu'aucune ne l'est.
        self._recuperation: int | None = None
        self.releve = Releve(seed=episode.seed, horizon=episode.horizon, bruit=episode.bruit)

    def _preparer(self) -> None:
        """Annonce la demande de l'événement courant, une seule fois : le
        `commit` dû est valide dès que l'affectation est observable (§S4.2).
        La dérive réelle (§S4.7) s'applique au même moment, quand l'événement
        porteur devient observable."""
        evenement = self._evenement_courant()
        if evenement is not None and self._prepare_index != self._index:
            self._prepare_index = self._index
            derive = self._episode.derive
            if derive is not None and self._index == derive.evenement:
                #: Dérive réelle (§S4.7) : la CI de la branche est cassée si elle
                #: est réellement verte ; sinon l'état réel reste inchangé.
                branche = nom_branche(derive.demande)
                if self._ci.get(branche) == VERTE:
                    self._ci[branche] = ROUGE
            if evenement.type == AFFECTATION:
                self._annoncees.add(evenement.demande)

    # ------------------------------------------------------------ observation
    def observation(self) -> str:
        """L'événement courant et sa télémétrie (§S4.3) ; le motif de fin sinon."""
        self._preparer()
        if self._index >= len(self._episode.evenements):
            return MOTIF_EPUISE
        evenement = self._episode.evenements[self._index]
        lignes = [evenement.observation]
        derive = self._episode.derive
        if derive is not None and self._index == derive.evenement:
            lignes.extend((ENTETE_ALERTE, derive.alerte))
        bruit = self._episode.telemetrie[self._index]
        if bruit:
            lignes.append(ENTETE_TELEMETRIE)
            lignes.extend(bruit)
        return "\n".join(lignes)

    def etat_terminal(self) -> str | None:
        """Motif d'arrêt quand l'épisode est épuisé (§S4.6), sinon None."""
        if self._index >= len(self._episode.evenements):
            return MOTIF_EPUISE
        return None

    # ----------------------------------------------------------------- accès
    def fichier_master(self, nom: str) -> str | None:
        """Contenu réel d'un fichier de master — pour les preuves, jamais l'agent."""
        return self._master.get(nom)

    def ci_branche(self, branche: str) -> str | None:
        """Statut CI réel d'une branche existante, None sinon — pour les preuves."""
        return self._ci.get(branche)

    def pr_ouverte(self, numero: int) -> str | None:
        """Branche d'une PR réelle ouverte, None sinon — pour les preuves."""
        return self._prs.get(numero)

    def _evenement_courant(self) -> EvenementDepot | None:
        if self._index >= len(self._episode.evenements):
            return None
        return self._episode.evenements[self._index]

    def _indice_branche(self, branche: str) -> int | None:
        """Indice de demande d'un nom de branche bien formé, None sinon."""
        prefixe = "branche_"
        if not branche.startswith(prefixe):
            return None
        try:
            return int(branche[len(prefixe) :])
        except ValueError:
            return None

    # --------------------------------------------------------------- actions
    def commit(self, branche: str, fichier: str) -> IssueBanc:
        """`commit <branche> <fichier>` (§S4.2)."""
        self._preparer()
        evenement = self._evenement_courant()
        if evenement is None:
            return IssueBanc(f"error: {MOTIF_EPUISE}", valide=False, correcte=False)
        indice = self._indice_branche(branche)
        if indice is None or indice not in self._annoncees or branche in self._fusionnees:
            return self._consommer(False, False, f"error: branche inconnue ou fermée : {branche}.")
        if branche not in self._branches:
            #: Premier commit : la branche naît et le défaut tiré se matérialise.
            self._branches[branche] = {}
            self._ci[branche] = ROUGE if self._episode.defauts[indice] else VERTE
        self._branches[branche][fichier] = f"contenu de {fichier}"
        correcte = (
            evenement.type == AFFECTATION
            and branche == nom_branche(evenement.demande)
            and fichier == nom_fichier(evenement.demande)
        )
        return self._consommer(True, correcte, f"Succès : commit de {fichier} sur {branche}.")

    def create_pr(self, branche: str) -> IssueBanc:
        """`create_pr <branche>` (§S4.2) : numéro réel croissant depuis 1."""
        self._preparer()
        evenement = self._evenement_courant()
        if evenement is None:
            return IssueBanc(f"error: {MOTIF_EPUISE}", valide=False, correcte=False)
        if branche not in self._branches:
            return self._consommer(False, False, f"error: {branche} n'existe pas.")
        if branche in self._prs.values():
            return self._consommer(False, False, f"error: une PR est déjà ouverte pour {branche}.")
        numero = self._pr_suivante
        self._pr_suivante += 1
        self._prs[numero] = branche
        correcte = evenement.type == REVUE and branche == nom_branche(evenement.demande)
        return self._consommer(True, correcte, f"Succès : PR #{numero} ouverte pour {branche}.")

    def fix_ci(self, branche: str) -> IssueBanc:
        """`fix_ci <branche>` (§S4.2) : corrigé, le défaut ne revient pas."""
        self._preparer()
        evenement = self._evenement_courant()
        if evenement is None:
            return IssueBanc(f"error: {MOTIF_EPUISE}", valide=False, correcte=False)
        if branche not in self._branches:
            return self._consommer(False, False, f"error: {branche} n'existe pas.")
        if self._ci[branche] != ROUGE:
            return self._consommer(False, False, f"error: la CI de {branche} n'est pas en échec.")
        self._ci[branche] = VERTE
        correcte = evenement.type == ECHEC_CI and branche == nom_branche(evenement.demande)
        return self._consommer(True, correcte, f"Succès : CI de {branche} corrigée.")

    def merge(self, numero: int | str) -> IssueBanc:
        """`merge <pr>` (§S4.2) : valide dès que la PR est ouverte ; une fusion
        en CI rouge CASSE la CI — l'issue le nomme, la résolution le paie.

        Le numéro arrive en texte depuis les outils du banc (U29a4) et se lit
        dans la notation que l'environnement émet lui-même (§S4.2, point tranché
        du 2026-09-02) : l'entier nu, « #3 », et le préfixe « PR » à casse
        indifférente avec ou sans espace ni croisillon (« PR #3 », « PR#3 »,
        « PR 3 »). Un numéro imprenable est une action invalide NOMMÉE qui
        consomme l'événement, comme toute action (§S4.6) — jamais une erreur
        obscure avant l'environnement.
        """
        self._preparer()
        evenement = self._evenement_courant()
        if evenement is None:
            return IssueBanc(f"error: {MOTIF_EPUISE}", valide=False, correcte=False)
        if isinstance(numero, str):
            texte = numero.strip()
            if texte[:2].lower() == "pr":
                texte = texte[2:].lstrip()
            try:
                numero = int(texte.lstrip("#").lstrip())
            except ValueError:
                return self._consommer(False, False, f"error: numéro de PR invalide : {numero}.")
        branche = self._prs.get(numero)
        if branche is None:
            return self._consommer(False, False, f"error: PR #{numero} n'est pas ouverte.")
        propre = self._ci[branche] == VERTE
        correcte = evenement.type == CI_VERTE and evenement.pr == numero and propre
        del self._prs[numero]
        for fichier, contenu in self._branches.pop(branche).items():
            self._master[fichier] = contenu
            self._fusion_propre[fichier] = propre
        del self._ci[branche]
        self._fusionnees.add(branche)
        if propre:
            texte = f"Succès : PR #{numero} fusionnée dans master."
        else:
            texte = f"Succès : PR #{numero} fusionnée dans master. La CI de master est CASSÉE."
        return self._consommer(True, correcte, texte)

    def wait(self) -> IssueBanc:
        """`wait` (§S4.2, toujours valide) : dû seulement aux cas de §S4.5."""
        self._preparer()
        evenement = self._evenement_courant()
        if evenement is None:
            return IssueBanc(f"error: {MOTIF_EPUISE}", valide=False, correcte=False)
        return self._consommer(True, self._wait_du(evenement), "Rien à faire.")

    def _wait_du(self, evenement: EvenementDepot) -> bool:
        """`wait` n'est l'obligation qu'en divergence (§S4.5) : l'action due par
        l'événement n'est plus jouable sur l'état réel."""
        branche = nom_branche(evenement.demande)
        if evenement.type == REVUE:
            return branche not in self._branches or branche in self._prs.values()
        if evenement.type == ECHEC_CI:
            return self._ci.get(branche) != ROUGE
        if evenement.type == CI_VERTE:
            if evenement.pr is None:
                return True
            ouverte = self._prs.get(evenement.pr)
            return ouverte is None or self._ci[ouverte] != VERTE
        #: `affectation` : le commit dû est toujours jouable (§S4.5).
        return False

    # ------------------------------------------------------------- résolution
    def demandes_jugees(self) -> int:
        """Demandes dont l'événement `ci_verte` nominal est dans l'épisode (§S4.4)."""
        return len({e.demande for e in self._episode.evenements if e.type == CI_VERTE})

    def demandes_resolues(self) -> int:
        """Demandes jugées dont le fichier est dans master, fusionné CI verte (§S4.4)."""
        jugees = {e.demande for e in self._episode.evenements if e.type == CI_VERTE}
        return sum(
            1
            for d in jugees
            if nom_fichier(d) in self._master and self._fusion_propre[nom_fichier(d)]
        )

    def resolution(self) -> float | None:
        """`resolution` de §S4.4, None quand aucune demande n'est jugée."""
        jugees = self.demandes_jugees()
        if jugees == 0:
            return None
        return self.demandes_resolues() / jugees

    def completer_releve(self) -> Releve:
        """Porte la résolution (§S4.4) et la récupération (§S5.5) au relevé."""
        self.releve.champs_libres.update(
            {
                "resolution": self.resolution(),
                "demandes_resolues": self.demandes_resolues(),
                "demandes_jugees": self.demandes_jugees(),
            }
        )
        if self._episode.derive is not None:
            self.releve.champs_libres.update(
                {
                    "derive_evenement": self._episode.derive.evenement,
                    "pas_de_recuperation": self._recuperation,
                    "recupere": self._recuperation is not None,
                }
            )
        return self.releve

    # -------------------------------------------------------------- mécanique
    def _consommer(self, valide: bool, correcte: bool, observation: str) -> IssueBanc:
        """Compte la première action au relevé et consomme l'événement (§S4.6)."""
        derive = self._episode.derive
        if (
            derive is not None
            and correcte
            and self._recuperation is None
            and self._index >= derive.evenement
        ):
            #: Première action correcte depuis la dérive (§S5.5).
            self._recuperation = self._index - derive.evenement
        self.releve.compter(valide, correcte)
        self._index += 1
        return IssueBanc(observation, valide=valide, correcte=correcte)
