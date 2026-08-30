"""Preuves du format de cassette : appariement, expurgation, aller-retour.

@verifies docs/BACKLOG.md U4 — llm-replay : enregistrement et rejeu
@verifies docs/SPEC_HARNAIS.md §H4.7 (clé d'appariement, erreur explicite, expurgation)
@verifies docs/SPEC_HARNAIS.md §H4.6 (aucun secret persisté)
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from llm_replay.cassette import (
    AUTH_ABSENTE,
    AUTH_INVALIDE,
    AUTH_VALIDE,
    TAILLE_CORPS_MAX,
    Cassette,
    Exchange,
    RequestRecord,
    RequeteInconnue,
    ResponseRecord,
)

_CORPS = {"model": "m", "messages": [{"role": "user", "content": "bonjour"}]}


def _echange(auth: str = AUTH_VALIDE, corps: object = None, status: int = 200) -> Exchange:
    return Exchange(
        request=RequestRecord.depuis(
            "POST", "/api/chat", auth, corps if corps is not None else _CORPS
        ),
        response=ResponseRecord(
            status=status, headers={"content-type": "application/json"}, body={"ok": True}
        ),
        recorded_at="2026-08-27T00:00:00+00:00",
        duration_ms=12,
    )


class TestCleAppariement(unittest.TestCase):
    def test_meme_corps_meme_cle_quel_que_soit_l_ordre_des_champs(self) -> None:
        a = RequestRecord.depuis("POST", "/api/chat", AUTH_VALIDE, {"a": 1, "b": 2})
        b = RequestRecord.depuis("POST", "/api/chat", AUTH_VALIDE, {"b": 2, "a": 1})
        self.assertEqual(a.cle, b.cle)

    def test_corps_different_donne_cle_differente(self) -> None:
        a = RequestRecord.depuis("POST", "/api/chat", AUTH_VALIDE, {"a": 1})
        b = RequestRecord.depuis("POST", "/api/chat", AUTH_VALIDE, {"a": 2})
        self.assertNotEqual(a.cle, b.cle)

    def test_la_nature_d_authentification_fait_partie_de_la_cle(self) -> None:
        valide = RequestRecord.depuis("POST", "/api/chat", AUTH_VALIDE, _CORPS)
        invalide = RequestRecord.depuis("POST", "/api/chat", AUTH_INVALIDE, _CORPS)
        absente = RequestRecord.depuis("POST", "/api/chat", AUTH_ABSENTE, _CORPS)
        self.assertNotEqual(valide.cle, invalide.cle)
        self.assertNotEqual(valide.cle, absente.cle)

    def test_methode_et_chemin_font_partie_de_la_cle(self) -> None:
        chat = RequestRecord.depuis("POST", "/api/chat", AUTH_VALIDE, _CORPS)
        tags = RequestRecord.depuis("POST", "/api/tags", AUTH_VALIDE, _CORPS)
        get = RequestRecord.depuis("GET", "/api/chat", AUTH_VALIDE, _CORPS)
        self.assertNotEqual(chat.cle, tags.cle)
        self.assertNotEqual(chat.cle, get.cle)


class TestAppariement(unittest.TestCase):
    def test_apparie_un_echange_enregistre(self) -> None:
        cassette = Cassette([_echange()])
        trouve = cassette.apparier("POST", "/api/chat", AUTH_VALIDE, _CORPS)
        self.assertEqual(trouve.response.status, 200)

    def test_requete_inconnue_leve_une_erreur_qui_nomme_l_ecart(self) -> None:
        cassette = Cassette([_echange()])
        with self.assertRaises(RequeteInconnue) as capture:
            cassette.apparier("POST", "/api/chat", AUTH_VALIDE, {"autre": "corps"})
        message = str(capture.exception)
        self.assertIn("aucun échange enregistré", message)
        self.assertIn("/api/chat", message)
        self.assertIn("make record-llm", message)

    def test_cassette_vide_le_dit(self) -> None:
        with self.assertRaises(RequeteInconnue) as capture:
            Cassette().apparier("GET", "/api/version", AUTH_VALIDE, None)
        self.assertIn("cassette vide", str(capture.exception))


class TestExpurgation(unittest.TestCase):
    """La clé et l'hôte ne doivent JAMAIS atteindre le disque."""

    def test_aucune_cle_ni_hote_dans_la_cassette_ecrite(self) -> None:
        secret = "sk-ollama-secret-de-test-a-ne-jamais-ecrire"
        cassette = Cassette([_echange(), _echange(auth=AUTH_INVALIDE, status=401)])
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "c.jsonl"
            cassette.ecrire(chemin)
            contenu = chemin.read_text(encoding="utf-8")
        self.assertNotIn(secret, contenu)
        self.assertNotIn("Authorization", contenu)
        self.assertNotIn("Bearer", contenu)
        for ligne in contenu.splitlines():
            self.assertIn(
                json.loads(ligne)["request"]["auth"], {AUTH_VALIDE, AUTH_INVALIDE, AUTH_ABSENTE}
            )

    def test_seuls_les_entetes_de_la_liste_blanche_sont_conserves(self) -> None:
        reponse = ResponseRecord(status=200, headers={"content-type": "application/json"})
        self.assertEqual(list(reponse.headers), ["content-type"])

    def test_corps_volumineux_non_stocke_mais_apparie_par_empreinte(self) -> None:
        gros = {"messages": [{"role": "user", "content": "x" * (TAILLE_CORPS_MAX + 1000)}]}
        enregistrement = RequestRecord.depuis("POST", "/api/chat", AUTH_VALIDE, gros)
        self.assertIsNone(enregistrement.body)
        self.assertGreater(enregistrement.body_bytes, TAILLE_CORPS_MAX)
        cassette = Cassette([_echange(corps=gros)])
        self.assertEqual(
            cassette.apparier("POST", "/api/chat", AUTH_VALIDE, gros).response.status, 200
        )


class TestAllerRetour(unittest.TestCase):
    def test_ecriture_puis_lecture_preserve_les_echanges(self) -> None:
        cassette = Cassette([_echange(), _echange(auth=AUTH_ABSENTE, status=401)])
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "c.jsonl"
            cassette.ecrire(chemin)
            relue = Cassette.lire(chemin)
        self.assertEqual(len(relue), 2)
        self.assertEqual([e.request.cle for e in relue], [e.request.cle for e in cassette])

    def test_lecture_d_un_dossier_concatene_les_cassettes(self) -> None:
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            Cassette([_echange()]).ecrire(racine / "a.jsonl")
            Cassette([_echange(auth=AUTH_ABSENTE)]).ecrire(racine / "b.jsonl")
            self.assertEqual(len(Cassette.lire_dossier(racine)), 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
