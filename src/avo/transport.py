"""Politique de transport partagée : retries bornés, jitter, aucun secret.

@spec docs/BACKLOG.md U17 — Client API ARC
@spec docs/SPEC_HARNAIS.md §H4.5 (retries bornés avec jitter), §H4.6 (sans secret)
@spec docs/SPEC_ARCAGI3.md §A2.1 (« mêmes règles transport que H4.5/H4.6 »)

La spécification du client ARC exige les **mêmes** règles que celles du client
d'inférence. Deux implémentations parallèles finiraient par diverger sans que rien
ne le signale : elles partagent donc celle-ci.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar

#: Attentes entre deux tentatives, en secondes (§H4.5). Cinq nouvelles tentatives
#: suivent l'échec initial, soit six requêtes au plus. Les deux paliers longs
#: absorbent les pannes transitoires de quelques minutes : à travers un pont qui
#: coupe avant les premiers en-têtes, chaque tentative échouée fait néanmoins
#: avancer le cache de préfixe du serveur (mesuré le 2026-09-01, `pilote-u24c`).
ATTENTES_RETRY: tuple[float, ...] = (1.0, 4.0, 16.0, 45.0, 90.0)

#: Amplitude du jitter appliqué à chaque attente (§H4.5).
JITTER = 0.25

T = TypeVar("T")


def attente(tentative: int, alea: Callable[[], float] = random.random) -> float:
    """Attente de la n-ième nouvelle tentative, jitter compris (§H4.5)."""
    base = ATTENTES_RETRY[tentative]
    return base * (1.0 + (alea() * 2.0 - 1.0) * JITTER)


def avec_retries(
    tenter: Callable[[], T],
    retryables: tuple[type[Exception], ...],
    dormir: Callable[[float], None] = time.sleep,
    alea: Callable[[], float] = random.random,
    journal: logging.Logger | None = None,
) -> T:
    """Exécute `tenter`, en réessayant les seules erreurs déclarées retryables.

    Une erreur non listée remonte immédiatement : un refus d'authentification ou un
    dépassement de contexte se reproduiraient à l'identique, les retenter ne ferait
    que retarder le diagnostic.
    """
    derniere: Exception | None = None
    for tentative in range(len(ATTENTES_RETRY) + 1):
        try:
            return tenter()
        except retryables as erreur:
            derniere = erreur
            if tentative == len(ATTENTES_RETRY):
                break
            delai = attente(tentative, alea)
            if journal is not None:
                journal.info(
                    "nouvelle tentative",
                    extra={
                        "tentative": tentative + 1,
                        "attente_s": round(delai, 2),
                        "motif": type(erreur).__name__,
                    },
                )
            dormir(delai)
    assert derniere is not None  # noqa: S101 — la boucle ne sort ainsi qu'après un échec
    raise derniere
