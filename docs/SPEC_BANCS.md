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

**S3.8 — Dérive d'état, condition 3** (source §5.4, Experiment 3 : l'état de
vérité est modifié HORS de la boucle d'action de l'agent et une alerte NON
STRUCTURÉE l'en informe ; la mesure est le retard de récupération, §S5.5).
Avec `derive` actif, l'épisode porte EXACTEMENT UNE dérive, figée à la
génération (§S1.4) sur un flux aléatoire seedé séparé (`derive-<seed>`), au
premier pas `d ≥ horizon // 2` où l'état nominal offre un candidat (une
étagère occupée ET une étagère vide) ; si aucun pas n'en offre, la génération
échoue par une erreur nommée — le point de mesure prend un autre seed.

Au pas `d` : (1) l'article d'une étagère occupée nominale, tirée au rng de
dérive, est déplacé vers la plus petite étagère nominale vide — « un opérateur
externe déplace un article », l'exemple même de la source ; (2) l'événement du
pas `d` est FORCÉ à `commande` de cet article, sans consommer le rng principal
à ce pas : seule l'alerte dit où l'article se trouve désormais — l'événement
teste la prise en compte de l'alerte ; (3) l'observation du pas `d` porte,
après la ligne d'événement et avant la télémétrie, l'alerte sous l'en-tête
`--- ALERTE EXTERNE ---` :
`[Audit externe] <article> déplacé de <source> vers <destination> par un opérateur externe.`.

Sur l'état RÉEL, la dérive s'applique au moment où l'événement `d` devient
observable : si l'article est réellement porté par une étagère et que la
destination nominale est réellement vide, il y est déplacé ; sinon (divergence
antérieure de l'agent) l'état réel est inchangé — l'alerte est émise telle
quelle et l'écart se paie comme toute divergence (§S3.4). La dérive n'est PAS
un événement actionnable : elle ne consomme rien et n'appelle aucune action
propre ; l'obligation du pas `d` reste celle de son événement (§S3.5), évaluée
sur l'état réel. À `derive` inactif, la génération est inchangée octet pour
octet — mêmes épisodes qu'avant la condition 3.

---

## S4. Environnement Dépôt logiciel

Détail exécutable écrit à l'ouverture de U29a3, avant son code, dans ce chapitre
seul. La source (annexe B.1) donne les invariants — état, espace d'actions,
familles d'observations, règles de transition, critère de succès — mais AUCUN
algorithme de génération pour cet environnement : le détail ci-dessous transpose
le patron de l'Entrepôt (§S3.3–§S3.5 ; état nominal, événements référençant les
entités nominales, une obligation par événement), qui est le patron mesuré de la
source (B.2). Chaque point que la source ne fixe pas est un POINT TRANCHÉ,
consigné ici avec l'issue écartée quand elle éclaire la décision.

**S4.1 — État de vérité** (source B.1). Le dépôt simulé porte :

- la branche `master` (dictionnaire fichier → contenu) et des branches de
  fonctionnalité `branche_N` — une par demande, créée par le PREMIER `commit` de
  l'agent sur son nom, supprimée par la fusion (B.1 : « merging a PR deletes the
  feature branch ») ;
- les PR ouvertes : numéro RÉEL croissant à partir de 1 dans l'ordre de création
  par l'agent, branche portée ;
- le statut CI de chaque branche : `rouge` si le défaut tiré de la demande
  (§S4.3) est présent et non corrigé, `verte` sinon ; indéfini avant tout commit ;
- les demandes annoncées (§S4.3) et, pour chaque fusion, le fait qu'elle a ou non
  cassé la CI.

L'état de vérité appartient à l'environnement, évolue exclusivement par les
actions VALIDES de l'agent, et n'est jamais montré à l'agent (§S3.1 s'applique).

**S4.2 — Actions** (B.1 fait foi ; NOTE : le corps de la source (§4.1) nomme un
espace différent — CherryPick/Merge/RunTests/CreateRelease/Rollback — l'annexe
B.1, plus précise et opérationnelle, fait foi ; écart consigné ici, pas ailleurs) :

| Action | Validité | Effet |
|---|---|---|
| `commit <branche> <fichier>` | la branche est celle d'une demande annoncée non encore fusionnée | crée la branche au besoin, écrit le fichier ; au PREMIER commit de la branche, le défaut tiré de la demande se matérialise (CI `rouge`) ou non (CI `verte`) |
| `create_pr <branche>` | la branche existe réellement ET aucune PR ouverte ne la porte | ouvre la PR de numéro réel suivant ; la CI de la PR est celle de la branche |
| `merge <pr>` | la PR est ouverte | les fichiers de la branche entrent dans `master`, la branche est supprimée, la PR fermée ; si la CI était `rouge`, la fusion CASSE la CI — l'issue le dit, la demande n'est pas correctement résolue (§S4.4) |
| `fix_ci <branche>` | la branche existe ET sa CI est `rouge` | le défaut est corrigé, la CI passe `verte` et le reste (le défaut est propre à la demande : corrigé, il ne revient pas) |
| `wait` | toujours | aucun |

