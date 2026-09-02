"""Preuves du client d'inférence : requête, réponse, erreurs, retries.

@verifies docs/BACKLOG.md U7 — Client d'inférence
@verifies docs/SPEC_HARNAIS.md §H4.2 (requête), §H4.3 (réponse typée),
          §H4.4 (erreurs typées), §H4.5 (retries bornés avec jitter),
          §H4.6 (aucun secret journalisé)

Le transport, l'attente et l'aléa sont injectés : la politique de retry est éprouvée
sans réseau et sans attente réelle.
"""

from __future__ import annotations

import http.client
import json
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from avo.config import Config, Mode, charger
from avo.llm.client import (
    AuthError,
    ChatResult,
    ContextOverflow,
    LLMClient,
    ProtocolError,
    ReponseHTTP,
    ServerError,
    TransportError,
    analyser_corps_chat,
    analyser_reponse,
    construire_corps,
    transport_urllib,
)
from avo.transport import ATTENTES_RETRY, JITTER

_MESSAGES = [{"role": "user", "content": "bonjour"}]


def _config(**env: str) -> Config:
    return charger(Mode.REJEU, env=env, racine=Path("/inexistant"))


class _TransportScripte:
    """Transport de test : rend ou lève ce qu'on lui a scripté, et compte les appels."""

    def __init__(self, *reponses: ReponseHTTP | Exception) -> None:
        self.reponses = list(reponses)
        self.appels: list[tuple[str, bytes, dict[str, str]]] = []

    def __call__(self, url: str, corps: bytes, entetes: Any, timeout: float) -> ReponseHTTP:
        self.appels.append((url, corps, dict(entetes)))
        suivante = self.reponses[min(len(self.appels) - 1, len(self.reponses) - 1)]
        if isinstance(suivante, Exception):
            raise suivante
        return suivante


class _AleaConstante:
    """Aléa déterministe : rend toujours le même tirage, pour borner le jitter."""

    def __init__(self, valeur: float) -> None:
        self.valeur = valeur

    def __call__(self) -> float:
        return self.valeur


def _ok(charge: dict[str, Any]) -> ReponseHTTP:
    return ReponseHTTP(200, json.dumps(charge).encode())


class TestConstructionDuCorps(unittest.TestCase):
    """§H4.2 : le corps porte model, stream, think, options et messages."""

    def test_champs_obligatoires_presents(self) -> None:
        corps = construire_corps(_config(), _MESSAGES)
        self.assertEqual(corps["model"], "qwen3.6:35b")
        self.assertTrue(corps["stream"])
        self.assertFalse(corps["think"])
        self.assertEqual(corps["messages"], _MESSAGES)
        self.assertEqual(set(corps["options"]), {"num_ctx", "num_predict", "temperature"})

    def test_les_outils_ne_sont_presents_que_s_ils_sont_fournis(self) -> None:
        self.assertNotIn("tools", construire_corps(_config(), _MESSAGES))
        outils = [{"type": "function", "function": {"name": "run_shell"}}]
        self.assertEqual(construire_corps(_config(), _MESSAGES, outils)["tools"], outils)

    def test_les_surcharges_priment_sur_la_configuration(self) -> None:
        corps = construire_corps(_config(), _MESSAGES, num_ctx=8192, num_predict=64, temperature=0)
        self.assertEqual(corps["options"], {"num_ctx": 8192, "num_predict": 64, "temperature": 0})

    def test_think_suit_la_configuration(self) -> None:
        corps = construire_corps(_config(AVO_THINK="true", AVO_NUM_PREDICT="8192"), _MESSAGES)
        self.assertTrue(corps["think"])


