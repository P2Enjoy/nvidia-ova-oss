# Contrat des commandes du dépôt — TOUT s'exécute dans Docker.
#
# @spec docs/BACKLOG.md U3 — Squelette Python et outillage (chaîne conteneurisée)
# @spec docs/SPEC_HARNAIS.md §H2.1 (outillage), §H2.3 (commandes), §H2.4 (conteneurisation)
# @spec docs/MASTER_PLAN.md §4 (classes de preuves, campagne complète)
#
# Règle du responsable (2026-08-27) : rien n'est installé sur la machine hôte.
# L'outillage (pytest, ruff, mypy) vit dans l'image `avo-dev` ; chaque cible
# lance un conteneur jetable sur le dépôt monté en volume.
#
# Échappatoire AVO_NO_DOCKER=1 : exécute les tests sur l'hôte avec la SEULE
# bibliothèque standard (unittest), sans rien installer. C'est un mode DÉGRADÉ
# — lint et typecheck y sont indisponibles — et il l'annonce (CLAUDE.md §18).

SHELL := /bin/bash
IMAGE ?= avo-dev
IMAGE_PROD ?= avo
PY ?= python3
PYTEST_ARGS ?=
ARGS ?=
RUN_ID ?=

DOCKER := $(shell command -v docker 2>/dev/null)
UIDGID := $(shell id -u):$(shell id -g)

# AVO_IN_CONTAINER est posé par l'image : les cibles y appellent les outils
# directement, au lieu de relancer un conteneur depuis un conteneur. C'est ce
# qui permet d'exécuter la campagne complète avec Docker pour seul prérequis :
#   docker run --rm -v "$$PWD":/app -w /app --user $$(id -u):$$(id -g) \
#     -e HOME=/tmp avo-dev make check
# En mode rootless, l'utilisateur de l'hôte est DÉJÀ mappé sur root dans le
# conteneur : y ajouter --user le priverait de droits sur le volume monté.
# En mode classique, --user est au contraire indispensable pour ne pas laisser
# de fichiers root dans le dépôt. La distinction est mesurée, pas supposée.
ROOTLESS := $(shell $(DOCKER) info -f '{{.SecurityOptions}}' 2>/dev/null | grep -c rootless)
ifeq ($(ROOTLESS),0)
USER_FLAG := --user $(UIDGID)
else
USER_FLAG :=
endif

# Les caches des outils vont dans /tmp du conteneur : le dépôt monté ne reçoit
# jamais de répertoire de cache.
CACHES := -e RUFF_CACHE_DIR=/tmp/.ruff_cache -e MYPY_CACHE_DIR=/tmp/.mypy_cache \
          -e PYTEST_ADDOPTS=-p\ no:cacheprovider

# Cibles [LIVE] : dans le conteneur les variables sont déjà présentes (passées par
# --env-file) ; depuis l'hôte, Docker les injecte. Aucun analyseur de .env n'existe.
ifdef AVO_IN_CONTAINER
RUN :=
RUN_LIVE :=
else
RUN_LIVE := $(DOCKER) run --rm --env-file .env -v "$(CURDIR)":/app -w /app $(USER_FLAG) \
            -e HOME=/tmp $(CACHES) $(IMAGE)
RUN := $(DOCKER) run --rm -v "$(CURDIR)":/app -w /app $(USER_FLAG) \
       -e PYTHONPATH=/app/src:/app/mocks -e HOME=/tmp $(CACHES) $(IMAGE)
endif

.DEFAULT_GOAL := aide
.PHONY: aide image install lint typecheck test-unit test-int test-e2e check build up down ps logs smoke-pile seed seed-e2e smoke-live run-arc resume record-llm test-int-live _exige-env _hote-seulement docker-check