Une action INVALIDE rend une erreur locale nommée et NE change PAS l'état
(§S3.2 s'applique) ; une action valide s'exécute toujours, même hors obligation.
POINT TRANCHÉ : `merge` sur CI rouge est VALIDE et casse la CI, plutôt que
refusé — c'est ce qui donne son sens au « sans casser la CI » du critère B.1 ;
l'issue nomme la casse, aucune perte silencieuse. `fix_ci` prend la branche
(signature B.1), même quand l'événement d'échec CI référence une PR.

POINT TRANCHÉ (2026-09-02, mesure : série live h25 bruit 5, seeds 1–2 — les
9 invalides des deux runs sont toutes des `merge` joués au bon événement sur la
bonne PR, refusés sur la seule notation du numéro) : le moteur lit le numéro de
PR de `merge` dans **la notation que l'environnement émet lui-même** — ses
événements et ses issues écrivent « PR #k ». Formes lues : l'entier nu (`3`),
`#3`, et le préfixe `PR` à casse indifférente, avec ou sans espace ni croisillon
(`PR #3`, `PR#3`, `PR 3`, `pr 3`). Un environnement qui refuse la notation qu'il
affiche enseigne une règle fausse (deux parcours identiques doivent se lire de la
même façon) ; l'issue écartée — garder la lecture stricte « 3 »/« #3 » — mesurait
la ponctuation du modèle, pas sa tenue d'état. Toute autre forme (`pr:3`,
`pr=3` hors normalisation §H15.8) reste une action invalide NOMMÉE qui consomme
l'événement (§S4.6). Les relevés antérieurs à cette lecture restent la trace de
l'ancienne référence et ne se comparent pas aux relevés postérieurs sur la
résolution.

**S4.3 — Cycle d'une demande et générateur.** Les demandes de fonctionnalité
sont l'unité de travail (B.1 : « feature requests »). La demande d'indice N
(croissant depuis 0) porte le fichier `fichier_N` et la branche `branche_N`. Son
cycle NOMINAL, dans l'ordre, chaque étape étant un événement actionnable :

1. `affectation` — `Issue affectée : demande_N — écrire fichier_N sur
   branche_N.` ; à son émission, le générateur tire au rng le défaut de la
   demande (équiprobable : la CI du premier commit sera `rouge` ou `verte`) ;
2. `revue` — `Revue approuvée pour branche_N : la PR peut être ouverte.` ;
3. si le défaut est tiré : `echec_ci` — `CI en échec pour PR #k (branche_N) :
   erreur de lint.` ;
4. `ci_verte` — `CI verte pour PR #k (branche_N) : prête à fusionner.`.

`#k` est le numéro de PR NOMINAL : croissant depuis 1 dans l'ordre nominal
d'ouverture (§S3.4 s'applique — les événements référencent les entités
nominales ; un agent qui a divergé rencontre des numéros qui ne correspondent
plus à son état réel, et l'écart se paie au score, jamais par un épisode
différent). Le générateur (`random.Random(seed)`, ordre d'appel fixe) maintient
l'état nominal en appliquant la réponse parfaite à chaque événement émis ; à
chaque pas, il choisit `rng.choice` parmi les candidats, liste construite dans
un ordre fixe : une `affectation` neuve (toujours faisable), puis le prochain
événement nominal de chaque demande en vie, dans l'ordre des indices. Le bruit
(§S3.6 s'applique : flux seedé séparé, en-tête `--- TELEMETRIE DE FOND ---`,
jamais d'effet sur l'état) tire ses lignes des distracteurs C.3 de la source :
télémétrie syslog de serveurs sans rapport (`[Syslog] Serveur-<n> — charge
CPU : <x> %, RAM : <y> %`).

**S4.4 — Score et résolution.** Le score CONTINU de §S5.1–§S5.2 s'applique
inchangé (source §4.3 : il couvre SkillExecBench entier, les deux
environnements). S'y ajoute le critère propre de B.1 : la RÉSOLUTION,
`resolution = demandes correctement résolues / demandes jugées`, où :

- une demande est CORRECTEMENT RÉSOLUE si, à la fin de l'épisode, son fichier
  figure dans `master` et sa fusion n'a pas cassé la CI ;
- les demandes JUGÉES sont celles dont l'événement `ci_verte` nominal est apparu
  dans l'épisode — celles dont l'horizon a réellement demandé la fusion ; une
  demande coupée en milieu de cycle par la fin d'épisode n'est pas jugée ;
- `resolution` vaut `null` quand aucune demande n'est jugée (jamais un faux 0).

Le relevé (§S5.3) d'un épisode Dépôt logiciel porte `resolution`,
`demandes_resolues` et `demandes_jugees` en plus des compteurs communs.

**S4.5 — Obligation d'un événement**, évaluée sur l'état de vérité RÉEL au
moment de l'action (§S3.5 s'applique, divergence comprise) :