class TestAssemblageDuFlux(unittest.TestCase):
    """§H4.3 : le corps 2xx admet deux formes — objet unique ou lignes NDJSON.

    @verifies docs/BACKLOG.md U29a4 — campagne de banc (correctif transport désigné
              par la mesure du 2026-09-02 : générations longues coupées par le pont)
    @verifies docs/SPEC_HARNAIS.md §H4.2 (stream), §H4.3 (assemblage des fragments)
    """

    def _ndjson(self, *fragments: dict[str, Any]) -> ReponseHTTP:
        corps = "\n".join(json.dumps(fragment) for fragment in fragments)
        return ReponseHTTP(200, corps.encode())

    def test_fragments_assembles_contenu_raisonnement_et_compteurs(self) -> None:
        resultat = analyser_corps_chat(
            self._ndjson(
                {"model": "m", "message": {"content": "", "thinking": "je "}, "done": False},
                {"model": "m", "message": {"content": "O", "thinking": "réfléchis"}, "done": False},
                {"model": "m", "message": {"content": "K"}, "done": False},
                {
                    "model": "m",
                    "message": {"content": ""},
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 24,
                    "eval_count": 218,
                    "total_duration": 6_600_000_000,
                },
            )
        )
        self.assertEqual(resultat.content, "OK")
        self.assertEqual(resultat.reasoning, "je réfléchis")
        self.assertEqual(resultat.done_reason, "stop")
        self.assertEqual(resultat.prompt_eval_count, 24)
        self.assertEqual(resultat.eval_count, 218)
        self.assertEqual(resultat.total_duration_ms, 6600)

    def test_appels_d_outil_collectes_sur_les_fragments(self) -> None:
        resultat = analyser_corps_chat(
            self._ndjson(
                {
                    "message": {
                        "content": "",
                        "tool_calls": [{"function": {"name": "agir", "arguments": {"a": 1}}}],
                    },
                    "done": False,
                },
                {"message": {"content": ""}, "done": True, "done_reason": "stop"},
            )
        )
        self.assertTrue(resultat.demande_outil)
        self.assertEqual(resultat.tool_calls[0].nom, "agir")
        self.assertEqual(resultat.tool_calls[0].arguments, {"a": 1})

    def test_objet_unique_reste_la_forme_non_streamee(self) -> None:
        resultat = analyser_corps_chat(
            ReponseHTTP(200, json.dumps({"message": {"content": "OK"}, "done": True}).encode())
        )
        self.assertEqual(resultat.content, "OK")

    def test_flux_sans_fragment_final_est_une_panne_de_transport(self) -> None:
        with self.assertRaises(TransportError):
            analyser_corps_chat(
                self._ndjson(
                    {"message": {"content": "dé"}, "done": False},
                    {"message": {"content": "but"}, "done": False},
                )
            )

    def test_fragment_final_tronque_est_une_panne_de_transport(self) -> None:
        corps = json.dumps({"message": {"content": "dé"}, "done": False}) + '\n{"message": {"con'
        with self.assertRaises(TransportError):
            analyser_corps_chat(ReponseHTTP(200, corps.encode()))

    def test_erreur_en_cours_de_flux_est_une_panne_serveur(self) -> None:
        with self.assertRaises(ServerError):
            analyser_corps_chat(
                self._ndjson(
                    {"message": {"content": "dé"}, "done": False},
                    {"error": "le serveur a déchargé le modèle"},
                )
            )

    def test_premiere_ligne_non_json_reste_une_erreur_de_protocole(self) -> None:
        with self.assertRaises(ProtocolError):
            analyser_corps_chat(ReponseHTTP(200, b"<html>panne</html>"))

    def test_corps_vide_est_une_erreur_de_protocole(self) -> None:
        with self.assertRaises(ProtocolError):
            analyser_corps_chat(ReponseHTTP(200, b""))

    def test_flux_tronque_est_retente_par_le_client(self) -> None:
        """§H4.5 : la troncature en cours de flux se retente comme toute panne."""
        tronque = ReponseHTTP(200, b'{"message": {"content": "d\\u00e9"}, "done": false}')
        complet = ReponseHTTP(200, b'{"message": {"content": "OK"}, "done": true}')
        # Un seul fragment sans done est la forme « objet unique » : pour éprouver le
        # retry, le flux tronqué porte DEUX fragments sans fragment final.
        corps_tronque = tronque.body + b"\n" + tronque.body
        transport = _TransportScripte(ReponseHTTP(200, corps_tronque), complet)
        client = LLMClient(_config(), transport=transport, dormir=lambda _s: None)
        resultat = client.chat(_MESSAGES)
        self.assertEqual(resultat.content, "OK")
        self.assertEqual(len(transport.appels), 2)