aide:
	@echo "Cibles du dépôt (contrat : docs/SPEC_HARNAIS.md §H2.3) — tout tourne dans Docker"
	@echo "  make image       construit l'image de développement '$(IMAGE)'"
	@echo "  make install     alias de 'make image' (rien n'est installé sur l'hôte)"
	@echo "  make lint        ruff, dans le conteneur"
	@echo "  make typecheck   mypy, dans le conteneur"
	@echo "  make test-unit   tests unitaires"
	@echo "  make test-int    tests d'intégration"
	@echo "  make test-e2e    tests de bout en bout"
	@echo "  make check       CAMPAGNE COMPLÈTE (hors ligne, sans secret)"
	@echo "  make build       image de production '$(IMAGE_PROD)'"
	@echo "  make up / down   pile locale de rejeu : llm-replay et arc-replay (hôte)"
	@echo "  make ps / logs   état et journaux de la pile (hôte)"
	@echo "  make smoke-pile  fumée de la pile par le port composé (hôte)"
	@echo "  make seed        contrôle des fixtures (n'en fabrique aucune)"
	@echo "  make seed-e2e    régénère les cassettes de scénario E2E (déterministe)"
	@echo "  make smoke-live     [LIVE] fumée contre le VRAI endpoint"
	@echo "  make record-llm     [LIVE] enregistre les cassettes sur le VRAI endpoint"
	@echo "  make test-int-live  [LIVE] détecte la dérive du contrat réel"
	@echo "  make run-arc     campagne ARC-AGI-3 (replay par défaut, live sous garde)"
	@echo "  make resume RUN_ID=<id>  reprend un run sans rejouer les jeux terminés"
	@echo "  make rapport-ab  A/B des deux modes de contexte, sur rejeu (U27)"
	@echo ""
	@echo "  AVO_NO_DOCKER=1 make test-unit   mode dégradé sur l'hôte (stdlib seule)"
	@echo ""
	@echo "  Sans 'make' sur l'hôte, la campagne complète s'exécute ainsi :"
	@echo "    docker build -t $(IMAGE) ."
	@echo "    docker run --rm -v \"\$$PWD\":/app -w /app -e HOME=/tmp \\"
	@echo "      -e RUFF_CACHE_DIR=/tmp/.ruff_cache -e MYPY_CACHE_DIR=/tmp/.mypy_cache \\"
	@echo "      $(IMAGE) make check      # ajouter --user \$$(id -u):\$$(id -g) hors rootless"

# Garde : dit précisément ce qui manque, plutôt que de laisser échouer docker.
docker-check:
ifndef AVO_IN_CONTAINER
	@if [ -z "$(DOCKER)" ]; then \
	  echo "ERREUR : docker introuvable dans le PATH." >&2; exit 2; \
	fi
	@if ! $(DOCKER) info >/dev/null 2>&1; then \
	  echo "ERREUR : le démon Docker est injoignable pour l'utilisateur courant." >&2; \
	  echo "  Cause habituelle : l'utilisateur n'appartient pas au groupe 'docker'." >&2; \
	  echo "  Correctif, UNE FOIS, par le responsable (droits administrateur) :" >&2; \
	  echo "      sudo usermod -aG docker \$$USER   puis rouvrir la session" >&2; \
	  echo "  Repli sans Docker et sans rien installer :" >&2; \
	  echo "      AVO_NO_DOCKER=1 make test-unit   (dégradé : stdlib seule)" >&2; \
	  exit 2; \
	fi
endif

image: docker-check
	$(DOCKER) build -t $(IMAGE) .

install: image

lint:
ifdef AVO_NO_DOCKER
	@echo "AVERTISSEMENT : mode dégradé — ruff indisponible hors conteneur."
	@echo "                Vérification RÉDUITE à la compilation. Ce n'est pas un lint."
	@PYTHONPATH=src $(PY) -m compileall -q src mocks tests
	@echo "compilation : OK (réduit)"
else
	@$(MAKE) --no-print-directory docker-check
	$(RUN) ruff check src mocks tests
	$(RUN) ruff format --check src mocks tests
endif

typecheck:
ifdef AVO_NO_DOCKER
	@echo "AVERTISSEMENT : mode dégradé — mypy indisponible hors conteneur."
	@echo "                Vérification de types NON EXÉCUTÉE, aucune garantie apportée."
else
	@$(MAKE) --no-print-directory docker-check
	$(RUN) mypy src mocks tests
endif

test-unit:
ifdef AVO_NO_DOCKER
	@echo "AVERTISSEMENT : mode dégradé — exécution sur l'hôte avec unittest (stdlib)."
	@PYTHONPATH=src:mocks $(PY) -m unittest discover -s tests/unit -t . -v
else
	@$(MAKE) --no-print-directory docker-check
	$(RUN) pytest tests/unit $(PYTEST_ARGS)
endif

test-int:
	@if [ -z "$$(find tests/integration -name 'test_*.py' -print -quit 2>/dev/null)" ]; then \
	  echo "aucun test d'intégration à ce stade — les premiers arrivent avec U4 (llm-replay)."; \
	elif [ -n "$(AVO_NO_DOCKER)" ]; then \
	  PYTHONPATH=src:mocks $(PY) -m unittest discover -s tests/integration -t . -v; \
	else \
	  $(MAKE) --no-print-directory docker-check && $(RUN) pytest tests/integration $(PYTEST_ARGS); \
	fi

