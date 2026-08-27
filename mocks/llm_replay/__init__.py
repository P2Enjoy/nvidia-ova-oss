"""`llm-replay` — enregistrement et rejeu des échanges du VRAI endpoint d'inférence.

@spec docs/BACKLOG.md U4 — llm-replay : enregistrement et rejeu du vrai endpoint
@spec docs/SPEC_HARNAIS.md §H4.7

Ce paquet ne simule pas l'endpoint : il capture ses échanges HTTP réels puis les
rejoue à l'identique. Le contrat servi en test est donc toujours d'origine mesurée
(CLAUDE.md §15 : un service exécutable localement ne se mocke pas).
"""

from llm_replay.cassette import Cassette, Exchange, RequestRecord, ResponseRecord

__all__ = ["Cassette", "Exchange", "RequestRecord", "ResponseRecord"]
