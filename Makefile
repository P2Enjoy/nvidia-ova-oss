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
PY ?= python3
PYTEST_ARGS ?=

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

ifdef AVO_IN_CONTAINER
RUN :=
else
RUN := $(DOCKER) run --rm -v "$(CURDIR)":/app -w /app $(USER_FLAG) \
       -e PYTHONPATH=/app/src -e HOME=/tmp $(CACHES) $(IMAGE)
endif

.DEFAULT_GOAL := aide
.PHONY: aide image install lint typecheck test-unit test-int test-e2e check build up down seed smoke-live run-arc record-llm test-int-live docker-check

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
	@echo "  make build       image de production               [à venir : U5]"
	@echo "  make up / down   pile locale (rejeu)               [à venir : U5]"
	@echo "  make seed        données de démonstration          [à venir : U4/U16]"
	@echo "  make smoke-live  fumée contre l'endpoint réel      [à venir : U8]"
	@echo "  make record-llm  enregistre les cassettes sur le VRAI endpoint [à venir : U4]"
	@echo "  make test-int-live  rejoue l'intégration contre le vrai serveur [à venir : U4]"
	@echo "  make run-arc     campagne ARC-AGI-3                [à venir : U23]"
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
	@PYTHONPATH=src $(PY) -m compileall -q src tests
	@echo "compilation : OK (réduit)"
else
	@$(MAKE) --no-print-directory docker-check
	$(RUN) ruff check src tests
	$(RUN) ruff format --check src tests
endif

typecheck:
ifdef AVO_NO_DOCKER
	@echo "AVERTISSEMENT : mode dégradé — mypy indisponible hors conteneur."
	@echo "                Vérification de types NON EXÉCUTÉE, aucune garantie apportée."
else
	@$(MAKE) --no-print-directory docker-check
	$(RUN) mypy src tests
endif

test-unit:
ifdef AVO_NO_DOCKER
	@echo "AVERTISSEMENT : mode dégradé — exécution sur l'hôte avec unittest (stdlib)."
	@PYTHONPATH=src $(PY) -m unittest discover -s tests/unit -t . -v
else
	@$(MAKE) --no-print-directory docker-check
	$(RUN) pytest tests/unit $(PYTEST_ARGS)
endif

test-int:
	@if [ -z "$$(find tests/integration -name 'test_*.py' -print -quit 2>/dev/null)" ]; then \
	  echo "aucun test d'intégration à ce stade — les premiers arrivent avec U4 (llm-replay)."; \
	elif [ -n "$(AVO_NO_DOCKER)" ]; then \
	  PYTHONPATH=src $(PY) -m unittest discover -s tests/integration -t . -v; \
	else \
	  $(MAKE) --no-print-directory docker-check && $(RUN) pytest tests/integration $(PYTEST_ARGS); \
	fi

test-e2e:
	@if [ -z "$$(find tests/e2e -name 'test_*.py' -print -quit 2>/dev/null)" ]; then \
	  echo "aucun test E2E à ce stade — le premier arrive avec U21 (partie complète sur rejeu)."; \
	elif [ -n "$(AVO_NO_DOCKER)" ]; then \
	  PYTHONPATH=src $(PY) -m unittest discover -s tests/e2e -t . -v; \
	else \
	  $(MAKE) --no-print-directory docker-check && $(RUN) pytest tests/e2e $(PYTEST_ARGS); \
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
	@echo "sans objet à ce stade : build (U5), up/down (U5), seed (U4/U16),"
	@echo "                        smoke-live (U8), run-arc (U23)"
	@echo "─────────────────────────────────────"

build:
	@echo "make build : l'image de production n'existe pas encore — à venir en U5" >&2
	@echo "  (l'image de développement, elle, se construit avec 'make image')" >&2
	@exit 2

up down:
	@echo "make $@ : la pile compose n'existe pas encore — à venir en U5" >&2
	@echo "  (docs/BACKLOG.md U5, docs/SPEC_HARNAIS.md §H2.4)" >&2
	@exit 2

seed:
	@echo "make seed : les fixtures n'existent pas encore — à venir en U4 (llm) et U16 (arc)" >&2
	@echo "  (docs/SPEC_ARCAGI3.md §A3.4)" >&2
	@exit 2

smoke-live:
	@echo "make smoke-live : à venir en U8 — exige .env, jamais dans 'make check'" >&2
	@echo "  (docs/SPEC_HARNAIS.md §H4.8)" >&2
	@exit 2

# Le contrat de l'endpoint n'est jamais inventé : il est enregistré sur le vrai
# serveur, puis rejoué. Ces deux cibles exigent .env et ne sont JAMAIS dans
# 'make check' (docs/SPEC_HARNAIS.md §H4.7).
record-llm:
	@echo "make record-llm : à venir en U4 — enregistre les cassettes sur le vrai endpoint" >&2
	@echo "  (exige .env ; docs/SPEC_HARNAIS.md §H4.7)" >&2
	@exit 2

test-int-live:
	@echo "make test-int-live : à venir en U4 — détection de dérive du contrat réel" >&2
	@echo "  (exige .env ; docs/SPEC_HARNAIS.md §H4.7)" >&2
	@exit 2

run-arc:
	@$(MAKE) --no-print-directory docker-check
	$(RUN) python -m avo run-arc