- `affectation` de `demande_N` → `commit branche_N fichier_N` ;
- `revue` pour `branche_N` → `create_pr branche_N` si la branche réelle existe
  sans PR ouverte ; sinon (branche absente, ou PR déjà ouverte — divergence) →
  `wait` ;
- `echec_ci` pour la PR nominale `#k` (`branche_N`) → `fix_ci branche_N` si la
  branche réelle existe avec CI `rouge` ; sinon → `wait` ;
- `ci_verte` pour la PR nominale `#k` → `merge k` si la PR réelle `#k` est
  ouverte avec CI `verte` ; sinon (PR inexistante, fermée, ou CI `rouge` —
  divergence) → `wait` ;
- observation de bruit seul → `wait`.

**S4.6 — Fin d'épisode.** §S3.7 s'applique tel quel : chaque action — valide ou
non — consomme l'événement courant, et l'épisode se termine quand les `horizon`
événements actionnables sont consommés ; `etat_terminal()` rend « épisode
épuisé ».

**S4.7 — Dérive d'état du dépôt** (source §5.4 et table 10 : l'état du dépôt
est altéré via une alerte non structurée). §S3.8 s'applique — une seule dérive,
rng de dérive séparé, premier pas `d ≥ horizon // 2` offrant un candidat,
erreur nommée sinon, alerte sous `--- ALERTE EXTERNE ---`, génération
inchangée à `derive` inactif — avec la mutation propre au dépôt : le candidat
est une demande en vie dont la PR nominale est ouverte et prête à fusionner
(prochain événement nominal `ci_verte`), et sa CI est cassée par un commit
direct externe.

