"""Preuves du limiteur de concurrence des requêtes LLM (§H4.9).

@verifies docs/BACKLOG.md U32 — Limitation de concurrence des requêtes LLM par endpoint
@verifies docs/SPEC_HARNAIS.md §H4.9 (jetons de fichiers, attente bornée, jeton
          périmé, `429`/`RateLimited` avec `Retry-After`, activation live
          uniquement, désactivation par `0`), §H3.1 (variables), §H4.5 (attente
          minimale honorée par les retries)
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any

from avo.config import Config, ConfigInvalide, Mode, charger
from avo.llm.client import LLMClient, RateLimited, ReponseHTTP
from avo.llm.concurrence import (
    LimiteurConcurrence,
    PatienceEpuisee,
    dossier_endpoint,
)
from avo.transport import avec_retries


def _config_rejeu(**env: str) -> Config:
    return charger(Mode.REJEU, env=env, racine=Path("/inexistant"))


def _config_live(slots: Path, **env: str) -> Config:
    base = {
        "OLLAMA_HOST": "https://endpoint.example",
        "OLLAMA_API_KEY": "cle-de-test",
        "OLLAMA_CONTEXT_LENGTH": "8192",
        "AVO_LLM_SLOTS_DIR": str(slots),
        "ARC_API_KEY": "00000000-0000-0000-0000-000000000000",
    }
    base.update(env)
    return charger(Mode.LIVE, env=base, racine=Path("/inexistant"))


class TestLimiteur(unittest.TestCase):
    """§H4.9 : jetons de fichiers — acquisition, libération, plafond, péremption."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dossier = Path(self._tmp.name) / "slots"
        self.addCleanup(self._tmp.cleanup)

    def _limiteur(self, plafond: int = 2, timeout_s: float = 10.0) -> LimiteurConcurrence:
        return LimiteurConcurrence(
            dossier=self.dossier,
            plafond=plafond,
            timeout_s=timeout_s,
            dormir=lambda _s: None,
            alea=lambda: 0.5,
        )

    def test_jeton_cree_puis_libere(self) -> None:
        limiteur = self._limiteur()
        with limiteur.jeton():
            jetons = list(self.dossier.glob("slot-*"))
            self.assertEqual(len(jetons), 1)
            contenu = json.loads(jetons[0].read_text())
            self.assertEqual(contenu["pid"], os.getpid())
        self.assertEqual(list(self.dossier.glob("slot-*")), [])

    def test_jeton_libere_meme_sur_exception(self) -> None:
        limiteur = self._limiteur()
        with self.assertRaises(RuntimeError):
            with limiteur.jeton():
                raise RuntimeError("panne pendant la requête")
        self.assertEqual(list(self.dossier.glob("slot-*")), [])

    def test_plafond_tenu_sous_fils_concurrents(self) -> None:
        limiteur = LimiteurConcurrence(
            dossier=self.dossier, plafond=2, timeout_s=30.0, alea=lambda: 0.5
        )
        verrou = threading.Lock()
        en_cours = 0
        pic = 0

        def travailler() -> None:
            nonlocal en_cours, pic
            for _ in range(5):
                with limiteur.jeton():
                    with verrou:
                        en_cours += 1
                        pic = max(pic, en_cours)
                    with verrou:
                        en_cours -= 1

        fils = [threading.Thread(target=travailler) for _ in range(6)]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join()
        self.assertLessEqual(pic, 2)
        self.assertEqual(list(self.dossier.glob("slot-*")), [])

    def test_jeton_perime_repris(self) -> None:
        limiteur = self._limiteur(plafond=1, timeout_s=10.0)
        self.dossier.mkdir(parents=True)
        abandonne = self.dossier / "slot-0"
        abandonne.write_text('{"pid": 0}')
        # Plus vieux que timeout_s + la marge de péremption : occupant réputé mort.
        os.utime(abandonne, (0, 0))
        with limiteur.jeton():
            self.assertEqual(len(list(self.dossier.glob("slot-*"))), 1)
        self.assertEqual(list(self.dossier.glob("slot-*")), [])

    def test_jeton_frais_jamais_vole(self) -> None:
        limiteur = self._limiteur(plafond=1, timeout_s=1.0)
        self.dossier.mkdir(parents=True)
        occupe = self.dossier / "slot-0"
        occupe.write_text('{"pid": 1}')
        with self.assertRaises(PatienceEpuisee):
            with limiteur.jeton():
                pass
        self.assertTrue(occupe.exists())

    def test_patience_epuisee_nomme_l_etat(self) -> None:
        limiteur = self._limiteur(plafond=1, timeout_s=1.0)
        self.dossier.mkdir(parents=True)
        (self.dossier / "slot-0").write_text('{"pid": 1234}')
        with self.assertRaises(PatienceEpuisee) as constat:
            with limiteur.jeton():
                pass
        message = str(constat.exception)
        self.assertIn(str(self.dossier), message)
        self.assertIn("slot-0", message)
        self.assertIn("1234", message)

    def test_plafond_zero_desactive_sans_repertoire(self) -> None:
        limiteur = self._limiteur(plafond=0)
        with limiteur.jeton():
            pass
        self.assertFalse(self.dossier.exists())

    def test_dossier_par_endpoint(self) -> None:
        racine = Path(self._tmp.name)
        a = dossier_endpoint(racine, "https://a.example")
        b = dossier_endpoint(racine, "https://b.example")
        self.assertNotEqual(a, b)
        self.assertEqual(a, dossier_endpoint(racine, "https://a.example"))
        self.assertEqual(a.parent, racine)