class TestAnalyseDeLaReponse(unittest.TestCase):
    """§H4.3 : normalisation en ChatResult."""

    def test_contenu_raisonnement_et_compteurs(self) -> None:
        resultat = analyser_reponse(
            {
                "model": "m",
                "message": {"role": "assistant", "content": "OK", "thinking": "je réfléchis"},
                "done_reason": "stop",
                "prompt_eval_count": 24,
                "eval_count": 218,
                "total_duration": 6_600_000_000,
                "prompt_eval_duration": 160_000_000,
                "eval_duration": 103_000_000,
            }
        )
        self.assertEqual(resultat.content, "OK")
        self.assertEqual(resultat.reasoning, "je réfléchis")
        self.assertEqual(resultat.prompt_eval_count, 24)
        self.assertEqual(resultat.eval_count, 218)
        self.assertEqual(resultat.total_duration_ms, 6600)
        self.assertEqual(resultat.prompt_eval_duration_ms, 160)
        self.assertFalse(resultat.tronquee)

    def test_reponse_tronquee_detectee(self) -> None:
        """Symptôme mesuré du raisonnement qui dévore le budget de sortie (§H12.1)."""
        resultat = analyser_reponse({"message": {"content": ""}, "done_reason": "length"})
        self.assertTrue(resultat.tronquee)
        self.assertEqual(resultat.content, "")

    def test_demande_outil_ne_depend_pas_de_done_reason(self) -> None:
        """§H4.3 : sur la surface native, un appel d'outil arrive avec « stop »."""
        avec_outil = analyser_reponse(
            {
                "done_reason": "stop",
                "message": {
                    "content": "",
                    "tool_calls": [{"function": {"name": "f", "arguments": {"x": 1}}}],
                },
            }
        )
        self.assertTrue(avec_outil.demande_outil)
        sans_outil = analyser_reponse({"done_reason": "stop", "message": {"content": "OK"}})
        self.assertFalse(sans_outil.demande_outil)

    def test_reponse_sans_message_est_une_erreur_de_protocole(self) -> None:
        with self.assertRaises(ProtocolError):
            analyser_reponse({"done_reason": "stop"})

    def test_appel_d_outil_avec_arguments_objet(self) -> None:
        resultat = analyser_reponse(
            {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "a1",
                            "function": {"name": "run_shell", "arguments": {"command": "ls"}},
                        }
                    ],
                }
            }
        )
        appel = resultat.tool_calls[0]
        self.assertEqual(appel.nom, "run_shell")
        self.assertEqual(appel.arguments, {"command": "ls"})
        self.assertTrue(appel.valide)

    def test_appel_d_outil_avec_arguments_en_chaine_json(self) -> None:
        resultat = analyser_reponse(
            {
                "message": {
                    "content": "",
                    "tool_calls": [{"function": {"name": "f", "arguments": '{"x": 1}'}}],
                }
            }
        )
        self.assertEqual(resultat.tool_calls[0].arguments, {"x": 1})

    def test_arguments_invalides_ne_levent_pas_d_exception(self) -> None:
        """§H4.3 : c'est une erreur d'outil rendue au modèle, pas un run interrompu."""
        resultat = analyser_reponse(
            {
                "message": {
                    "content": "",
                    "tool_calls": [{"function": {"name": "f", "arguments": "{pas du json"}}],
                }
            }
        )
        appel = resultat.tool_calls[0]
        self.assertFalse(appel.valide)
        self.assertIsNotNone(appel.erreur_arguments)
        self.assertEqual(appel.arguments_bruts, "{pas du json")


