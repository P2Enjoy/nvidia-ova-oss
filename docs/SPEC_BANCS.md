# Spécification des bancs d'affinage du harnais

Référence stable pour les commentaires `@spec` : `docs/SPEC_BANCS.md §Sn`.
Unités de backlog couvertes : U29 et ses sous-unités (voir `docs/BACKLOG.md`).
Sources faisant foi : export SKILL.state
(`knowledge/arxiv-2608.26263-skill-state-long-horizon-agent-skills.md`) — §4.1
(définition des environnements), §4.3 (métriques), annexe B (implémentation),
annexe C (bruit), annexe D (résultats open-weight) ; `docs/SPEC_HARNAIS.md` §H8.2
(contrat `Environnement`), §H7 (outils), §H16 (gardes).

Objet : les bancs sur lesquels le harnais s'AFFINE avant la campagne ARC
(décision du responsable, 2026-09-01, journal suite 11). Trois bancs, dans l'ordre :
a) patron SkillExecBench (§S2–§S5), b) InterCode CTF (spécifié à l'ouverture de
son unité), c) τ-Bench (idem). Ce document porte le banc a en entier.

---

## S1. Cadre commun des bancs

**S1.1 — Rôle.** Un banc est un TERRAIN DE MESURE du harnais, pas un produit : il
fournit un environnement de tâche, un générateur d'épisodes et un score, afin que
chaque amélioration générique du harnais (U31) soit mesurée avant/après sur un
terrain déterministe et rejouable. Le banc a est le mètre hors ligne des
améliorations U31 (contrat U29).

**S1.2 — Le noyau reste agnostique.** Aucun banc n'ajoute une ligne au noyau §H.
Chaque banc est un ADAPTATEUR MINCE, comme `avo.arc` pour ARC : il implémente le
contrat `Environnement` de §H8.2, déclare ses outils dans un `RegistreOutils`
(§H7.1, étiquette `action` sur les outils qui consomment un événement) et fournit
son contexte de tâche. La boucle P→I→E→B, les gardes H16, les modes de contexte
H5/H15 et le superviseur s'appliquent SANS modification.

**S1.3 — Règles données, but donné : différence assumée avec ARC.** Contrairement
à §A5.1 (aucune règle de jeu), le patron SkillExecBench DONNE à l'agent le
protocole de la tâche : espace d'actions, règles de transition, obligations. C'est
la définition même du banc (annexe A de la source : `skill.instructions` injecte
persona, espace d'actions et règles). Ce protocole est le « contexte de tâche
fourni » de la garde documentaire §H16.1 — il entre dans K, jamais dans le code du
noyau. L'interdiction de benchmaxing est inchangée et porte sur le HARNAIS :
aucune règle, aucun indice, aucune constante propre à un banc ou à un épisode dans
le noyau §H ni dans ses prompts ; le protocole du banc vit dans l'adaptateur, qui
le donne à l'agent comme n'importe quel responsable donnerait une documentation
d'API.

**S1.4 — Déterminisme.** Tout épisode est engendré par un générateur pseudo-
aléatoire seedé (annexe B.2 de la source). À seed et paramètres identiques, la
suite d'événements est identique octet pour octet, quel que soit le comportement
de l'agent (§S3.4 règle la résolution des références). Les preuves rejouent par
cassettes (garde A2.3 : aucun appel réseau externe depuis les tests) ; la mesure
de score réelle passe par le gateway LLM du responsable, pile locale sans réseau
pour l'environnement lui-même.

**S1.5 — Arborescence.** `src/avo/bancs/` (paquet des bancs),
`src/avo/bancs/skillexec/` pour le banc a :

```
src/avo/bancs/__init__.py
src/avo/bancs/skillexec/__init__.py
src/avo/bancs/skillexec/entrepot.py      # §S3 : environnement Warehouse
src/avo/bancs/skillexec/generation.py    # §S3.3 : générateur d'épisodes seedé
src/avo/bancs/skillexec/score.py         # §S5 : score continu et relevé
src/avo/bancs/skillexec/depot.py         # §S4 : environnement Software Repository
src/avo/bancs/skillexec/adaptateur.py    # §S6 : outils + contexte de tâche + CLI
```

Les tests suivent le miroir habituel (`tests/unit/bancs/…`, `tests/integration/…`).

---

## S2. Banc a — patron SkillExecBench : objet et périmètre

**S2.1 — Objet** (source §4.1). Isoler la MÉCANIQUE D'EXÉCUTION de la recherche
heuristique ouverte : tâches procédurales séquentielles à transitions
déterministes, où la difficulté est de maintenir un état exact sur un horizon
long, sous bruit, et de s'en remettre après altération. Deux environnements :

- **Entrepôt (Warehouse Management)** — §S3 : 500 étagères indépendantes, état
  plat, variables non chevauchantes ; teste la tenue d'un état large et simple.
- **Dépôt logiciel (Software Repository)** — §S4 : graphe branches/commits/PR/CI
  aux dépendances denses ; teste le raisonnement structurel sur un état intriqué.

**S2.2 — Paramètres d'un épisode.** `seed` (entier), `horizon` (nombre
d'événements actionnables), `bruit` (événements de télémétrie par observation,
§S3.5 ; défaut 0). Horizons de référence de la source : 10, 25, 50, 100, 200.