class TestConfiguration(unittest.TestCase):
    """§H3.1 : `AVO_LLM_MAX_CONCURRENT` (0 admis), `AVO_LLM_SLOTS_DIR` (défaut)."""

    def test_defauts(self) -> None:
        config = _config_rejeu()
        self.assertEqual(config.llm_max_concurrent, 3)
        self.assertEqual(config.llm_slots_dir, config.runs_dir / ".llm-slots")

    def test_zero_admis_negatif_refuse(self) -> None:
        self.assertEqual(_config_rejeu(AVO_LLM_MAX_CONCURRENT="0").llm_max_concurrent, 0)
        with self.assertRaises(ConfigInvalide):
            _config_rejeu(AVO_LLM_MAX_CONCURRENT="-1")

    def test_repertoire_surcharge(self) -> None:
        config = _config_rejeu(AVO_LLM_SLOTS_DIR="/partage/jetons")
        self.assertEqual(config.llm_slots_dir, Path("/partage/jetons"))

    def test_resume_sans_secret(self) -> None:
        resume = _config_rejeu().resume()
        self.assertEqual(resume["llm_max_concurrent"], 3)
        self.assertIn("llm_slots_dir", resume)


class _TransportScripte:
    def __init__(self, *reponses: ReponseHTTP | Exception) -> None:
        self.reponses = list(reponses)
        self.appels = 0
        self.jetons_pendant_appel: list[int] = []
        self.dossier: Path | None = None

    def __call__(self, url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
        if self.dossier is not None:
            self.jetons_pendant_appel.append(len(list(self.dossier.glob("slot-*"))))
        self.appels += 1
        suivante = self.reponses[min(self.appels - 1, len(self.reponses) - 1)]
        if isinstance(suivante, Exception):
            raise suivante
        return suivante


def _ok() -> ReponseHTTP:
    return ReponseHTTP(200, json.dumps({"message": {"content": "OK"}, "done": True}).encode())


class TestClientSousLimiteur(unittest.TestCase):
    """§H4.9 : le client live tient un jeton par tentative et le libère toujours."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.slots = Path(self._tmp.name) / "slots"
        self.addCleanup(self._tmp.cleanup)

    def test_live_acquiert_et_libere_le_jeton(self) -> None:
        config = _config_live(self.slots)
        transport = _TransportScripte(_ok())
        transport.dossier = dossier_endpoint(self.slots, config.ollama_host)
        client = LLMClient(config, transport=transport, dormir=lambda _s: None)
        client.chat([{"role": "user", "content": "bonjour"}])
        self.assertEqual(transport.jetons_pendant_appel, [1])
        self.assertEqual(list(transport.dossier.glob("slot-*")), [])

    def test_rejeu_sans_limiteur_ni_repertoire(self) -> None:
        config = _config_rejeu(AVO_LLM_SLOTS_DIR=str(self.slots))
        client = LLMClient(config, transport=_TransportScripte(_ok()))
        client.chat([{"role": "user", "content": "bonjour"}])
        self.assertFalse(self.slots.exists())

    def test_desactive_par_zero_en_live(self) -> None:
        config = _config_live(self.slots, AVO_LLM_MAX_CONCURRENT="0")
        client = LLMClient(config, transport=_TransportScripte(_ok()))
        client.chat([{"role": "user", "content": "bonjour"}])
        self.assertFalse(self.slots.exists())


class TestRateLimited(unittest.TestCase):
    """§H4.9 : `429` = patienter — retentée, `Retry-After` honoré quand plus long."""

    def _client(self, transport: _TransportScripte, attentes: list[float]) -> LLMClient:
        config = _config_rejeu()
        return LLMClient(
            config,
            transport=transport,
            dormir=attentes.append,
            alea=lambda: 0.5,
        )

    def test_429_retentee_jusqu_au_succes(self) -> None:
        transport = _TransportScripte(ReponseHTTP(429, b""), _ok())
        attentes: list[float] = []
        resultat = self._client(transport, attentes).chat([{"role": "user", "content": "x"}])
        self.assertEqual(resultat.content, "OK")
        self.assertEqual(transport.appels, 2)
        self.assertEqual(len(attentes), 1)

    def test_retry_after_prime_sur_le_palier(self) -> None:
        transport = _TransportScripte(ReponseHTTP(429, b"", retry_after_s=300.0), _ok())
        attentes: list[float] = []
        self._client(transport, attentes).chat([{"role": "user", "content": "x"}])
        self.assertEqual(attentes, [300.0])

    def test_palier_prime_sur_un_retry_after_plus_court(self) -> None:
        # Paliers (alea 0,5, sans jitter effectif) : 1, 4, 16 s ; un Retry-After
        # de 0,5 s, plus court que chacun, ne raccourcit jamais l'attente.
        transport = _TransportScripte(
            ReponseHTTP(429, b"", retry_after_s=0.5),
            ReponseHTTP(429, b"", retry_after_s=0.5),
            ReponseHTTP(429, b"", retry_after_s=0.5),
            _ok(),
        )
        attentes: list[float] = []
        self._client(transport, attentes).chat([{"role": "user", "content": "x"}])
        self.assertEqual(attentes, [1.0, 4.0, 16.0])

    def test_epuisement_remonte_rate_limited(self) -> None:
        transport = _TransportScripte(ReponseHTTP(429, b""))
        attentes: list[float] = []
        with self.assertRaises(RateLimited):
            self._client(transport, attentes).chat([{"role": "user", "content": "x"}])
        self.assertEqual(transport.appels, 6)


class TestAttenteMinimale(unittest.TestCase):
    """§H4.5 amendé : `avec_retries` honore `attente_minimale_s` de l'erreur."""

    def test_attente_minimale_honoree(self) -> None:
        attentes: list[float] = []
        compteur = {"appels": 0}

        def tenter() -> str:
            compteur["appels"] += 1
            if compteur["appels"] == 1:
                erreur = RuntimeError("file d'attente")
                erreur.attente_minimale_s = 42.0  # type: ignore[attr-defined]
                raise erreur
            return "ok"

        resultat = avec_retries(tenter, (RuntimeError,), dormir=attentes.append, alea=lambda: 0.5)
        self.assertEqual(resultat, "ok")
        self.assertEqual(attentes, [42.0])


if __name__ == "__main__":
    unittest.main()
