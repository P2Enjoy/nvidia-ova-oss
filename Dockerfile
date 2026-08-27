# Image de développement et de preuves du harnais AVO.
#
# @spec docs/BACKLOG.md U3 — Squelette Python et outillage (chaîne conteneurisée)
# @spec docs/SPEC_HARNAIS.md §H2.1 (outillage), §H2.3 (commandes), §H2.4 (conteneurisation)
#
# Règle du responsable (2026-08-27) : TOUT s'exécute dans Docker ; rien n'est
# installé sur la machine hôte. L'outillage de développement (pytest, ruff,
# mypy) vit donc ICI, dans l'image, et nulle part ailleurs.
#
# Le harnais lui-même n'a AUCUNE dépendance d'exécution (§H2.1) : l'image de
# production n'installerait que le paquet. Cette image-ci ajoute uniquement de
# quoi PROUVER le code.

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src:/app/mocks \
    AVO_IN_CONTAINER=1

WORKDIR /app

# `make` est installé ICI et non sur l'hôte : la campagne complète s'exécute
# donc avec Docker pour seul prérequis (§H2.4). AVO_IN_CONTAINER=1 indique au
# Makefile qu'il est déjà dans le conteneur et ne doit pas en relancer un.
RUN apt-get update \
 && apt-get install -y --no-install-recommends make \
 && rm -rf /var/lib/apt/lists/*

# Outillage de preuve, épinglé par plancher de version (cf. pyproject [dev]).
RUN pip install --no-cache-dir "pytest>=8" "ruff>=0.6" "mypy>=1.11"

# Le code est monté en volume par le Makefile : l'image ne le copie pas, afin
# qu'une modification locale soit immédiatement prouvable sans reconstruction.
CMD ["python", "-m", "avo", "--version"]
