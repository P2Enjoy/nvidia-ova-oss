"""Lignée de solutions : versions validées, scorées, committées dans un dépôt jetable.

@spec docs/BACKLOG.md U14 — Lignée et fonction de score
@spec docs/SPEC_HARNAIS.md §H9.1 (formalisme AVO), §H9.2 (instanciation ARC),
      §H9.3 (dépôt git jetable, isolation absolue), §H9.4 (`Scorer` branchable)
@spec CLAUDE.md §13 (interdiction absolue de toucher au dépôt du projet)

Mécanisme repris du papier AVO : une lignée single-lineage de paires (solution,
score), où une version n'est committée que si elle est **correcte** ET **au moins
aussi bonne** que la meilleure déjà committée. Une régression n'entre jamais dans la
lignée ; elle reste dans la trajectoire interne de recherche.

**Isolation.** Toute commande git est lancée avec `--git-dir` et `--work-tree`
explicites, ce qui empêche git de remonter l'arborescence. Sans cela, un `git init`
raté ferait committer dans le dépôt du projet — le seul défaut de ce module qui
serait vraiment grave, et il est vérifié par test.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

_journal = logging.getLogger("avo.lignee")

#: Identité posée sur le dépôt jetable. Il n'est jamais poussé nulle part ; cette
#: identité sert uniquement à ce que git accepte de committer.
IDENTITE = ("P2Enjoy", "contact@p2enjoy.studio")


class LigneeNonIsolee(RuntimeError):
    """Le dépôt de lignée n'est pas isolé : refus absolu d'exécuter une commande git.

    C'est la garde qui protège le dépôt du projet (CLAUDE.md §13). Elle lève plutôt
    que de tenter quoi que ce soit : un commit égaré dans le dépôt du projet serait
    bien plus coûteux qu'un run interrompu.
    """


class Scorer(Protocol):
    """Fonction de score `f` branchable (§H9.4)."""

    def score(self, evidence: Any) -> tuple[int, ...]: ...
    def est_valide(self, evidence: Any) -> bool: ...


@dataclass(frozen=True)
class ScorerARC:
    """Instanciation ARC de `f` (§H9.2).

    Score lexicographique `(niveaux complétés, −actions cumulées)` : progresser prime
    toujours, et à progression égale, moins d'actions vaut mieux. « Correct » signifie
    qu'une progression a été constatée **par l'environnement**, jamais affirmée par le
    modèle.
    """

    def score(self, evidence: Any) -> tuple[int, ...]:
        return (int(evidence.niveaux_completes), -int(evidence.actions_jeu))

    def est_valide(self, evidence: Any) -> bool:
        return int(evidence.niveaux_completes) > 0


@dataclass(frozen=True)
class ScorerConstant:
    """Scorer déterministe pour éprouver la boucle sans environnement réel (§H9.4)."""

    valide: bool = True

    def score(self, evidence: Any) -> tuple[int, ...]:
        return tuple(evidence)

    def est_valide(self, evidence: Any) -> bool:
        return self.valide


@dataclass(frozen=True)
class Decision:
    """Ce que la lignée a fait d'une version proposée."""

    acceptee: bool
    motif: str
    score: tuple[int, ...]
    sha: str | None = None


