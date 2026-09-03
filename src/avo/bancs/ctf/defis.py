"""Familles de défis du banc b et générateur seedé.

@spec docs/BACKLOG.md U29b1 — générateur des cinq familles + matérialisation
@spec docs/SPEC_BANCS.md §S9.1 (défi = famille + plan + drapeau ; plan PUR,
      identique octet pour octet à seed égal ; en `aleatoire` la famille est le
      premier tirage), §S9.2 (les cinq familles, solubles par construction avec
      l'outillage garanti de §S10.4), §S8.3 (paramètres d'un épisode)

Le générateur produit un PLAN — liste ordonnée de fichiers relatifs et de leurs
octets — sans toucher au disque ; `materialiser` l'écrit sous le répertoire de
travail. Les métadonnées de recouvrement (`chemin_drapeau`, `transformations`,
`etapes`) n'existent que pour les preuves de solvabilité : elles ne sont jamais
montrées à l'agent.
"""

from __future__ import annotations

import base64
import codecs
import gzip
import io
import string
import tarfile
from dataclasses import dataclass
from pathlib import Path
from random import Random

#: Familles de défis (§S9.2) et sentinelle de tirage au seed (§S8.3).
FAMILLES = ("fouille", "encodage", "archive", "binaire", "piste")
ALEATOIRE = "aleatoire"

#: Format du drapeau (§S9.1) : `FLAG{` + 16 hexadécimaux tirés + `}`.
PREFIXE_DRAPEAU = "FLAG{"

#: Transformations réversibles de la famille `encodage` (§S9.2).
TRANSFORMATIONS = ("base64", "hexadecimal", "rot13", "inversion")

_ALPHANUM = string.ascii_letters + string.digits


class FamilleInconnue(ValueError):
    """Famille absente de §S9.2 : l'erreur nomme les familles disponibles."""


@dataclass(frozen=True)
class Fichier:
    """Un fichier du plan : chemin relatif au répertoire de travail, octets."""

    chemin: str
    contenu: bytes


@dataclass(frozen=True)
class PlanDefi:
    """Plan pur d'un défi (§S9.1) ; les métadonnées servent aux preuves seules.

    `transformations` : famille `encodage` — compositions dans l'ordre
    d'application ; famille `archive` — couches dans l'ordre d'application
    (la plus interne d'abord). `etapes` : famille `piste` — chemins de la
    chaîne, fichier racine en premier.
    """

    seed: int
    famille: str
    drapeau: str
    fichiers: tuple[Fichier, ...]
    chemin_drapeau: str
    transformations: tuple[str, ...] = ()
    etapes: tuple[str, ...] = ()


def generer_defi(seed: int, famille: str = ALEATOIRE) -> PlanDefi:
    """Engendre le plan du défi de `seed` (§S9.1) ; famille tirée en `aleatoire`."""
    if famille != ALEATOIRE and famille not in FAMILLES:
        raise FamilleInconnue(
            f"famille inconnue : « {famille} ». Disponibles : {', '.join(FAMILLES)}, {ALEATOIRE}."
        )
    rng = Random(seed)
    if famille == ALEATOIRE:
        famille = rng.choice(FAMILLES)
    drapeau = PREFIXE_DRAPEAU + "".join(rng.choice("0123456789abcdef") for _ in range(16)) + "}"
    constructeurs = {
        "fouille": _construire_fouille,
        "encodage": _construire_encodage,
        "archive": _construire_archive,
        "binaire": _construire_binaire,
        "piste": _construire_piste,
    }
    return constructeurs[famille](seed, drapeau, rng)


def materialiser(plan: PlanDefi, racine: Path) -> None:
    """Écrit le plan sous `racine` (§S9.1) ; les répertoires naissent au besoin."""
    for fichier in plan.fichiers:
        cible = racine / fichier.chemin
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(fichier.contenu)


# ------------------------------------------------------------------ communs --
def _ligne_journal(rng: Random) -> str:
    """Une ligne de journal gabarit, neutre et sans rapport avec le drapeau."""
    return (
        f"2026-0{rng.randint(1, 9)}-{rng.randint(10, 28)} "
        f"service_{rng.randint(1, 40)} : requete {rng.randrange(100000):05d} "
        f"traitee en {rng.randint(1, 900)} ms"
    )


def _chaine(rng: Random, longueur: int) -> str:
    """Chaîne alphanumérique tirée — jamais de `{`, donc jamais `FLAG{`."""
    return "".join(rng.choice(_ALPHANUM) for _ in range(longueur))


