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
- `GET /api/games` → liste `{game_id, title, tags, baseline_actions[]}` (vérifié ;
  `GET /api/games/<id|préfixe>` rend la fiche d'un jeu) ;
- ouverture/fermeture/lecture de scorecard, puis commandes de jeu `RESET`,
  `ACTION1`–`ACTION5`, `ACTION6` (coordonnées de clic) et `ACTION7` (annulation,
  pour les jeux qui la servent), chaque commande renvoyant frame(s), état,
  progression et actions disponibles.

**A1.4 — Format de fil MESURÉ (sonde U22, 2026-08-31).** Le format a été mesuré sur
l'API officielle — scorecard de sonde `7528ca63-3eff-4866-97c3-8c4a6ded0e63`,
capture expurgée committée (`tests/fixtures/arc/episodes/sonde_u22*`) — et recoupé
avec la description OpenAPI publiée (`docs.arcprize.org/arc3v1.yaml`). Client et
serveur de rejeu implémentent ce format, et lui seul.

- `POST /api/scorecard/open` `{source_url?, tags?, opaque?, competition_mode?}` →
  `{card_id}`. Le serveur ajoute de lui-même l'étiquette `agent` aux tags.
- `POST /api/scorecard/close` `{card_id}` → résumé complet : `{card_id, score,
  tags, environments: [{id, score, actions, levels_completed, level_count, resets,
  runs: [{guid, actions, level_actions[], level_baseline_actions[], level_scores[],
  levels_completed, resets, score, state, completed}]}], tags_scores}`. C'est la
  **seule** source des compteurs officiels par niveau (réconciliation A5.3).
- `GET /api/scorecard/<card_id>` : mesuré **404** sur un scorecard sans partie ET
  après fermeture — ne pas bâtir dessus ; le résumé fait foi à la fermeture.
- `POST /api/cmd/RESET` `{game_id, card_id, guid?}` — `game_id` ET `card_id`
  REQUIS. Sans `guid` : crée la partie et rend le sien. Avec `guid` : relance le
  niveau courant, ou le jeu entier si aucune action n'a été jouée depuis la
  dernière transition de niveau (`full_reset` le dit) ; deux `RESET` consécutifs
  garantissent donc une partie neuve.
- `POST /api/cmd/ACTION1`–`ACTION5`, `ACTION7` : `{game_id, guid, reasoning?}` —
  `game_id` requis dans CHAQUE action, `card_id` n'y figure pas (l'attribution au
  scorecard est faite par le `RESET`). `reasoning` : blob JSON libre ≤ 16 Ko.
- `POST /api/cmd/ACTION6` : `{game_id, guid, x, y, reasoning?}` — `x` = colonne
  (0 à gauche), `y` = ligne (0 en haut), 0–63. Mesuré : `{row, col}` est refusé
  (HTTP 500), la conversion A4.2 est donc obligatoire côté client.
- Réponse commune : `{game_id, guid, frame, state, levels_completed, win_levels,
  action_input: {id: 0–7, data, reasoning}, full_reset, available_actions}`, où
  `frame` (au singulier) est la liste des grilles 64×64 émises — transitoires
  d'abord, frame de décision en dernier —, `state` vaut `NOT_PLAYED`,
  `NOT_FINISHED`, `WIN` ou `GAME_OVER`, et `available_actions` est une liste
  d'ENTIERS 0–7 (0 = RESET, jamais observé déclaré : RESET reste toujours jouable,
  A1.2). La réponse ne porte NI niveau courant, NI score, NI compteur d'actions :
  le niveau courant se dérive (`levels_completed + 1`, borné par `win_levels`) et
  le comptage d'actions est local (A5.3).
- **Affinité de session par cookies** : le serveur pose des cookies (`AWSALB*`)
  au `RESET`, à renvoyer sur chaque commande de la même partie — sans eux, les
  requêtes peuvent atteindre un backend qui ignore la session. Le client tient un
  pot de cookies par instance.
- **Jeux listés non servis** : `/api/games` peut lister un jeu que le backend de
  commandes refuse (`400`, « game … not found » — mesuré sur le jeu de moindre
  coût du listing). Un tel refus est nommé, jamais transformé en saut silencieux.
- Vérifié : `baseline_actions` du listing = `level_baseline_actions` du résumé de
  scorecard, niveau par niveau.