class TestTransportUrllib(unittest.TestCase):
    """§H4.4 : toute panne de réseau du transport réel est TYPÉE, jamais brute.

    Mesuré le 2026-09-01 (relevé live du banc) : un pont qui coupe après l'envoi
    de la requête mais avant les premiers en-têtes lève `RemoteDisconnected`,
    que `urllib` n'enveloppe pas en `URLError` — non typée, elle arrêtait le run
    au lieu d'être retentée (§H4.5).
    """

    def _leve(self, erreur: Exception) -> None:
        with mock.patch("urllib.request.urlopen", side_effect=erreur):
            with self.assertRaises(TransportError) as contexte:
                transport_urllib("https://exemple.invalide/api/chat", b"{}", {}, timeout=1.0)
        self.assertIn("connexion interrompue", str(contexte.exception))

    def test_remote_disconnected_devient_transport_error(self) -> None:
        self._leve(http.client.RemoteDisconnected("Remote end closed connection"))

    def test_connection_reset_nu_devient_transport_error(self) -> None:
        self._leve(ConnectionResetError(104, "Connection reset by peer"))


class TestErreursTypees(unittest.TestCase):
    """§H4.4 : chaque statut se traduit par une erreur nommée."""

    def _client(self, *reponses: ReponseHTTP | Exception) -> tuple[LLMClient, _TransportScripte]:
        transport = _TransportScripte(*reponses)
        return LLMClient(_config(), transport=transport, dormir=lambda _: None), transport

    def test_401_et_403_sont_fatals(self) -> None:
        for statut in (401, 403):
            with self.subTest(statut=statut):
                client, transport = self._client(ReponseHTTP(statut, b'{"error":"refus"}'))
                with self.assertRaises(AuthError):
                    client.chat(_MESSAGES)
                self.assertEqual(len(transport.appels), 1, "une erreur d'auth ne se retente pas")

    def test_413_porte_les_champs_reels_du_corps(self) -> None:
        corps = json.dumps(
            {
                "error": "contexte de la requête trop grand pour cette clé",
                "tokens_estimated": 248803,
                "max_context_tokens": 229376,
            }
        ).encode()
        client, transport = self._client(ReponseHTTP(413, corps))
        with self.assertRaises(ContextOverflow) as capture:
            client.chat(_MESSAGES)
        self.assertEqual(capture.exception.tokens_estimated, 248803)
        self.assertEqual(capture.exception.max_context_tokens, 229376)
        self.assertEqual(len(transport.appels), 1, "un 413 ne se retente pas")

    def test_400_est_une_erreur_de_protocole_non_retentee(self) -> None:
        client, transport = self._client(ReponseHTTP(400, b'{"error":"corps invalide"}'))
        with self.assertRaises(ProtocolError):
            client.chat(_MESSAGES)
        self.assertEqual(len(transport.appels), 1)

    def test_reponse_2xx_non_json_est_une_erreur_de_protocole(self) -> None:
        client, _ = self._client(ReponseHTTP(200, b"<html>"))
        with self.assertRaises(ProtocolError):
            client.chat(_MESSAGES)