def _arborescence(rng: Random, minimum: int, maximum: int, profondeur_max: int = 3) -> list[str]:
    """Chemins de répertoires tirés, certains cachés par préfixe `.` (§S9.2)."""
    dossiers: list[str] = []
    for indice in range(rng.randint(minimum, maximum)):
        parent = rng.choice([""] + dossiers) if dossiers else ""
        if parent.count("/") + (1 if parent else 0) >= profondeur_max:
            parent = ""
        prefixe = "." if rng.random() < 0.3 else ""
        nom = f"{prefixe}dossier_{indice}"
        dossiers.append(f"{parent}/{nom}" if parent else nom)
    return dossiers


# ------------------------------------------------------------------ fouille --
def _construire_fouille(seed: int, drapeau: str, rng: Random) -> PlanDefi:
    """§S9.2 `fouille` : le drapeau en clair sur une ligne d'un fichier tiré."""
    dossiers = _arborescence(rng, 8, 15)
    nb_fichiers = rng.randint(30, 60)
    contenus: list[list[str]] = []
    chemins: list[str] = []
    for indice in range(nb_fichiers):
        dossier = rng.choice([""] + dossiers)
        chemin = f"{dossier}/journal_{indice}.log" if dossier else f"journal_{indice}.log"
        chemins.append(chemin)
        contenus.append([_ligne_journal(rng) for _ in range(rng.randint(5, 20))])
    for _ in range(rng.randint(4, 8)):
        cible = rng.randrange(nb_fichiers)
        gabarit = rng.choice(("NOTE{", "TEST{"))
        leurre = gabarit + _chaine(rng, 16) + "}"
        contenus[cible].insert(rng.randint(0, len(contenus[cible])), leurre)
    porteur = rng.randrange(nb_fichiers)
    contenus[porteur].insert(rng.randint(0, len(contenus[porteur])), drapeau)
    fichiers = tuple(
        Fichier(chemin, ("\n".join(lignes) + "\n").encode())
        for chemin, lignes in zip(chemins, contenus, strict=True)
    )
    return PlanDefi(seed, "fouille", drapeau, fichiers, chemin_drapeau=chemins[porteur])


# ----------------------------------------------------------------- encodage --
def _appliquer_transformation(nom: str, texte: str) -> str:
    """Applique une transformation de §S9.2 (toutes réversibles)."""
    if nom == "base64":
        return base64.b64encode(texte.encode()).decode()
    if nom == "hexadecimal":
        return texte.encode().hex()
    if nom == "rot13":
        return codecs.encode(texte, "rot13")
    if nom == "inversion":
        return texte[::-1]
    raise FamilleInconnue(f"transformation inconnue : « {nom} ».")


def inverser_transformation(nom: str, texte: str) -> str:
    """Inverse d'une transformation — chemin canonique des preuves (§S12.5)."""
    if nom == "base64":
        return base64.b64decode(texte.encode()).decode()
    if nom == "hexadecimal":
        return bytes.fromhex(texte).decode()
    if nom == "rot13":
        return codecs.decode(texte, "rot13")
    if nom == "inversion":
        return texte[::-1]
    raise FamilleInconnue(f"transformation inconnue : « {nom} ».")


def _construire_encodage(seed: int, drapeau: str, rng: Random) -> PlanDefi:
    """§S9.2 `encodage` : composition de 1–3 transformations, parmi des leurres."""
    nb_blocs = rng.randint(5, 10)
    porteur = rng.randrange(nb_blocs)
    fichiers: list[Fichier] = []
    composition_porteur: tuple[str, ...] = ()
    for indice in range(nb_blocs):
        composition = tuple(rng.choice(TRANSFORMATIONS) for _ in range(rng.randint(1, 3)))
        charge = drapeau if indice == porteur else _chaine(rng, 24)
        resultat = charge
        for transformation in composition:
            resultat = _appliquer_transformation(transformation, resultat)
        if indice == porteur:
            composition_porteur = composition
        fichiers.append(Fichier(f"bloc_{indice}.dat", (resultat + "\n").encode()))
    return PlanDefi(
        seed,
        "encodage",
        drapeau,
        tuple(fichiers),
        chemin_drapeau=f"bloc_{porteur}.dat",
        transformations=composition_porteur,
    )


# ------------------------------------------------------------------ archive --
def _envelopper_tar(donnees: bytes, nom_membre: str) -> bytes:
    """Une couche tar déterministe : un seul membre, métadonnées neutres."""
    tampon = io.BytesIO()
    with tarfile.open(fileobj=tampon, mode="w") as archive:
        membre = tarfile.TarInfo(name=nom_membre)
        membre.size = len(donnees)
        membre.mtime = 0
        archive.addfile(membre, io.BytesIO(donnees))
    return tampon.getvalue()