**A1.5 — Étiquettes de modalité.** `/api/games` porte `tags` ∈ {`click`, `keyboard`,
`keyboard_click`, absent}. Elles n'ajoutent aucune règle : la vérité des actions
disponibles est ce que la frame déclare (Tycho, remarque 1). Les tags servent
uniquement au séquencement de campagne et aux rapports.

## A2. Client API ARC

**A2.1 —** `ArcClient` (stdlib, mêmes règles transport que H4.5/H4.6 : retries bornés
sur 5xx/réseau, jamais sur 4xx, aucun secret journalisé). Méthodes : `games()`,
`open_scorecard(tags)`, `scorecard(id)`, `close_scorecard(id)`,
`reset(game_id, card_id, guid?)`, `action(n, game_id, guid, coords?)`. Le client
tient un pot de cookies par instance (affinité de session A1.4) et confine la
conversion de coordonnées A4.2. Réponses normalisées en `FrameResult` typé : frames
(liste de grilles 64×64), état, score (= niveaux complétés), niveau courant dérivé,
niveaux requis pour gagner, actions disponibles (noms `RESET`/`ACTION1`–`ACTION7`),
guid, drapeau de remise à zéro complète.

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
expurgées de tout secret — une ligne = `{"command", "request", "response"}`). Le
premier épisode réel est celui de la sonde U22 (`sonde_u22.jsonl`). Une requête qui
dévie de l'épisode — commande différente, ou corps dont une clé ou une valeur
s'écarte de l'enregistré, `card_id` et `guid` exceptés car propres à chaque
session — reçoit une réponse d'erreur explicite (test rouge lisible).

**A3.4 — Seed.** `make seed` régénère les fixtures déterministes (scénarios llm-replay,
paramètres du jeu `cible`, épisodes) — c'est le contrat de données de démonstration du
dépôt (CLAUDE.md §8) : reproductible, couvrant succès, refus (401), erreurs (413,
game over) et branches (RESET, continuation).

## A4. Rendu texte et mémoire de frames

**A4.1 — Observation** (billet NVIDIA : texte seul, grille exacte). Rendu canonique
d'une grille : 64 lignes de 64 valeurs décimales séparées par des espaces, précédées
d'une ligne d'état (`niveau, score, actions_du_niveau, actions_disponibles`). Aucune
image, aucun autre enrichissement dans l'observation courante.

**A4.2 — Convention de coordonnées (MESURÉE en U22).** Interne : (row, col), 0-basé,
origine en haut à gauche. Le fil exige `x` = colonne et `y` = ligne (A1.4) ; la
conversion `(row, col) → {x: col, y: row}` est confinée au client A2.1 — mesuré :
le serveur refuse `{row, col}` — et l'agent ne voit que (row, col).

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

**A5.2 — Outils d'action.** Un outil par commande disponible (`action1`…`action7`,
`reset`), exposés seulement dans l'état Implementation (H8), filtrés par les actions
que la frame courante déclare — sauf `reset`, toujours offert : le protocole le rend
toujours jouable (A1.2) et l'API ne le déclare jamais dans `available_actions`
(mesuré, A1.4). `action6` exige (row, col) validés dans [0,63].
Chaque appel : joue la commande via `ArcClient`, enregistre les frames typées,
incrémente le compteur officiel (A1.2 : RESET en cours de partie compte), retourne le
rendu A4.1 de la nouvelle frame de décision (+ mention des frames transitoires
disponibles via `inspect`).

Le filtrage doit atteindre la **surface réellement exposée** : le registre d'outils de
la boucle est construit une fois, alors que les commandes déclarées changent à chaque
frame. L'interface synchronise donc le groupe « action » du registre après chaque
frame absorbée (H7.1). Sans cela, le modèle continuerait de voir une commande que
l'environnement n'offre plus, et l'apprendrait par une erreur au lieu de l'observer.

**A5.3 — Comptage.** Le compteur d'actions par niveau/jeu est tenu localement.
L'API ne rend AUCUN compteur par frame (mesuré, A1.4) : la réconciliation avec les
compteurs officiels se fait sur le résumé de scorecard (`level_actions` par run) à
la fermeture — c'est une preuve de campagne (U24) ; divergence → journalisée et
remontée dans le rapport (jamais masquée).

