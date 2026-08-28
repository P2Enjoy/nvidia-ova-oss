# Spécification de l'interface ARC-AGI-3 et de l'évaluation

Référence stable pour les commentaires `@spec` : `docs/SPEC_ARCAGI3.md §An`.
Unités de backlog couvertes : U16–U25 (voir `docs/BACKLOG.md`).
Sources faisant foi : export Tycho (formalisation §3, protocole, outils annexe A),
export VISTA (harnais, prompt, mémoire visuelle), billet NVIDIA (configuration AVO
texte-seul), listing officiel `/api/games` vérifié le 2026-08-27. La définition RHAE
de l'export Tycho §3.1 fait foi ; la méthodologie officielle
(docs.arcprize.org/methodology) prime en cas de divergence constatée.

---

## A1. Formalisation et protocole officiel

**A1.1 — Environnement** (Tycho §3.1) : machines de Moore rendues, déterministes.
Observation = grille 64×64, 16 couleurs (0–15). Un jeu = suite ordonnée de niveaux
partageant les mécaniques ; état caché possible (la grille courante n'est pas Markov).
Sorties d'un état : grille rendue, actions disponibles, issue
(`ongoing`/`level_complete`/`game_over`). Entre deux frames de décision, des frames
transitoires (animations) peuvent être émises : évidence, mais on n'agit pas dessus.

**A1.2 — Protocole de score** (Tycho déf. 2) : toute action ordinaire compte pour le
niveau courant ; `RESET` est toujours disponible, coûte 1 action en cours de partie
(le RESET initial qui crée la partie est gratuit) et relance la tentative au début du
niveau courant ; `level_complete` ferme le niveau et avance gratuitement ;
`game_over` ferme la tentative seulement. Le raisonnement interne et l'inspection en
lecture seule sont gratuits.

**A1.3 — API officielle.** Base `ARC_BASE_URL`, en-tête `X-API-Key` (vérifié le
2026-08-27 : 401 sans clé). Surfaces utilisées :
- `GET /api/games` → liste `{game_id, title, tags, baseline_actions[]}` (vérifié) ;
- ouverture/fermeture/lecture de scorecard, puis commandes de jeu `RESET` et
  `ACTION1`–`ACTION6` (`ACTION6` porte des coordonnées de clic), chaque commande
  renvoyant frame(s), état, score et actions disponibles — contrat d'après l'export
  Tycho (annexe A : `take_action(action, row?, col?)` contraint à RESET + contrôles
  déclarés par la frame courante).

**A1.4 — Format de fil retenu, et son statut.** Le format exact n'a **pas** été
sondé — jouer via l'API publie un scorecard (règle « évaluer, c'est publier »,
`CLAUDE_PROJECT.md`). Celui qui suit est écrit d'après l'export Tycho, implémenté des
deux côtés (client U17, rejeu U16), et **confirmé ou corrigé par l'unité U22** ; tout
écart constaté corrige le client ET le serveur de rejeu dans le même changement.

- `POST /api/scorecard/open` `{tags}` → `{card_id}` ; `POST /api/scorecard/close`
  `{card_id}` → résumé ; `GET /api/scorecard/<card_id>` → résumé.
- `POST /api/cmd/RESET` `{game_id?, card_id?, guid?}` : sans `guid`, crée la partie
  et rend le sien ; avec, relance la tentative courante.
- `POST /api/cmd/ACTION1`–`ACTION6` `{guid, card_id?}`, plus `{row, col}` pour
  `ACTION6`.
- Réponse commune : `{guid, game_id, frames, state, score, level, actions_level,
  available_actions}`, où `frames` est la liste des grilles 64×64 émises par la
  commande — transitoires d'abord, frame de décision en dernier — et `state` vaut
  `NOT_PLAYED`, `NOT_FINISHED`, `WIN` ou `GAME_OVER`.

**A1.5 — Étiquettes de modalité.** `/api/games` porte `tags` ∈ {`click`, `keyboard`,
`keyboard_click`, absent}. Elles n'ajoutent aucune règle : la vérité des actions
disponibles est ce que la frame déclare (Tycho, remarque 1). Les tags servent
uniquement au séquencement de campagne et aux rapports.

## A2. Client API ARC

**A2.1 —** `ArcClient` (stdlib, mêmes règles transport que H4.5/H4.6 : retries bornés
sur 5xx/réseau, jamais sur 4xx, aucun secret journalisé). Méthodes : `games()`,
`open_scorecard(tags)`, `scorecard(id)`, `close_scorecard(id)`, `reset(game, guid?)`,
`action(n, coords?, guid)`. Réponses normalisées en `FrameResult` typé : frames
(liste de grilles 64×64), état, score (niveaux), actions disponibles, guid,
compteur d'actions.