**S2.3 — Ce que le banc ne fait pas.** Pas de récompense apprise, pas de
variation d'épisode adaptée au modèle, pas d'accès de l'agent à l'état de vérité
(il ne voit que les observations textuelles et les issues de ses actions).

---

## S3. Environnement Entrepôt

**S3.1 — État de vérité.** 500 étagères `etagere_0` … `etagere_499` ; chacune
porte au plus un identifiant d'article (`article_N`) ou est vide. L'état de
vérité appartient à l'environnement, évolue exclusivement par les actions VALIDES
de l'agent, et n'est jamais montré à l'agent.

**S3.2 — Espace d'actions** (source B.1) :

| Action | Validité | Effet |
|---|---|---|
| `store <article> <etagere>` | l'article est en attente de rangement ET l'étagère est vide | l'article est posé sur l'étagère |
| `ship <article> <etagere>` | l'étagère porte exactement cet article | l'article est détruit, l'étagère se vide |
| `move <article> <src> <dst>` | `src` porte l'article ET `dst` est vide | l'article change d'étagère |
| `wait` | toujours | aucun |

Une action INVALIDE rend une erreur locale nommée et NE change PAS l'état
(source B.1). Une action valide s'exécute toujours, même si elle n'est pas celle
que l'événement attend (elle compte alors 0 au score, §S5.2).

**S3.3 — Générateur d'épisodes** (source B.2, algorithme 2). Générateur seedé
(`random.Random(seed)`). À chaque pas, le type d'événement est tiré parmi les
types FAISABLES sur l'état nominal (l'état de vérité qu'aurait produit un agent
parfait) :