**A5.4 — État terminal.** L'interface implémente `etat_terminal()` (SPEC_HARNAIS
§H8.3) : « victoire » quand la frame courante déclare l'état `WIN` (A1.4), `None`
sinon. `GAME_OVER` n'est PAS terminal : `RESET` reste jouable (A1.2), relance la
tentative, et la boucle traite l'échec en Bug-Fixing (H8.1). Après `WIN`,
l'environnement n'offre plus que `RESET` (mesuré, run opérateur U21) : poursuivre ne
peut ni améliorer le score ni apprendre quoi que ce soit d'utile au run.

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

**A7.4 — Contrat d'implémentation du runner** (`avo.arc.campagne`, `avo.arc.rapport`).

*Surface CLI.*

```
python -m avo run-arc --mode replay|live [--games a,b,c]
                      [--actions-max-niveau N] [--actions-max-jeu N]
                      [--budget-secondes-jeu S] [--budget-tokens-jeu N]
                      [--tours-max N] [--run-id ID]
                      [--j-autorise-la-publication]
python -m avo resume <run_id>
```

- `--games` absent : tous les jeux que `/api/games` déclare. Un identifiant inconnu du
  serveur est un refus nommé, jamais un jeu silencieusement sauté.
- **En `--mode live`, les quatre plafonds sont obligatoires** (A7.1) et leur absence
  est un refus qui les nomme. En rejeu ils sont facultatifs : les bornes d'actions
  retombent sur la configuration (H8.3), les budgets de temps et de tokens sur
  « aucune limite ».
- **Garde d'accord** (A7.2) : `--mode live` sans `--j-autorise-la-publication` est un
  refus. Le drapeau est explicite parce que la conséquence l'est : jouer publie un
  scorecard au nom du responsable.

*Budgets et bornes — comment ils cohabitent avec H8.3.* H8.3 interdit de borner du
temps d'horloge **à l'intérieur** de la boucle : aucune temporisation n'interrompt une
opération en vol. Les budgets de temps et de tokens de A7.1 sont d'une autre nature —
ce sont des conditions d'arrêt **de campagne**, évaluées entre deux tours, qui closent
le jeu proprement et nomment leur motif dans le rapport. Les deux règles sont donc
compatibles, et c'est la seule lecture qui permet à une campagne live de ne pas
dépenser sans fin.

*Déroulé d'un jeu.* Workspace du run (H6.1) → un scorecard pour la campagne, ouvert
avant le premier jeu et fermé après le dernier → pour chaque jeu : interface (A5),
registre (outils d'action, d'inspection et de notes), boucle (H8), superviseur (H10),
lignée (H9) → à la fin du jeu : historique typé persisté (A2.2), RHAE calculé (A6) à
partir des baselines de `/api/games`, résultat enregistré. Le même chemin de code sert
en rejeu et en live : seul l'hôte change, ce qui évite une branche live jamais éprouvée.

*Reprise* (H13.2, A7.1). L'état de campagne vit dans `runs/<id>/campagne.json` :
plafonds, scorecard, et pour chaque jeu son statut et son résultat. Il est réécrit
**après chaque jeu**, de sorte qu'une interruption ne coûte au plus qu'un jeu.
`resume <run_id>` relit ce fichier, saute les jeux terminés et reprend à la suite ; les
notes du run (`GUIDE.md`) ne sont pas réinitialisées, donc la connaissance acquise
survit.

**Décision : la reprise est de granularité JEU, pas action.** Un jeu interrompu est
rejoué depuis le début, dans une partie neuve. Motif : reprendre une partie en cours
supposerait de retrouver la frame courante, qu'aucune requête ne rend gratuitement —
la redemander coûterait une action, et le score mêlerait deux tentatives, ce qui
priverait le RHAE de sens. Ce qui coûte cher, ce sont les jeux déjà terminés : ils ne
sont jamais rejoués.

**Décision : une lignée par JEU, sous `runs/<id>/lineage/<game_id>/`.** La politique
H9.1 est « correct ∧ ≥ meilleur » ; or le score H9.2 est
`(niveaux complétés, −actions)` **du jeu courant**. Une lignée unique pour toute la
campagne refuserait toute version du deuxième jeu, qui repart à zéro niveau — la
progression du premier bloquerait définitivement l'enregistrement de la seconde. La
monotonie n'a de sens qu'à l'intérieur d'un jeu, et c'est bien ce que décrit H9.2
(« chaque complétion de niveau produit un commit de lignée avec son score »).