class TestPolitiqueDeRetry(unittest.TestCase):
    """§H4.5 : trois nouvelles tentatives, uniquement sur 5xx et transport."""

    def _client_avec_attentes(
        self, *reponses: ReponseHTTP | Exception
    ) -> tuple[LLMClient, _TransportScripte, list[float]]:
        attentes: list[float] = []
        transport = _TransportScripte(*reponses)
        client = LLMClient(_config(), transport=transport, dormir=attentes.append, alea=lambda: 0.5)
        return client, transport, attentes

    def test_erreur_serveur_puis_succes(self) -> None:
        client, transport, attentes = self._client_avec_attentes(
            ReponseHTTP(500, b"{}"),
            _ok({"message": {"content": "OK"}}),
        )
        resultat = client.chat(_MESSAGES)
        self.assertEqual(resultat.content, "OK")
        self.assertEqual(len(transport.appels), 2)
        self.assertEqual(len(attentes), 1)

    def test_echec_persistant_epuise_les_tentatives_puis_leve(self) -> None:
        client, transport, attentes = self._client_avec_attentes(ReponseHTTP(503, b"{}"))
        with self.assertRaises(ServerError) as capture:
            client.chat(_MESSAGES)
        self.assertEqual(capture.exception.status, 503)
        self.assertEqual(len(transport.appels), len(ATTENTES_RETRY) + 1)
        self.assertEqual(len(attentes), len(ATTENTES_RETRY))

    def test_erreur_de_transport_est_retentee(self) -> None:
        client, transport, _ = self._client_avec_attentes(
            TransportError("réseau coupé"),
            _ok({"message": {"content": "OK"}}),
        )
        self.assertEqual(client.chat(_MESSAGES).content, "OK")
        self.assertEqual(len(transport.appels), 2)

    def test_les_attentes_suivent_le_backoff_avec_jitter_borne(self) -> None:
        client, _, attentes = self._client_avec_attentes(ReponseHTTP(500, b"{}"))
        with self.assertRaises(ServerError):
            client.chat(_MESSAGES)
        for observee, base in zip(attentes, ATTENTES_RETRY, strict=True):
            self.assertGreaterEqual(observee, base * (1 - JITTER))
            self.assertLessEqual(observee, base * (1 + JITTER))

    def test_le_jitter_varie_reellement_autour_de_la_base(self) -> None:
        for tirage, attendu in ((0.0, 1 - JITTER), (1.0, 1 + JITTER)):
            transport = _TransportScripte(ReponseHTTP(500, b"{}"))
            attentes: list[float] = []
            alea = _AleaConstante(tirage)
            client = LLMClient(_config(), transport=transport, dormir=attentes.append, alea=alea)
            with self.assertRaises(ServerError):
                client.chat(_MESSAGES)
            self.assertAlmostEqual(attentes[0], ATTENTES_RETRY[0] * attendu, places=6)


class TestAucunSecretJournalise(unittest.TestCase):
    """§H4.6 : la clé ne doit apparaître dans aucun journal."""

    def test_les_journaux_ne_portent_ni_cle_ni_en_tete(self) -> None:
        config = _config(OLLAMA_API_KEY="sk-secret-a-ne-pas-journaliser")
        transport = _TransportScripte(_ok({"message": {"content": "OK"}, "eval_count": 3}))
        client = LLMClient(config, transport=transport, dormir=lambda _: None)
        with self.assertLogs("avo.llm", level="INFO") as journaux:
            client.chat(_MESSAGES)
        trace = "\n".join(journaux.output)
        self.assertNotIn("sk-secret-a-ne-pas-journaliser", trace)
        self.assertNotIn("Authorization", trace)

    def test_le_resume_ne_contient_aucun_contenu_de_message(self) -> None:
        resultat = ChatResult(content="texte confidentiel", reasoning="secret")
        resume = resultat.resume()
        self.assertNotIn("texte confidentiel", str(resume))
        self.assertEqual(resume["content_chars"], len("texte confidentiel"))

    def test_l_en_tete_d_autorisation_est_bien_envoye(self) -> None:
        """La clé part au serveur — ce qui est interdit, c'est de la JOURNALISER."""
        config = _config(OLLAMA_API_KEY="sk-de-test")
        transport = _TransportScripte(_ok({"message": {"content": "OK"}}))
        LLMClient(config, transport=transport, dormir=lambda _: None).chat(_MESSAGES)
        self.assertEqual(transport.appels[0][2]["Authorization"], "Bearer sk-de-test")


class TestJournalisationDesRetries(unittest.TestCase):
    def test_chaque_retry_est_journalise(self) -> None:
        transport = _TransportScripte(ReponseHTTP(500, b"{}"))
        client = LLMClient(_config(), transport=transport, dormir=lambda _: None)
        with self.assertLogs("avo.llm", level="INFO") as journaux, self.assertRaises(ServerError):
            client.chat(_MESSAGES)
        tentatives = [ligne for ligne in journaux.output if "nouvelle tentative" in ligne]
        self.assertEqual(len(tentatives), len(ATTENTES_RETRY))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