test-e2e:
	@if [ -z "$$(find tests/e2e -name 'test_*.py' -print -quit 2>/dev/null)" ]; then \
	  echo "aucun test E2E à ce stade — le premier arrive avec U21 (partie complète sur rejeu)."; \
	elif [ -n "$(AVO_NO_DOCKER)" ]; then \
	  PYTHONPATH=src:mocks $(PY) -m unittest discover -s tests/e2e -t . -v; \
	else \
	  $(MAKE) --no-print-directory docker-check && $(RUN_PILE) pytest tests/e2e $(PYTEST_ARGS); \
	fi

# Campagne complète : tout ce qui EXISTE, hors ligne et sans secret.
# Le bilan nomme ce qui a été dégradé ou n'a pas encore d'objet, afin qu'un vert
# ne soit jamais lu comme une preuve non exécutée.
check: lint typecheck test-unit test-int test-e2e
	@echo ""
	@echo "───────── BILAN DE CAMPAGNE ─────────"
	@echo "exécutés : lint, typecheck, test-unit, test-int, test-e2e"
ifdef AVO_NO_DOCKER
	@echo "MODE     : DÉGRADÉ (hors Docker) — lint réduit, typecheck NON exécuté"
endif
	@echo "hors campagne ([LIVE], exigent .env) : record-llm, test-int-live, smoke-live"
	@echo "hors campagne (pilotent Docker, hôte) : build, up, down, smoke-pile"
	@echo "hors campagne (exigent la pile debout) : run-arc, resume"
	@echo "─────────────────────────────────────"

# Image de PRODUCTION : le paquet seul, sans outillage de test (§H2.4).
build: docker-check
	$(DOCKER) build --target runtime -t $(IMAGE_PROD) .

# Pile de services. Cibles d'HÔTE : elles pilotent Docker, qui n'est pas
# disponible depuis l'intérieur d'un conteneur.
up: _hote-seulement docker-check
	$(DOCKER) compose up -d --build
	@$(MAKE) --no-print-directory ps

down: _hote-seulement docker-check
	$(DOCKER) compose down

ps: _hote-seulement docker-check
	@$(DOCKER) compose ps --format 'table {{.Service}}\t{{.Status}}\t{{.Ports}}'

logs: _hote-seulement docker-check
	@$(DOCKER) compose logs --tail=50

# Fumée de la pile : le rejeu répond-il réellement par le port composé ?
smoke-pile: _hote-seulement docker-check
	@sh scripts/smoke_pile.sh

_hote-seulement:
ifdef AVO_IN_CONTAINER
	@echo "ERREUR : « make $(MAKECMDGOALS) » pilote Docker : à lancer depuis l'HÔTE," >&2
	@echo "  pas depuis le conteneur (docs/SPEC_HARNAIS.md §H2.4)." >&2
	@exit 2
endif

# Contrat de données de démonstration (CLAUDE.md §8, docs/SPEC_ARCAGI3.md §A3.4).
# La fixture llm n'est pas GÉNÉRÉE : elle est ENREGISTRÉE sur le vrai endpoint
# (make record-llm). Cette cible en contrôle donc la présence et l'intégrité, et
# dit précisément ce qui manque plutôt que de fabriquer un contrat.
seed:
	@echo "→ fixtures llm (cassettes enregistrées sur le vrai endpoint)"
	@if [ -s tests/fixtures/llm/cassettes/contrat_endpoint.jsonl ]; then \
	  echo "  contrat_endpoint.jsonl : $$(wc -l < tests/fixtures/llm/cassettes/contrat_endpoint.jsonl) échanges"; \
	else \
	  echo "  ABSENTE — lancez « make record-llm » ([LIVE], exige .env)"; \
	fi
	@echo "→ fixtures arc (jeu synthétique cible, épisodes)"
	@$(RUN) python -c "from arc_replay.jeu_cible import JeuCible, baseline_humaine; \
	  j=JeuCible(); print('  jeu cible :', j.niveaux, 'niveaux, baselines', j.baselines())"
	@if [ -n "$$(find tests/fixtures/arc/episodes -name '*.jsonl' -print -quit 2>/dev/null)" ]; then \
	  echo "  épisodes enregistrés : $$(ls tests/fixtures/arc/episodes/*.jsonl | wc -l)"; \
	else \
	  echo "  aucun épisode réel — le premier vient de la sonde U22 ([LIVE])"; \
	fi
	@echo "→ cassettes de scénario E2E (U21, générées : make seed-e2e)"
	@for f in e2e_victoire.jsonl e2e_echec.jsonl; do \
	  if [ -s tests/fixtures/llm/cassettes/$$f ]; then \
	    echo "  $$f : $$(wc -l < tests/fixtures/llm/cassettes/$$f) échanges"; \
	  else \
	    echo "  $$f ABSENTE — lancez « make seed-e2e » puis relancez la pile"; \
	  fi; \
	done
	@echo "→ cassette de scénario E2E, mode state (U27, générée : make seed-e2e)"
	@if [ -s tests/fixtures/llm/cassettes/e2e_etat_victoire.jsonl ]; then \
	  echo "  e2e_etat_victoire.jsonl : $$(wc -l < tests/fixtures/llm/cassettes/e2e_etat_victoire.jsonl) échanges"; \
	else \
	  echo "  e2e_etat_victoire.jsonl ABSENTE — lancez « make seed-e2e » puis relancez la pile"; \
	fi
	@echo "→ cassettes de scénario E2E, bancs (U29a2/U29a4/U29b2, générées : make seed-e2e)"
	@for f in e2e_banc_entrepot.jsonl e2e_banc_depot.jsonl e2e_banc_ctf.jsonl; do \
	  if [ -s tests/fixtures/llm/cassettes/$$f ]; then \
	    echo "  $$f : $$(wc -l < tests/fixtures/llm/cassettes/$$f) échanges"; \
	  else \
	    echo "  $$f ABSENTE — lancez « make seed-e2e » puis relancez la pile"; \
	  fi; \
	done