- `reception` (toujours faisable tant qu'une étagère nominale est vide) : un
  article neuf, identifiant croissant (`article_0`, `article_1`, …), arrive.
  Observation : `Livraison reçue : <article>.` ;
- `commande` (faisable si l'état nominal porte au moins un article) : un article
  présent est tiré. Observation : `Commande client : <article>.` ;
- `maintenance` (faisable si l'état nominal porte au moins une étagère occupée) :
  une étagère occupée est tirée. Observation :
  `Maintenance requise sur <etagere>.`.

**S3.4 — Résolution nominale et divergence de l'agent.** POINT TRANCHÉ (la
source engendre les événements sur l'état de vérité en supposant le geste correct
à chaque pas ; elle ne dit pas ce que référencent les événements quand l'agent a
divergé). Décision : le générateur maintient l'ÉTAT NOMINAL (jeu parfait, `store`
nominal sur la plus petite étagère vide, résolutions tirées au rng seedé) et les
événements référencent articles et étagères NOMINAUX — la suite d'événements est
ainsi identique pour tous les runtimes comparés, exigence de comparaison équitable
de la source (B.2), et un agent qui a divergé rencontre des événements qui ne
correspondent plus à son état réel : l'écart se paie au score, jamais par un
épisode différent. Issue écartée : engendrer sur l'état réel de l'agent — les
épisodes cesseraient d'être comparables entre runs et entre runtimes.

**S3.5 — Obligation d'un événement.** Chaque événement appelle EXACTEMENT UNE
action correcte, évaluée sur l'état de vérité RÉEL au moment de l'action :

- `reception` de `article_X` → `store article_X <étagère vide>` (toute étagère
  réellement vide est correcte : la source valide « the shelf is empty », elle
  n'impose pas l'étagère) ;
- `commande` de `article_X` → `ship article_X <étagère qui le porte réellement>` ;
- `maintenance` sur `etagere_Y` → `move <article porté par Y> etagere_Y
  <étagère vide>` ; si l'étagère réelle Y est vide (divergence), l'action
  correcte est `wait` — rien à déplacer ;
- observation de bruit seul (§S3.6) → `wait`.

**S3.6 — Bruit, condition 1** (source annexe C). Avec `bruit=N`, chaque
observation reçoit N lignes de télémétrie strictement hors sujet, tirées d'un
flux aléatoire seedé SÉPARÉ de celui des événements — le niveau de bruit ne
change jamais la suite d'événements : même tâche, distracteurs ajoutés (batterie,
température, charge CPU, capteurs, OCR caméra — gabarits de C.2), sous l'en-tête
`--- TELEMETRIE DE FOND ---`. Le bruit n'altère jamais l'état et n'appelle
jamais d'action. Niveaux de référence : 0, 5, 20, 50.

**S3.7 — Fin d'épisode.** L'épisode se termine quand les `horizon` événements
actionnables sont consommés (chacun par exactement une action de l'agent,
correcte ou non — une action invalide rend son erreur et CONSOMME l'événement,
sans quoi un agent bloqué boucle sans fin ; POINT TRANCHÉ, la source compte les
actions invalides comme échouées sans détailler la suite). `etat_terminal()`
rend alors le motif « épisode épuisé » (§H8.3).

---

## S4. Environnement Dépôt logiciel

Spécifié ici dans ses invariants ; son unité (U29a3) précise le détail exécutable
avant son code, dans ce chapitre, sans toucher aux chapitres voisins.

**S4.1 — État de vérité** (source B.1) : branches (histoires de commits),
contenus de fichiers, PR ouvertes, statuts CI. **S4.2 — Actions** :
`commit <branche> <fichier>`, `create_pr <branche>`, `merge <pr>`,
`fix_ci <branche>`, `wait`. NOTE : le corps de la source (§4.1) nomme un espace
différent (CherryPick/Merge/RunTests/CreateRelease/Rollback) ; l'annexe B.1, plus
précise et opérationnelle, fait foi — écart consigné ici, pas ailleurs.
**S4.3 — Observations** : notifications CI, revues, affectations d'issues.
**S4.4 — Score** : pourcentage de demandes de fonctionnalité correctement
résolues — fusionnées dans `master` sans casser la CI.

---

## S5. Score et relevé

**S5.1 — Score continu** (source §4.3) :
`score = actions correctes / événements actionnables`, dans [0, 1].

**S5.2 — Action correcte.** La PREMIÈRE action jouée en réponse à l'événement,
et elle seule, est comparée à l'obligation de §S3.5 : conforme → 1, sinon
(invalide OU valide-mais-autre) → 0. `wait` face à un événement actionnable
compte 0.

**S5.3 — Relevé.** L'environnement tient, par épisode : score, actions
correctes/incorrectes/invalides, tokens consommés (relevé du client §H4),
taille moyenne de prompt, durée. Le relevé s'écrit en JSON dans le workspace du
run (`banc.json`), à côté des artefacts H16 ; c'est lui qui alimente le journal
et le déclencheur U25.