**A2.2 — Typage de l'historique** (Tycho déf. 3, simplifié) : chaque frame reçue est
étiquetée `decision` | `transient` | `terminal_win` | `terminal_gameover` |
`reset_init` | `level_init`, et chaque action enregistrée est rattachée à la frame de
décision d'où elle a été choisie. Persisté dans `runs/<id>/frames/` (JSONL par
niveau).

**A2.3 — Garde anti-publication.** En `mode=replay`, construire un `ArcClient` vers
un hôte ≠ hôte de rejeu local est une erreur fatale. Les tests ne peuvent pas
atteindre l'API officielle par construction.

## A3. Environnement local de rejeu (`arc-replay`)

**A3.1 — Rôle.** Serveur stdlib exposant le **même contrat HTTP** que l'API
officielle (A1.3/A2.1), pour : tests d'intégration et E2E déterministes, développement
sans réseau ni publication, rejeu d'épisodes réels enregistrés. Service compose avec
healthcheck ; peuplé par `make seed`.

**A3.2 — Jeu synthétique `cible` (spécification fermée).** Jeu déterministe servi par
`arc-replay`, permettant de vraies parties de bout en bout :
- niveau ℓ (1-indexé, L=3 par défaut) : fond 0, bordure couleur 5, cible 2×2 couleur 3
  au coin (row, col) = ((7·ℓ) mod 60 + 2, (13·ℓ) mod 60 + 2), curseur 1×1 couleur 8
  démarrant en (32, 32) ;
- actions disponibles : `ACTION1`–`ACTION4` = curseur haut/bas/gauche/droite (bloqué
  par la bordure), `ACTION6(row, col)` = clic ;
- clic avec curseur sur la cible → `level_complete` ; 3 clics hors cible dans la même
  tentative → `game_over` ; `RESET` conforme A1.2 ;
- baseline humaine synthétique du niveau : distance de Manhattan initiale
  curseur→cible + 1 (connue en forme fermée → RHAE attendu calculable exactement dans
  les tests) ;
- une frame transitoire (curseur en couleur 9 sur sa case d'arrivée) est émise avant
  chaque frame de décision, pour exercer le typage A2.2.

**A3.3 — Mode rejeu d'épisodes.** `arc-replay` sert aussi des épisodes enregistrés
(`tests/fixtures/arc/episodes/*.jsonl` : suites requête→réponse capturées en live,
expurgées de tout secret). La sonde U22 produit le premier épisode réel. Une requête
qui dévie de l'épisode → réponse d'erreur explicite (test rouge lisible).

**A3.4 — Seed.** `make seed` régénère les fixtures déterministes (scénarios llm-replay,
paramètres du jeu `cible`, épisodes) — c'est le contrat de données de démonstration du
dépôt (CLAUDE.md §8) : reproductible, couvrant succès, refus (401), erreurs (413,
game over) et branches (RESET, continuation).

## A4. Rendu texte et mémoire de frames

**A4.1 — Observation** (billet NVIDIA : texte seul, grille exacte). Rendu canonique
d'une grille : 64 lignes de 64 valeurs décimales séparées par des espaces, précédées
d'une ligne d'état (`niveau, score, actions_du_niveau, actions_disponibles`). Aucune
image, aucun autre enrichissement dans l'observation courante.

**A4.2 — Convention de coordonnées (décision).** Interne : (row, col), 0-basé,
origine en haut à gauche. La conversion vers le format de fil de l'API (x/y) est
confinée au client A2.1 et **confirmée en U22** ; l'agent ne voit que (row, col).

**A4.3 — Mémoire de frames sans perte** (VISTA). Toute frame reçue (décision et
transitoire) est stockée, indexée (tour, index de frame). Outils gratuits au score :
- `inspect(turn?, frame?, region?)` : réaffiche une frame passée ou une découpe, avec
  index de lignes/colonnes en marge ; plusieurs vues par appel autorisées ;
- `read_pixels(region)` : valeurs exactes d'une région de la frame courante ou d'une
  frame désignée ;
- `diff(turn_a, turn_b)` : cellules qui changent entre deux frames de décision
  (compteur + liste bornée), inspiré de `wmlib.diff_text` (Tycho annexe C.1).

**A4.4 —** Le rendu et les outils d'inspection sont purs (sans effet sur
l'environnement) et testés sur fixtures avec sorties attendues exactes.

## A5. Interface de tâche direct-interaction

**A5.1 — Contrainte fondatrice** (billet NVIDIA, VISTA) : l'agent reçoit les actions
disponibles **sans description des règles ni du but**, et doit inférer leurs effets en
interagissant. Le prompt de tâche est minimal, calqué sur le prompt VISTA (export,
section 3) : terminer avec le moins d'actions possible, entretenir un modèle compact
et révisable, énoncer la prédiction avant d'agir et les changements observés après,
tenir `GUIDE.md`/`WORKING.md`. Aucun indice spécifique à un jeu, nulle part
(prompts, code, fixtures) — vérifié en revue.

**A5.2 — Outils d'action.** Un outil par commande disponible (`action1`…`action6`,
`reset`), exposés seulement dans l'état Implementation (H8), filtrés par les actions
que la frame courante déclare. `action6` exige (row, col) validés dans [0,63].
Chaque appel : joue la commande via `ArcClient`, enregistre les frames typées,
incrémente le compteur officiel (A1.2 : RESET en cours de partie compte), retourne le
rendu A4.1 de la nouvelle frame de décision (+ mention des frames transitoires
disponibles via `inspect`).

