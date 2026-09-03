"""Domaine Détail du banc c : base SQLite seedée, outils, journal des événements.

@spec docs/BACKLOG.md U29c1 — base seedée et outils du banc c
@spec docs/SPEC_BANCS.md §S15.1 (base de vérité : schéma fixe, contenus tirés au
      générateur seedé, jamais montrée à l'agent), §S15.2 (outils : effets et
      refus techniques nommés ; les outils exécutent le possible même contraire
      à la politique, et l'environnement tient le journal des transactions),
      §S17.1 (le journal est la trace que l'évaluateur confronte à la politique)

La base vit dans une connexion `sqlite3` en mémoire, une par épisode (source
§4.2 : « query relational SQLite databases via tool calls »). Le journal des
ÉVÉNEMENTS — recherches de client et transactions exécutées, dans l'ordre —
appartient à la base : c'est lui qui permet à l'évaluateur (§S17.1) de juger
l'identification et la conformité à la politique sans garde-fou codé.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from random import Random
from typing import Final

#: Statuts de commande (§S15.1) ; seuls les trois premiers sont tirés à la génération.
STATUT_EN_ATTENTE: Final = "en_attente"
STATUT_EXPEDIEE: Final = "expediee"
STATUT_LIVREE: Final = "livree"
STATUT_ANNULEE: Final = "annulee"
STATUT_RETOURNEE: Final = "retournee"
STATUTS_INITIAUX: Final = (STATUT_EN_ATTENTE, STATUT_EXPEDIEE, STATUT_LIVREE)

#: Adhésions des clients (§S15.1).
ADHESIONS: Final = ("standard", "premium")

_SCHEMA: Final = """
CREATE TABLE clients (id TEXT PRIMARY KEY, nom TEXT NOT NULL, adhesion TEXT NOT NULL);
CREATE TABLE articles (id TEXT PRIMARY KEY, nom TEXT NOT NULL, prix_centimes INTEGER NOT NULL);
CREATE TABLE commandes (id TEXT PRIMARY KEY, client TEXT NOT NULL, statut TEXT NOT NULL);
CREATE TABLE lignes (commande TEXT NOT NULL, article TEXT NOT NULL, quantite INTEGER NOT NULL);
"""

#: Gabarits neutres des contenus tirés (§S15.1) — aucun rapport avec une
#: intention ni une politique : de simples identités et objets de catalogue.
_PRENOMS: Final = (
    "Alex",
    "Camille",
    "Dominique",
    "Morgane",
    "Sacha",
    "Noa",
    "Eden",
    "Lou",
    "Charlie",
    "Ariel",
)
_NOMS: Final = (
    "Bernard",
    "Fontaine",
    "Lambert",
    "Marchand",
    "Renard",
    "Vidal",
    "Perrin",
    "Costa",
    "Weber",
    "Silva",
)
_CATALOGUE: Final = (
    "lampe",
    "carnet",
    "gourde",
    "sacoche",
    "casque",
    "clavier",
    "tapis",
    "bouilloire",
    "cadre",
    "plaid",
    "chargeur",
    "coussin",
    "gant",
    "thermos",
    "enceinte",
    "reveil",
    "brosse",
    "malette",
    "veste",
    "bonnet",
)


@dataclass(frozen=True)
class IssueOutil:
    """Issue d'un outil du domaine (§S15.2) : observation et validité TECHNIQUE.

    `valide = False` pour les seuls refus techniques nommés du tableau §S15.2 —
    rien n'a changé et rien n'entre au journal ; une exécution contraire à la
    politique reste `valide = True`, sa conformité se juge à l'évaluateur.
    """

    observation: str
    valide: bool


@dataclass(frozen=True)
class Evenement:
    """Une entrée du journal (§S15.2, §S17.1) : recherche ou transaction exécutée.

    `genre` vaut `recherche` (chercher_client : `arguments` porte le texte,
    `resultat` les identifiants rendus) ou `transaction` (outil transactionnel
    réellement exécuté : `arguments` porte commande et paramètres).
    """

    genre: str
    outil: str
    arguments: dict[str, str | int] = field(default_factory=dict)
    resultat: tuple[str, ...] = ()


class BaseDetail:
    """La base de vérité du domaine Détail et ses outils (§S15.1, §S15.2)."""

    def __init__(self, connexion: sqlite3.Connection) -> None:
        self._cx = connexion
        self.evenements: list[Evenement] = []

    # ------------------------------------------------------------- construction
    @classmethod
    def creer(cls, rng: Random) -> BaseDetail:
        """Engendre la base seedée de §S15.1 (ordre d'appel du rng fixe)."""
        base = cls._vide()
        cx = base._cx
        identites = rng.sample([(p, n) for p in _PRENOMS for n in _NOMS], rng.randint(8, 15))
        for indice, (prenom, nom) in enumerate(identites):
            cx.execute(
                "INSERT INTO clients VALUES (?, ?, ?)",
                (f"client_{indice}", f"{prenom} {nom}", rng.choice(ADHESIONS)),
            )
        noms_articles = rng.sample(_CATALOGUE, rng.randint(10, 20))
        for indice, nom_article in enumerate(noms_articles):
            cx.execute(
                "INSERT INTO articles VALUES (?, ?, ?)",
                (f"article_{indice}", nom_article, rng.randint(5, 200) * 100),
            )
        for indice in range(rng.randint(15, 30)):
            commande = f"commande_{indice}"
            client = f"client_{rng.randrange(len(identites))}"
            cx.execute(
                "INSERT INTO commandes VALUES (?, ?, ?)",
                (commande, client, rng.choice(STATUTS_INITIAUX)),
            )
            for rang in sorted(rng.sample(range(len(noms_articles)), rng.randint(1, 3))):
                cx.execute(
                    "INSERT INTO lignes VALUES (?, ?, ?)",
                    (commande, f"article_{rang}", rng.randint(1, 4)),
                )
        cx.commit()
        return base

    @classmethod
    def depuis_lignes(
        cls,
        clients: list[tuple[str, str, str]],
        articles: list[tuple[str, str, int]],
        commandes: list[tuple[str, str, str]],
        lignes: list[tuple[str, str, int]],
    ) -> BaseDetail:
        """Base construite ligne à ligne — décor déterministe des preuves (§S18.5)."""
        base = cls._vide()
        base._cx.executemany("INSERT INTO clients VALUES (?, ?, ?)", clients)
        base._cx.executemany("INSERT INTO articles VALUES (?, ?, ?)", articles)
        base._cx.executemany("INSERT INTO commandes VALUES (?, ?, ?)", commandes)
        base._cx.executemany("INSERT INTO lignes VALUES (?, ?, ?)", lignes)
        base._cx.commit()
        return base

    @classmethod
    def _vide(cls) -> BaseDetail:
        connexion = sqlite3.connect(":memory:")
        connexion.executescript(_SCHEMA)
        return cls(connexion)

    def cloner(self) -> BaseDetail:
        """Copie indépendante de la base — le calcul de l'état attendu (§S16.2)."""
        copie = sqlite3.connect(":memory:")
        self._cx.backup(copie)
        return BaseDetail(copie)

    def fermer(self) -> None:
        self._cx.close()

    # ------------------------------------------------------------------- lecture
    def dump_canonique(self) -> str:
        """Forme canonique de l'état (§S17.1) : lignes de chaque table, triées."""
        tables = {}
        for table in ("clients", "articles", "commandes", "lignes"):
            lignes = self._cx.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608 — table sûre
            tables[table] = sorted(tuple(ligne) for ligne in lignes)
        return json.dumps(tables, ensure_ascii=False, sort_keys=True, default=list)

    def nom_client(self, client: str) -> str | None:
        ligne = self._cx.execute("SELECT nom FROM clients WHERE id = ?", (client,)).fetchone()
        return None if ligne is None else str(ligne[0])

    def proprietaire(self, commande: str) -> str | None:
        requete = "SELECT client FROM commandes WHERE id = ?"
        ligne = self._cx.execute(requete, (commande,)).fetchone()
        return None if ligne is None else str(ligne[0])

    def statut(self, commande: str) -> str | None:
        requete = "SELECT statut FROM commandes WHERE id = ?"
        ligne = self._cx.execute(requete, (commande,)).fetchone()
        return None if ligne is None else str(ligne[0])

    def commandes_par_statut(self, statuts: tuple[str, ...]) -> list[tuple[str, str]]:
        """(id, client) des commandes dont le statut est dans `statuts`, triées par id."""
        marqueurs = ", ".join("?" for _ in statuts)
        requete = f"SELECT id, client FROM commandes WHERE statut IN ({marqueurs}) ORDER BY id"  # noqa: S608
        return [(str(i), str(c)) for i, c in self._cx.execute(requete, statuts).fetchall()]

    def lignes_de(self, commande: str) -> list[tuple[str, int]]:
        """(article, quantite) des lignes de la commande, triées par article."""
        lignes = self._cx.execute(
            "SELECT article, quantite FROM lignes WHERE commande = ? ORDER BY article",
            (commande,),
        ).fetchall()
        return [(str(a), int(q)) for a, q in lignes]

    # -------------------------------------------------------------------- outils
    def chercher_client(self, nom: str) -> IssueOutil:
        """§S15.2 : les clients dont le nom contient le texte ; jamais de refus."""
        trouves = self._cx.execute(
            "SELECT id, nom, adhesion FROM clients WHERE nom LIKE ? ORDER BY id",
            (f"%{nom.strip()}%",),
        ).fetchall()
        self.evenements.append(
            Evenement(
                "recherche",
                "chercher_client",
                {"nom": nom.strip()},
                tuple(str(ligne[0]) for ligne in trouves),
            )
        )
        if not trouves:
            return IssueOutil(f"Aucun client dont le nom contient « {nom.strip()} ».", True)
        lignes = [f"{i} : {n} ({a})" for i, n, a in trouves]
        return IssueOutil("Clients trouvés :\n" + "\n".join(lignes), True)

    def lire_commandes(self, client: str) -> IssueOutil:
        """§S15.2 : les commandes du client ; refus nommé si le client n'existe pas."""
        existe = self._cx.execute("SELECT 1 FROM clients WHERE id = ?", (client,)).fetchone()
        if existe is None:
            return IssueOutil(f"Client inconnu : « {client} ».", False)
        lignes = self._cx.execute(
            "SELECT id, statut FROM commandes WHERE client = ? ORDER BY id", (client,)
        ).fetchall()
        if not lignes:
            return IssueOutil(f"Le client {client} n'a aucune commande.", True)
        rendu = [f"{i} : statut {s}" for i, s in lignes]
        return IssueOutil(f"Commandes de {client} :\n" + "\n".join(rendu), True)

    def lire_commande(self, commande: str) -> IssueOutil:
        """§S15.2 : statut, lignes et montant ; refus nommé si elle n'existe pas."""
        statut = self.statut(commande)
        if statut is None:
            return IssueOutil(f"Commande inconnue : « {commande} ».", False)
        details = self._cx.execute(
            "SELECT l.article, l.quantite, a.prix_centimes FROM lignes l "
            "JOIN articles a ON a.id = l.article WHERE l.commande = ? ORDER BY l.article",
            (commande,),
        ).fetchall()
        montant = sum(int(q) * int(p) for _, q, p in details)
        rendu = [f"{a} × {q} ({int(p) * int(q)} centimes)" for a, q, p in details]
        return IssueOutil(
            f"Commande {commande} — statut {statut}, client {self.proprietaire(commande)} :\n"
            + "\n".join(rendu)
            + f"\nMontant : {montant} centimes.",
            True,
        )

    def annuler_commande(self, commande: str) -> IssueOutil:
        """§S15.2 : statut → annulee ; refus si inexistante ou déjà close."""
        statut = self.statut(commande)
        if statut is None:
            return IssueOutil(f"Commande inconnue : « {commande} ».", False)
        if statut in (STATUT_ANNULEE, STATUT_RETOURNEE):
            return IssueOutil(f"La commande {commande} est déjà {statut} : rien à annuler.", False)
        self._cx.execute("UPDATE commandes SET statut = ? WHERE id = ?", (STATUT_ANNULEE, commande))
        self._cx.commit()
        self.evenements.append(Evenement("transaction", "annuler_commande", {"commande": commande}))
        return IssueOutil(f"Commande {commande} annulée.", True)

    def modifier_ligne(self, commande: str, article: str, quantite: int) -> IssueOutil:
        """§S15.2 : remplace la quantité d'une ligne ; refus techniques nommés."""
        if self.statut(commande) is None:
            return IssueOutil(f"Commande inconnue : « {commande} ».", False)
        if quantite < 1:
            return IssueOutil(f"Quantité invalide : {quantite} (entier ≥ 1 attendu).", False)
        existe = self._cx.execute(
            "SELECT 1 FROM lignes WHERE commande = ? AND article = ?", (commande, article)
        ).fetchone()
        if existe is None:
            return IssueOutil(
                f"La commande {commande} ne porte aucune ligne pour « {article} ».", False
            )
        self._cx.execute(
            "UPDATE lignes SET quantite = ? WHERE commande = ? AND article = ?",
            (quantite, commande, article),
        )
        self._cx.commit()
        self.evenements.append(
            Evenement(
                "transaction",
                "modifier_ligne",
                {"commande": commande, "article": article, "quantite": quantite},
            )
        )
        return IssueOutil(f"Ligne {article} de {commande} portée à {quantite}.", True)

    def retourner_commande(self, commande: str) -> IssueOutil:
        """§S15.2 : statut → retournee ; refus si ni livree ni expediee."""
        statut = self.statut(commande)
        if statut is None:
            return IssueOutil(f"Commande inconnue : « {commande} ».", False)
        if statut not in (STATUT_LIVREE, STATUT_EXPEDIEE):
            return IssueOutil(
                f"La commande {commande} est {statut} : un retour ne s'applique pas.", False
            )
        self._cx.execute(
            "UPDATE commandes SET statut = ? WHERE id = ?", (STATUT_RETOURNEE, commande)
        )
        self._cx.commit()
        self.evenements.append(
            Evenement("transaction", "retourner_commande", {"commande": commande})
        )
        return IssueOutil(f"Commande {commande} retournée.", True)