**S5.4 — Scores de référence consignés** (source annexe D, modèles open-weight
de taille comparable à `qwen3.6:35b`, Entrepôt, bruit 0, runtime SKILL.state —
notre mode `state` en est l'homologue) :

| Horizon | Qwen-3-8B-it (table 8) | Gemma-4-31B-it (table 7) |
|---|---|---|
| 10 | 0,94 ± 2,1 % | 0,98 ± 1,5 % |
| 25 | 0,76 ± 4,2 % | 0,84 ± 3,6 % |
| 50 | 0,58 ± 4,5 % | 0,68 ± 3,9 % |
| 100 | 0,34 ± 4,6 % | 0,42 ± 4,1 % |

`qwen3.6:35b` (35 G paramètres) se situe entre ces deux gabarits : la fourchette
[Qwen-3-8B, Gemma-4-31B] est la référence « scores comparables aux modèles de
taille similaire » du déclencheur U25 pour ce banc. La source mesure sur
5 seeds ; la nôtre relève au minimum 3 seeds par point avant toute comparaison.

---

## S6. Adaptateur harnais et CLI

**S6.1 — Environnement de boucle.** `adaptateur.py` implémente le contrat §H8.2 :
`observation()` rend l'observation courante (événement + bruit),
`actions_disponibles()` la liste des commandes, `derniere_issue()` l'issue de la
dernière action, `etat_terminal()` le motif de fin (§S3.7). Les outils portent
l'étiquette `action`, le paramètre `prediction` (§H16.2) et des descriptions qui
énoncent la COMMANDE et sa SYNTAXE — le protocole étant donné (§S1.3), la
description peut nommer l'effet, contrairement à ARC.

**S6.2 — Contexte de tâche.** L'adaptateur fournit à K (§H16.1) le protocole du
banc : espace d'actions, règles de validité, obligations de §S3.5. Il ne fournit
ni l'état de vérité, ni la suite d'événements, ni aucune solution.

**S6.3 — CLI.** Sous-commande `banc` :
`python -m avo banc skillexec --env entrepot --horizon 50 --seed 42 [--bruit N]`.
Elle monte la boucle complète (client LLM selon le mode, workspace, gardes) et
écrit le relevé §S5.3. En mode rejeu, elle pointe la pile locale comme le reste
du produit.

**S6.4 — Preuves du banc a** (Definition of Done des unités) :

- unitaires : générateur (déterminisme à seed égal, faisabilité des événements,
  divergence §S3.4), transitions (chaque action valide/invalide de §S3.2),
  score (§S5.2, cas nominal, action valide-mais-autre, invalide, `wait` dû et
  indu), bruit (n'altère pas l'état, en-tête, comptage) ;
- intégration : partie jouée en rejeu par la boucle complète sous gardes sur un
  épisode court, relevé `banc.json` écrit et exact ;
- E2E : scénario rejoué par cassette (épisode court, score attendu exact) ;
- balayage « zéro indice de jeu » (§A5) inchangé sur le noyau : les mots du banc
  ne doivent apparaître que sous `src/avo/bancs/`.

## S7. Découpage en unités d'une session

- **U29a1** — la présente spécification, puis `entrepot.py` + `generation.py` +
  `score.py` : environnement Entrepôt complet, générateur, score, preuves
  unitaires. Sans adaptateur ni CLI.
- **U29a2** — `adaptateur.py` + CLI `banc` : boucle complète en rejeu, cassette,
  intégration + E2E, premier relevé de score live (3 seeds, horizon 10 et 25) au
  journal.
- **U29a3** — `depot.py` : environnement Dépôt logiciel (détail exécutable de §S4
  écrit d'abord), preuves unitaires, score §S4.4.
- **U29a4** — conditions de bruit et de récupération d'état en campagne de banc,
  relevés multi-seeds consignés, alimentation du déclencheur U25.