@dataclass
class Lignee:
    """Dépôt git jetable portant la suite des versions validées (§H9.3)."""

    chemin: Path
    scorer: Scorer
    meilleur_score: tuple[int, ...] | None = None
    decisions: list[Decision] = field(default_factory=list)

    # --------------------------------------------------------------- ouverture
    @classmethod
    def ouvrir(cls, chemin: Path, scorer: Scorer) -> Lignee:
        """Crée le dépôt jetable et rend la lignée prête à recevoir des versions."""
        chemin.mkdir(parents=True, exist_ok=True)
        lignee = cls(chemin=chemin, scorer=scorer)
        if not (chemin / ".git").exists():
            subprocess.run(  # noqa: S603 — arguments fixes, aucun contenu externe
                ["git", "init", "--quiet", "--initial-branch=lignee", str(chemin)],
                check=True,
                capture_output=True,
            )
        lignee._git("config", "user.name", IDENTITE[0])
        lignee._git("config", "user.email", IDENTITE[1])
        return lignee

    # ------------------------------------------------------------------- garde
    @property
    def git_dir(self) -> Path:
        return self.chemin / ".git"

    def verifier_isolation(self) -> None:
        """Refuse d'agir si le dépôt jetable n'est pas là où il doit être (§H9.3)."""
        if not self.git_dir.is_dir():
            raise LigneeNonIsolee(
                f"{self.git_dir} absent : sans dépôt dédié, une commande git "
                "remonterait l'arborescence et pourrait atteindre le dépôt du projet "
                "(CLAUDE.md §13)."
            )

    def _git(self, *arguments: str) -> str:
        """Exécute une commande git STRICTEMENT dans le dépôt de lignée.

        `--git-dir` et `--work-tree` explicites : git ne remonte jamais l'arborescence,
        quoi qu'il arrive au répertoire courant.
        """
        self.verifier_isolation()
        resultat = subprocess.run(  # noqa: S603 — arguments contrôlés par ce module
            [
                "git",
                f"--git-dir={self.git_dir}",
                f"--work-tree={self.chemin}",
                *arguments,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return resultat.stdout.strip()

    # ---------------------------------------------------------------- politique
    def proposer(
        self,
        evidence: Any,
        notes: Mapping[str, str],
        meta: Mapping[str, Any] | None = None,
    ) -> Decision:
        """Applique la politique « correct ∧ ≥ meilleur » (§H9.1).

        Une version incorrecte ou en régression n'est pas committée : elle reste dans
        la trajectoire interne de recherche, exactement comme le décrit le papier AVO.

        La garde d'isolation est vérifiée **avant toute écriture** : sur une lignée
        non isolée, rien ne doit être écrit nulle part, pas même un fichier de notes.
        """
        self.verifier_isolation()
        if not self.scorer.est_valide(evidence):
            decision = Decision(False, "version incorrecte", self.scorer.score(evidence))
            return self._retenir(decision)

        score = self.scorer.score(evidence)
        if self.meilleur_score is not None and score < self.meilleur_score:
            decision = Decision(False, f"régression : {score} < {self.meilleur_score}", score)
            return self._retenir(decision)

        sha = self._committer(score, notes, meta or {})
        self.meilleur_score = score
        return self._retenir(Decision(True, "version committée", score, sha))

    def _retenir(self, decision: Decision) -> Decision:
        self.decisions.append(decision)
        _journal.info(
            "décision de lignée",
            extra={
                "acceptee": decision.acceptee,
                "motif": decision.motif,
                "score": list(decision.score),
                "versions": self.nombre_de_versions(),
            },
        )
        return decision

    def _committer(
        self, score: tuple[int, ...], notes: Mapping[str, str], meta: Mapping[str, Any]
    ) -> str:
        for nom, contenu in notes.items():
            (self.chemin / f"{nom}.md").write_text(contenu, encoding="utf-8")
        (self.chemin / "meta.json").write_text(
            json.dumps({**meta, "score": list(score)}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self._git("add", "--all")
        version = self.nombre_de_versions() + 1
        self._git(
            "commit",
            "--quiet",
            "--allow-empty",
            "-m",
            f"v{version} score={list(score)}",
        )
        return self._git("rev-parse", "HEAD")

    # ---------------------------------------------------------------- lectures
    def nombre_de_versions(self) -> int:
        self.verifier_isolation()
        try:
            sortie = self._git("rev-list", "--count", "HEAD")
        except subprocess.CalledProcessError:
            return 0  # dépôt sans commit : `rev-list` échoue, ce n'est pas une erreur
        return int(sortie or 0)

    def versions(self) -> Sequence[str]:
        """Messages des commits, du plus ancien au plus récent."""
        if self.nombre_de_versions() == 0:
            return []
        return self._git("log", "--reverse", "--format=%s").splitlines()

    def resume(self) -> dict[str, Any]:
        return {
            "versions": self.nombre_de_versions(),
            "meilleur_score": list(self.meilleur_score) if self.meilleur_score else None,
            "propositions": len(self.decisions),
            "refus": sum(1 for decision in self.decisions if not decision.acceptee),
        }
