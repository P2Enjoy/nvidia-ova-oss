# Images du harnais AVO — deux étages, deux objets distincts.
#
# @spec docs/BACKLOG.md U3 (image de développement) · U5 (image de production)
# @spec docs/SPEC_HARNAIS.md §H2.1 (zéro dépendance d'exécution), §H2.4 (conteneurisation)
#
# Règle du responsable (2026-08-27) : TOUT s'exécute dans Docker ; rien n'est
# installé sur la machine hôte.
#
#   --target runtime  → image de production : le paquet seul, aucune dépendance,
#                       aucun outillage de test. C'est ce qui serait déployé.
#   --target dev      → y ajoute make, pytest, ruff et mypy. C'est le seul endroit
#                       où l'outillage vit. Étage par défaut.

# ---------------------------------------------------------------- runtime ----
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# `git` est la SEULE dépendance système du harnais : la lignée de solutions est un
# dépôt git jetable créé par chaque run (§H9.3). Ce n'est pas une dépendance Python,
# le principe « zéro dépendance d'exécution » (§H2.1) reste tenu.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ ./src/

CMD ["python", "-m", "avo"]

# -------------------------------------------------------------------- dev ----
FROM runtime AS dev

# AVO_IN_CONTAINER indique au Makefile qu'il est déjà dans le conteneur et ne doit
# pas en relancer un ; `make` est installé ICI et non sur l'hôte, de sorte que la
# campagne complète s'exécute avec Docker pour seul prérequis (§H2.4).
ENV AVO_IN_CONTAINER=1 \
    PYTHONPATH=/app/src:/app/mocks

RUN apt-get update \
 && apt-get install -y --no-install-recommends make \
 && rm -rf /var/lib/apt/lists/*

# Autorités de certification supplémentaires (§H2.4) : tout `*.crt` déposé dans
# certs/ (vide par défaut, cf. certs/README.md) entre au magasin système, et pip
# lit ce magasin — nécessaire derrière un proxy TLS interceptant, sans effet
# sinon (le magasin système reste le jeu d'autorités standard).
COPY certs/ /usr/local/share/ca-certificates/extra/
RUN update-ca-certificates
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt

# Outillage de preuve, épinglé par plancher de version (cf. pyproject [dev]).
RUN pip install --no-cache-dir "pytest>=8" "ruff>=0.6" "mypy>=1.11"

# En développement le code est monté en volume par le Makefile et la pile compose :
# une modification locale est prouvable sans reconstruction.
CMD ["python", "-m", "avo", "--version"]