# Cassettes de scénario E2E (§A8.5) : génération DÉTERMINISTE par capture en deux
# passes, auto-vérifiée (double génération comparée). Le rejoueur charge ses
# cassettes au démarrage : après régénération, relancer la pile.
seed-e2e:
	@$(MAKE) --no-print-directory docker-check
	$(RUN) python -m tests.e2e.generer_cassettes
	$(RUN) python -m tests.e2e.generer_cassette_etat
	$(RUN) python -m tests.e2e.generer_cassette_banc
	@echo "cassettes E2E écrites — relancez la pile pour qu'elle les serve : make down && make up"

# Fumée manuelle contre le VRAI endpoint (§H4.8). Exige .env, jamais dans check.
smoke-live: _exige-env
	$(RUN_LIVE) python -m avo smoke-live

# Le contrat de l'endpoint n'est jamais inventé : il est enregistré sur le vrai
# serveur, puis rejoué. Ces deux cibles exigent .env et ne sont JAMAIS dans
# 'make check' (docs/SPEC_HARNAIS.md §H4.7).
# Le fichier .env n'est jamais lu par le code : Docker le passe en variables
# d'environnement au conteneur (--env-file), ce qui évite tout analyseur maison
# et toute trace de secret dans le dépôt.
record-llm: _exige-env
	$(RUN_LIVE) python -m llm_replay record

test-int-live: _exige-env
	$(RUN_LIVE) pytest tests/live $(PYTEST_ARGS)

_exige-env:
ifndef AVO_IN_CONTAINER
	@$(MAKE) --no-print-directory docker-check
	@if [ ! -r .env ]; then \
	  echo "ERREUR : .env absent — cette cible appelle le VRAI endpoint." >&2; \
	  echo "  Elle est [LIVE] et n'entre jamais dans 'make check'." >&2; \
	  exit 2; \
	fi
endif

# `run-arc` et `resume` parlent à la pile compose par ses ports publiés sur
# l'hôte : le conteneur doit donc partager le réseau de l'hôte, sinon 127.0.0.1
# désigne le conteneur lui-même et rien ne répond. ARGS passe les options.
RUN_PILE := $(DOCKER) run --rm --network host -v "$(CURDIR)":/app -w /app $(USER_FLAG) \
            -e PYTHONPATH=/app/src -e HOME=/tmp -e AVO_RUNS_DIR=/app/runs $(IMAGE)

run-arc:
	@$(MAKE) --no-print-directory docker-check
	$(RUN_PILE) python -m avo run-arc $(ARGS)

resume:
	@if [ -z "$(RUN_ID)" ]; then echo "usage : make resume RUN_ID=<identifiant>"; exit 2; fi
	@$(MAKE) --no-print-directory docker-check
	$(RUN_PILE) python -m avo resume $(RUN_ID) $(ARGS)

# A/B des deux modes de contexte, sur rejeu (U27) : rejoue deux mini-campagnes par
# la CLI réelle (une par AVO_CONTEXT_MODE) et écrit docs/rapports/ab_mode_contexte.md.
rapport-ab:
	@$(MAKE) --no-print-directory docker-check
	$(RUN_PILE) python scripts/generer_rapport_ab.py