Le filtrage doit atteindre la **surface réellement exposée** : le registre d'outils de
la boucle est construit une fois, alors que les commandes déclarées changent à chaque
frame. L'interface synchronise donc le groupe « action » du registre après chaque
frame absorbée (H7.1). Sans cela, le modèle continuerait de voir une commande que
l'environnement n'offre plus, et l'apprendrait par une erreur au lieu de l'observer.

**A5.3 — Comptage.** Le compteur d'actions par niveau/jeu est tenu localement ET
réconcilié avec ce que renvoie l'API ; divergence → journalisée et remontée dans le
rapport (jamais masquée).

## A6. RHAE

**A6.1 — Définition** (export Tycho §3.1, fait foi) : pour le niveau ℓ (1-indexé) de
baseline hₗ, complétion cₗ, actions aₗ :
`eₗ = min(115, 100·(hₗ/aₗ)²)` si cₗ=1 et aₗ>0, sinon 0 ; poids `wₗ = ℓ` ;
`RHAE_jeu = min( Σwₗeₗ/Σwₗ , 100·Σwₗcₗ/Σwₗ )` ;
score global = moyenne arithmétique des RHAE de jeu sur les jeux du périmètre.

**A6.1 bis — Sur quels niveaux la somme porte (décision).** ℓ parcourt **tous les
niveaux du jeu**, c'est-à-dire `1..len(baseline_actions)`, et non les seuls niveaux
que l'agent a atteints. Un niveau jamais atteint a aₗ = 0, cₗ = 0 et donc eₗ = 0, mais
il pèse `wₗ = ℓ` au dénominateur des deux termes.

Motif : c'est la seule lecture qui donne un sens au plafond. Sommer sur les seuls
niveaux atteints ferait qu'un agent complétant le premier niveau d'un jeu qui en
compte trois obtiendrait 100, à égalité avec un agent ayant tout terminé — le second
terme du `min` ne plafonnerait plus rien. Avec l'ensemble complet, ce même agent
obtient au mieux 100·(1/6) = 16,67.