Au pas `d` : (1) la demande candidate, tirée au rng de dérive, voit sa CI
nominale repasser rouge — son prochain événement nominal redevient `echec_ci`,
puis le cycle reprend (§S4.3) ; (2) l'événement du pas `d` est FORCÉ au
`ci_verte` de sa PR — la notification périmée, partie avant la casse : seule
l'alerte dit la vérité, et l'obligation réelle du pas est `wait` (§S4.5, la CI
n'est plus verte) là où un agent à l'état périmé fusionne et casse master ;
(3) l'alerte du pas `d` :
`[Alerte] Commit direct sur <branche> : sa CI est repassée au rouge.`.

Sur l'état RÉEL : si la branche existe réellement et que sa CI est verte, elle
passe rouge au moment où l'événement `d` devient observable ; sinon
(divergence antérieure) l'état réel est inchangé.

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

Le relevé s'écrit MÊME quand l'épisode est interrompu par une erreur avant son
terme (panne de l'endpoint plus longue que les relances §H4.5, incident de
transport) : `arret` porte alors `incident : <classe>: <message>`, les compteurs
valent ce qui a réellement été consommé, et l'erreur remonte inchangée à
l'appelant — un relevé partiel n'est jamais un succès simulé, et un relevé dont
`evenements_consommes < horizon` n'entre dans aucune comparaison de scores.

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

**S5.5 — Mesure de récupération** (source §5.4 : « recovery steps »). Avec la
dérive active (§S3.8, §S4.7), le relevé porte en champs libres :
`derive_evenement` (l'indice `d`) ; `pas_de_recuperation` — le nombre
d'événements consommés depuis `d` avant la PREMIÈRE action correcte : 0 quand
l'action du pas `d` lui-même est correcte, `null` quand aucune action correcte
ne suit la dérive ; `recupere` — vrai dès qu'une action correcte suit la
dérive. Un épisode sans dérive ne porte aucun de ces champs. La comparaison
entre runs exige des épisodes complets (§S5.3) aux mêmes paramètres, dérive
comprise.

---

## S6. Adaptateur harnais et CLI

**S6.1 — Environnement de boucle.** `adaptateur.py` implémente le contrat §H8.2 :
`observation()` rend l'observation courante (événement + bruit),
`actions_disponibles()` la liste des commandes, `derniere_issue()` l'issue de la
dernière action, `etat_terminal()` le motif de fin (§S3.7). L'issue exposée à la
boucle porte `refusee = not valide` (§S3.2, §S4.2 : une action invalide ne change
rien à l'environnement) — c'est le drapeau du contrat §H15.8, qui protège Σ du
patch d'une action refusée. Les outils portent
l'étiquette `action`, le paramètre `prediction` (§H16.2) et des descriptions qui
énoncent la COMMANDE et sa SYNTAXE — le protocole étant donné (§S1.3), la
description peut nommer l'effet, contrairement à ARC.

**S6.2 — Contexte de tâche.** L'adaptateur fournit à K (§H16.1) le protocole du
banc : espace d'actions, règles de validité, obligations de §S3.5. Il ne fournit
ni l'état de vérité, ni la suite d'événements, ni aucune solution. Il nomme le
canal d'alerte (§S3.8) : les lignes sous `--- ALERTE EXTERNE ---` rapportent des
changements RÉELS effectués hors du contrôle de l'agent — sans dire quand ni
quoi, l'alerte reste non structurée et son contenu n'est jamais annoncé.

**S6.3 — CLI.** Sous-commande `banc` :
`python -m avo banc skillexec --env entrepot --horizon 50 --seed 42 [--bruit N] [--derive]`.
Elle monte la boucle complète (client LLM selon le mode, workspace, gardes) et
écrit le relevé §S5.3. En mode rejeu, elle pointe la pile locale comme le reste
du produit.

**S6.4 — Preuves du banc a** (Definition of Done des unités) :

- unitaires : générateur (déterminisme à seed égal, faisabilité des événements,
  divergence §S3.4), transitions (chaque action valide/invalide de §S3.2),
  score (§S5.2, cas nominal, action valide-mais-autre, invalide, `wait` dû et
  indu), bruit (n'altère pas l'état, en-tête, comptage), dérive (§S3.8/§S4.7 :
  unicité et pas forcé, alerte à l'observation, erreur nommée sans candidat,
  génération inchangée à `derive` inactif, application réelle et cas de
  divergence, obligation du pas `d`, mesure §S5.5) ;
- intégration : partie jouée en rejeu par la boucle complète sous gardes sur un
  épisode court, relevé `banc.json` écrit et exact ;
- E2E : scénario rejoué par cassette (épisode court, score attendu exact) ;
- balayage « zéro indice de jeu » (§A5) inchangé sur le noyau : les mots du banc
  ne doivent apparaître que sous `src/avo/bancs/`.

**S6.5 — Schéma de Σ des deux domaines** (§H15.9 : déclaré par le domaine,
validé par le noyau ; papier §3.1 et B.3). L'adaptateur déclare, une fois par
environnement, la forme dans laquelle l'agent tient son état — une documentation
d'API au même titre que le contexte de tâche (§S1.3, §S6.2), jamais une règle ni
une solution :

| Domaine | Champ | Genre | Rôle cité au protocole |
|---|---|---|---|
| Entrepôt | `hypotheses` | liste de chaînes | ce que tu tiens pour vrai |
| Entrepôt | `inventaire` | dictionnaire | étagère → article qu'elle porte |
| Entrepôt | `en_attente` | liste de chaînes | articles livrés non encore rangés |
| Dépôt | `hypotheses` | liste de chaînes | ce que tu tiens pour vrai |
| Dépôt | `branches` | dictionnaire | branche → ce que tu en sais (fichiers, CI, PR) |
| Dépôt | `prs` | dictionnaire | numéro de PR → branche, tant qu'elle est ouverte |

Le relevé §S5.3 porte `schema_etat` (le nom du schéma) : deux relevés ne se
comparent qu'à schéma égal. Les schémas nomment des CONTENANTS, pas des
contenus : rien n'y dit quelle action jouer ni quand.

## S7. Découpage en unités d'une session

- **U29a1** — la présente spécification, puis `entrepot.py` + `generation.py` +
  `score.py` : environnement Entrepôt complet, générateur, score, preuves
  unitaires. Sans adaptateur ni CLI.
- **U29a2** — `adaptateur.py` + CLI `banc` : boucle complète en rejeu, cassette,
  intégration + E2E, premier relevé de score live (3 seeds, horizon 10 et 25) au
  journal.
- **U29a3** — `depot.py` : environnement Dépôt logiciel (détail exécutable de §S4
  écrit d'abord), preuves unitaires, score §S4.4.
- **U29a4** — branchement du Dépôt logiciel à l'adaptateur et à la CLI (§S6 :
  outils, contexte de tâche, dispatch — POINT TRANCHÉ à la clôture de U29a3 : le
  branchement appartient à l'unité de campagne, qui en est le premier
  consommateur ; U29a3 reste l'environnement et ses preuves propres), puis
  conditions de bruit et de récupération d'état en campagne de banc, relevés
  multi-seeds consignés, alimentation du déclencheur U25.
