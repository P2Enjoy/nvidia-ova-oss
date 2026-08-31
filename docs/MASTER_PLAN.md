# MASTER PLAN — ordre d'exécution et Definition of Done commune

Ce document est lu par chaque session (interactive ou worker planifié) après le
journal et le backlog (`docs/CloudWorker.md` §4.1). Il fixe l'ordre d'exécution des
unités, la Definition of Done commune, et les adaptations de méthode propres à ce
dépôt (produit Python en ligne de commande, sans interface graphique).

## 1. Objet du produit

Implémentation open source du harnais AVO (spécifications : `docs/SPEC_HARNAIS.md`,
`docs/SPEC_ARCAGI3.md`) et son évaluation sur ARC-AGI-3, ensemble public. Les
spécifications de **toutes** les unités sont déjà écrites et committées : une session
qui prend une unité est dans le cas « spécification existante » de
`docs/CloudWorker.md` §3.2 — elle lit les chapitres cités par l'unité, vérifie
qu'ils couvrent ce qui reste à livrer, puis **code directement**. Réécrire une
spécification déjà écrite est une session en échec.

## 2. Ordre d'exécution

Les unités du backlog s'exécutent **dans l'ordre de leur numéro** (U3, U4, …, U30),
sauf reprise désignée par la dernière entrée du journal, et sauf U29, hors ordre tant
que son arbitrage n'est pas rendu (backlog, lot G). Chaque unité tient dans une
session et produit du code ; aucune unité documentaire ne reste ouverte.

| Lot | Unités | Contenu |
|---|---|---|
| A — Socle | U3–U5 | squelette Python, llm-replay, conteneurisation + seed |
| B — Client LLM | U6–U8 | config, client d'inférence, comptabilité/journalisation |
| C — Contexte | U9–U11 | transcript append-only, budget/continuation, notes |
| D — Boucle | U12–U15 | outils, boucle P→I→E→B, lignée+score, superviseur |
| E — ARC-AGI-3 | U16–U22 | rejeu local, client API, rendu, interface, RHAE, E2E, sonde |
| F — Campagne | U23–U25 | runner+rapport, campagne pilote, campagne étendue |
| G — État structuré (SKILL.state) | U26–U29 | spec H15 + runtime Σ, mode `state` + A/B rejeu, A/B réel, benchmarks complémentaires (arbitrage) |
| H — Méthode dans la structure | U30 | spec H16 + gardes de méthode dans les phases P→I→E→B |

## 3. Unités [LIVE] — règle pour le worker

Les unités marquées **[LIVE]** (U22, U24, U25, U28) exigent les secrets locaux
(`.env` : endpoint d'inférence et clé ARC) et, pour U24/U25/U28, engagent une
publication de scorecard au nom du responsable. **Une session qui ne détient pas les
secrets ne les prend jamais** : elles lui sont bloquées par un accès externe (cas 4 de
« Demande d'arbitrage », CLAUDE.md §1), elle les saute et prend l'unité suivante
non-[LIVE]. **La routine planifiée provisionnée par le responsable** (2026-08-30)
reçoit les secrets dans son environnement et porte son autorisation explicite de
jouer ARC Prize et de publier des scorecards : pour elle, les unités [LIVE] sont des
unités comme les autres — les plafonds de campagne (§A7.1) et la garde d'accord
(§A7.2, levée au titre de cette autorisation) restent obligatoires, et l'interdiction
de benchmaxing de `CLAUDE_PROJECT.md` s'applique sans exception. Quand il ne reste
aucune unité qu'une session puisse prendre, elle est dans le cas d'arrêt n° 2 de
`docs/CloudWorker.md` §4.5 et arrête la tâche planifiée en suivant la procédure.

## 4. Preuves du dépôt et campagne complète

Les classes de preuves de ce dépôt sont portées par le Makefile (contrat
`docs/SPEC_HARNAIS.md` §H2.3) et **s'exécutent toutes dans un conteneur** : rien n'est
installé sur la machine hôte. Une session qui ne peut pas joindre le démon Docker le
consigne (§2.5 du contrat worker), exécute ce qui reste vérifiable via
`AVO_NO_DOCKER=1` — mode dégradé, sans lint ni typecheck, qui l'annonce — et laisse
l'unité en `[~]` si ses preuves n'ont pas toutes tourné.

- pendant le travail (preuves de l'unité seule) : `make test-unit`,
  `make test-int` ciblés (`PYTEST_ARGS`), `make lint`, `make typecheck` ;
- **campagne complète de fin de session** : `make check` = lint + typecheck +
  test-unit + test-int + test-e2e, complété de `make build` exécuté depuis
  l'hôte (la cible check reste exécutable en conteneur, où docker n'existe
  pas — c'est pourquoi build n'y est pas inclus). C'est la « campagne » au sens
  de `docs/CloudWorker.md` §2.3/§4.3. Elle tourne intégralement hors ligne
  (rejeu, `mode=replay`), sans `.env` et sans réseau externe ; test-e2e exige la
  pile locale debout (§A8.5).

Ce dépôt n'a ni base de données applicative, ni messagerie, ni interface web : les
classes « tests de base de données », « E2E de messagerie », « E2E d'interface »
du contrat worker sont **sans objet** ici ; les sections Node/Playwright/port 4173 de
`docs/CloudWorker.md` ne s'appliquent qu'aux dépôts qui portent cet outillage, pas à
celui-ci. La pile compose du dépôt (`make up`) sert les services de rejeu `llm-replay` et
`arc-replay` ; le seed est `make seed`.

## 5. Vérification « dans la peau de l'utilisateur » (adaptation CLAUDE.md §16)

Le produit est une CLI. La vérification utilisateur consiste à exécuter réellement
les commandes documentées dans un terminal (`make up && make seed && make test-e2e`,
`python -m avo run-arc --mode replay …`), observer les sorties, et lire les artefacts
produits (`runs/<id>/report.md`, rendus de grilles, lignée). Aucune capture d'écran
n'est requise tant qu'aucune interface graphique n'existe ; les sorties de terminal
et artefacts committés en tiennent lieu de preuve. Si une UI apparaît un jour,
CLAUDE.md §16 s'applique en entier, captures comprises.

## 6. Definition of Done commune (complète CLAUDE.md §17)

Une unité passe à `[x]` seulement si :

1. le comportement spécifié par ses chapitres `@spec` est implémenté, avec les
   commentaires `@spec`/`@verifies` vers l'unité et les chapitres cités ;
2. ses tests propres (unitaires + intégration et/ou E2E selon l'unité) existent et
   passent ; `make check` entier est vert en fin de session ;
3. les cassettes, fixtures et seed reflètent tout nouveau comportement (CLAUDE.md §8) ;
4. `README.md`, `docs/DAT.md`, `CHANGELOG.md` ([Non publié]), le journal et le
   backlog sont à jour dans le même commit ; les documents rendus faux sont corrigés ;
5. commit(s) poussé(s) sur `origin/main`.

Interdits rappelés : aucun appel réseau externe depuis les tests (garde A2.3),
aucun secret committé ou journalisé, aucune unité [LIVE] prise sans `.env`, aucune
branche/worktree (CLAUDE.md §13), lignée git uniquement sous `runs/…` (H9.3).

## 7. Fin de la boucle planifiée

La tâche planifiée s'arrête (procédure `docs/CloudWorker.md` §4.5) quand U3–U21 et
U23 sont `[x]` et qu'il ne reste que des unités [LIVE], ou quand tout est `[x]`.
Les campagnes U24/U25 et la sonde U22 se font en session interactive avec le
responsable ; leur périmètre exact est consigné au journal avant lancement.