**A6.2 — Baselines.** hₗ = `baseline_actions[ℓ-1]` servi par `/api/games` (source de
vérité, vérifiée le 2026-08-27 contre l'export VISTA sur sc25). En rejeu local :
baselines synthétiques du jeu `cible` (A3.2), servies par le même point d'entrée.

**A6.3 — Tests.** Vecteurs travaillés à la main dans les tests unitaires : niveau non
complété (0), agent plus efficace que l'humain (plafond 115), plafonnement par la
complétion (jeu partiellement complété), pondération croissante, cas aₗ=hₗ (=100),
reproduction d'un RHAE=100.00 de bout en bout sur `cible`.

**A6.4 — Contrat d'implémentation** (`avo.arc.rhae`). Module pur : aucune entrée-sortie,
aucun accès réseau, aucune dépendance à l'état d'un run. Il reçoit des nombres et rend
des nombres, ce qui le rend éprouvable exactement.

*Structures.*
- `NiveauJoue` (gelée) : `niveau` (1-indexé), `baseline` (hₗ), `actions` (aₗ),
  `complete` (cₗ).
- `ResultatRhae` (gelée) : `valeur` (RHAE du jeu), `efficacite_ponderee` (Σwₗeₗ/Σwₗ),
  `plafond_completion` (100·Σwₗcₗ/Σwₗ), `plafonne` (le plafond a-t-il mordu),
  `niveaux` (le détail par niveau, dans l'ordre, pour le rapport A7.3).

*Fonctions.*
- `efficacite_niveau(niveau: NiveauJoue) -> float` : eₗ selon A6.1.
- `rhae_jeu(niveaux: Sequence[NiveauJoue]) -> ResultatRhae`.
- `rhae_global(valeurs: Sequence[float]) -> float` : moyenne arithmétique.
- `niveaux_joues(historique, baselines) -> list[NiveauJoue]` : le pont entre une
  partie réellement jouée (historique typé A2.2) et les entrées de la formule.

*Refus explicites* — `RhaeInvalide` est levée, jamais un zéro silencieux :
- baseline nulle ou négative (hₗ ≤ 0) : le rapport hₗ/aₗ n'a pas de sens, et rendre 0
  ferait passer un défaut de protocole pour une mauvaise performance ;
- actions négatives, ou numéro de niveau hors de `1..len(baselines)` ;
- doublon ou trou dans la suite des niveaux fournie à `rhae_jeu` ;
- liste de jeux vide passée à `rhae_global` : une moyenne sur rien n'est pas 0, elle
  n'existe pas ;
- historique dont la première entrée n'est pas le `RESET` de création.

*Cas limites tranchés.*
- aₗ = 0 avec cₗ = 1 : eₗ = 0 par la définition elle-même (« si cₗ=1 **et aₗ>0** »).
  Le cas n'est pas atteignable par le protocole — compléter coûte au moins une
  action — mais la garde est écrite plutôt que supposée.
- Aucun arrondi n'est appliqué dans le calcul : `valeur` est un flottant de pleine
  précision. La mise en forme à deux décimales appartient au rapport (A7.3).

*Attribution des actions aux niveaux dans `niveaux_joues`* — c'est le seul point
délicat, et il est tranché ici :
- **une entrée d'historique compte pour le niveau depuis lequel elle a été jouée**,
  pas pour celui qu'elle produit. L'action qui complète le niveau 1 est renvoyée par
  l'API avec `level = 2` ; l'imputer au niveau 2 volerait une action au niveau 1 et en
  ajouterait une au suivant. Le niveau d'origine est celui de l'entrée précédente ;
- la **première** entrée est le `RESET` de création : elle est gratuite (A1.2) et
  n'est comptée nulle part ; toutes les suivantes coûtent exactement une action,
  `RESET` en cours de partie compris ;
- cₗ = 1 si et seulement si le score rendu par le serveur atteint ℓ à un moment de la
  partie. C'est le serveur qui fait autorité sur la complétion, jamais notre lecture
  des frames (même principe qu'en A5.3) ;
- les niveaux du jeu que l'historique ne mentionne pas existent quand même dans le
  résultat, avec aₗ = 0 et cₗ = 0 (A6.1 bis).

## A7. Campagne et rapport

**A7.1 — Runner.** `python -m avo run-arc --games <liste> --mode replay|live`
+ plafonds obligatoires en live : actions/niveau, actions/jeu, budget temps/jeu,
budget tokens/jeu. Exécution séquentielle des jeux ; artefacts H6.1 par jeu ;
reprise (H13.2) sans rejouer les jeux terminés.

**A7.2 — Scorecard (live).** Un scorecard ouvert par campagne, fermé en fin ; son
identifiant et son URL dans le rapport. **Garde d'accord** : le runner en `mode=live`
exige `--j-autorise-la-publication` explicite ; le périmètre exact (jeux, plafonds)
est écrit dans le journal avant lancement et l'accord du responsable est acquis pour
la première campagne (CLAUDE_PROJECT.md).

**A7.3 — Rapport.** `report.md` par campagne : tableau par jeu (niveaux, actions,
RHAE, baseline), score global, coûts (tokens, durées, actions), événements
(continuations, interventions superviseur, 413), comparaison aux références des
sources (AVO 100.00/6 624 ; VISTA 100.00/7 542 ; Tycho Opus 5 100.00/6 641), écarts
et limites. Les rapports de campagne officielle sont committés sous `docs/rapports/`.

## A8. Plan de tests ARC

**A8.1 — Unitaires** : rendu A4.1 (sorties exactes sur fixtures), coordonnées A4.2,
diff/inspect (A4.3), RHAE (A6.3), typage d'historique (A2.2), moteur du jeu `cible`
(transitions, bordures, game over, baselines).

**A8.2 — Intégration** : `ArcClient` contre `arc-replay` (nominal, RESET, game over,
épisode dévié → erreur explicite, garde anti-publication A2.3).

**A8.3 — E2E (preuve cœur du produit)** : depuis la CLI réelle, pile compose debout,
l'agent complet (llm-replay scripté pour le déterminisme) joue le jeu `cible` de bout
en bout, gagne les 3 niveaux, le RHAE calculé est exactement la valeur attendue en
forme fermée, `report.md` et la lignée existent et sont cohérents. Un second
scénario E2E couvre l'échec : game over, RESET, puis victoire.

**A8.4 — Live (hors campagne de tests)** : U22 (sonde de contrat, 1 scorecard
étiqueté probe) et campagnes U24/U25 — jamais exécutés par `make check`.