*Structures.* `Plafonds` (gelée) ; `ResultatJeu` (gelée : `game_id`, `guid`, `niveaux`,
`rhae`, `tours`, `arret`, `actions`, `tokens`, `secondes`, `evenements`) ;
`ResultatCampagne` (gelée : `run_id`, `mode`, `card_id`, `plafonds`, `jeux`,
`score_global`). Le rapport est une **fonction pure** de `ResultatCampagne` et des
métriques lues : il ne rejoue rien et ne devine rien.

*Refus explicites* — `CampagneInvalide`, jamais un repli silencieux : mode live sans
accord, mode live sans plafond, jeu inconnu du serveur, `--games` vide, reprise d'un
run inexistant ou dont le `campagne.json` est absent.

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

**A8.5 — Contrat d'implémentation des E2E (U21).** Décisions prises avant le code,
mesures à l'appui (journal du 2026-08-30) :

1. **Cassettes de scénario seedées et committées** sous
   `tests/fixtures/llm/cassettes/` : `e2e_victoire.jsonl` et `e2e_echec.jsonl`,
   produites par le générateur déterministe `tests/e2e/generer_cassettes.py`
   (cible `make seed-e2e`). Procédé : capture en deux passes — la campagne joue
   d'abord avec un transport injecté qui répond selon la politique scriptée et
   relève les corps exacts émis ; la cassette apparie ensuite ces corps aux mêmes
   réponses. L'enveloppe de réponse est le gabarit de la cassette réelle du
   contrat (aucune forme inventée, §H4.7) ; la politique scriptée rejoue
   `chemin_optimal()` du moteur `cible` — outil de test de §A3.2, jamais employé
   par le harnais. Horodatage de cassette fixe : la régénération est identique
   octet à octet, et le générateur le vérifie lui-même (double génération
   comparée). Le rejoueur chargeant les cassettes au démarrage, toute
   (re)génération exige de relancer la pile (`make down && make up`).
2. **Environnement épinglé**, partagé par le générateur, les tests et la
   vérification opérateur — la configuration de rejeu lisant l'environnement puis
   `.env` avant ses défauts, tout champ qui influe sur les corps de requête ou le
   déroulé est fixé explicitement : `OLLAMA_CONTEXT_LENGTH=229376`,
   `AVO_MODEL=qwen3.6:35b`, `AVO_THINK=false`, `AVO_TEMPERATURE=0.7`,
   `AVO_CONTEXT_SOFT_RATIO=0.85`, `AVO_TOOL_STEPS_MAX=40`,
   `AVO_SUP_STALL_ACTIONS=60`, `AVO_SUP_COOLDOWN=30`, et `AVO_NUM_PREDICT`
   **discriminant de scénario** : `4096` (victoire) / `4097` (échec) — les deux
   scénarios partagent leur première observation, ce champ rend leurs corps
   disjoints dans le dossier de cassettes fusionné.
3. **Exécution** : `make test-e2e` passe par le réseau de l'hôte (même mesure que
   `run-arc`, 2026-08-28) et exige la pile compose debout ; à défaut, échec
   explicite nommant `make up`. La campagne `make check` reste hors ligne : la
   pile est locale et ne sert que de l'enregistré.
4. **Scénarios et valeurs attendues, en forme fermée** (jeu `cible`, curseur
   initial (32,32), baselines [39, 19, 18]) :
   - *victoire* : politique parfaite, 76 actions (39+19+18), 3/3 niveaux,
     RHAE exactement **100.00** ;
   - *échec → RESET → victoire* : trois clics en (32,32) hors cible au niveau 1
     → `GAME_OVER`, `RESET` compté, puis parfait — niveau 1 à **43** actions,
     80 au total, RHAE du jeu = min((1·100·(39/43)² + 2·100 + 3·100)/6, 100),
     recalculé indépendamment dans le test ;
   - *artefacts* : `report.md` (sections A7.3) cohérent avec les compteurs,
     frames par niveau, lignée git isolée par jeu portant les complétions,
     métriques `llm`/`action`/`jeu` présentes ;
   - *reprise* : `python -m avo resume <run_id>` par la CLI réelle rend le même
     bilan sans nouvel appel au modèle (compteurs inchangés, aucune métrique
     `llm` nouvelle).
5. Au moins un scénario s'exécute par **sous-processus réel** `python -m avo`
   (CLI réelle, MASTER_PLAN §5) avec l'environnement épinglé ; les assertions
   fines peuvent passer par `cli.main` en processus. Les workspaces de test vont
   dans un répertoire temporaire (`AVO_RUNS_DIR`), la commande opérateur
   documentée écrivant, elle, sous `runs/`.