def _construire_archive(seed: int, drapeau: str, rng: Random) -> PlanDefi:
    """§S9.2 `archive` : 2–4 couches tar/gzip, extension parfois trompeuse."""
    lignes = [_ligne_journal(rng) for _ in range(rng.randint(3, 8))]
    lignes.insert(rng.randint(0, len(lignes)), drapeau)
    donnees = ("\n".join(lignes) + "\n").encode()
    couches = tuple(rng.choice(("tar", "gzip")) for _ in range(rng.randint(2, 4)))
    for indice, couche in enumerate(couches):
        if couche == "tar":
            donnees = _envelopper_tar(donnees, f"contenu_{indice}")
        else:
            donnees = gzip.compress(donnees, mtime=0)
    extension = rng.choice((".tar", ".tar.gz", ".txt", ".dat"))
    chemin = f"sauvegarde_{rng.randint(0, 99)}{extension}"
    fichiers = [Fichier(chemin, donnees)]
    for indice in range(rng.randint(3, 6)):
        lignes_leurre = [_ligne_journal(rng) for _ in range(rng.randint(5, 15))]
        contenu_leurre = ("\n".join(lignes_leurre) + "\n").encode()
        fichiers.append(Fichier(f"journal_{indice}.log", contenu_leurre))
    return PlanDefi(
        seed,
        "archive",
        drapeau,
        tuple(fichiers),
        chemin_drapeau=chemin,
        transformations=couches,
    )


def desarchiver(couche: str, donnees: bytes) -> bytes:
    """Défait une couche d'archive — chemin canonique des preuves (§S12.5)."""
    if couche == "gzip":
        return gzip.decompress(donnees)
    if couche == "tar":
        with tarfile.open(fileobj=io.BytesIO(donnees), mode="r") as archive:
            membre = archive.getmembers()[0]
            extrait = archive.extractfile(membre)
            if extrait is None:
                raise FamilleInconnue(f"membre illisible : « {membre.name} ».")
            return extrait.read()
    raise FamilleInconnue(f"couche inconnue : « {couche} ».")


# ------------------------------------------------------------------ binaire --
def _construire_binaire(seed: int, drapeau: str, rng: Random) -> PlanDefi:
    """§S9.2 `binaire` : le drapeau ASCII inséré dans un blob d'octets tirés."""
    taille = rng.randint(64, 256) * 1024
    blob = bytearray(rng.randbytes(taille))
    insertions = [drapeau.encode()] + [
        _chaine(rng, len(drapeau)).encode() for _ in range(rng.randint(3, 6))
    ]
    for sequence in insertions:
        position = rng.randrange(len(blob))
        blob[position:position] = sequence
    chemin = rng.choice(("programme.bin", "noyau.img", "capture.raw"))
    return PlanDefi(
        seed, "binaire", drapeau, (Fichier(chemin, bytes(blob)),), chemin_drapeau=chemin
    )


# -------------------------------------------------------------------- piste --
#: Gabarit de la ligne d'indice (§S9.2) ; le chemin suit le deux-points.
GABARIT_INDICE = "Indice : consulter "


def _construire_piste(seed: int, drapeau: str, rng: Random) -> PlanDefi:
    """§S9.2 `piste` : chaîne d'indices de la racine jusqu'au drapeau."""
    dossiers = _arborescence(rng, 5, 10)
    nb_etapes = rng.randint(4, 7)
    depart = rng.choice(("consignes.txt", "note.txt", "lisez_moi.txt"))
    chemins_etapes = [depart]
    for indice in range(nb_etapes):
        dossier = rng.choice(dossiers)
        chemins_etapes.append(f"{dossier}/fragment_{indice}.txt")
    fichiers: list[Fichier] = []
    for position, chemin in enumerate(chemins_etapes):
        lignes = [_ligne_journal(rng) for _ in range(rng.randint(3, 8))]
        if position < len(chemins_etapes) - 1:
            ligne_utile = GABARIT_INDICE + chemins_etapes[position + 1]
        else:
            ligne_utile = drapeau
        lignes.insert(rng.randint(0, len(lignes)), ligne_utile)
        fichiers.append(Fichier(chemin, ("\n".join(lignes) + "\n").encode()))
    return PlanDefi(
        seed,
        "piste",
        drapeau,
        tuple(fichiers),
        chemin_drapeau=chemins_etapes[-1],
        etapes=tuple(chemins_etapes),
    )
