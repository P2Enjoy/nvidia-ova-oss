# certs/ — autorités de certification supplémentaires pour la construction

`@spec` U3, `docs/SPEC_HARNAIS.md` §H2.4 (environnements à proxy TLS interceptant).

Dossier **vide par défaut**. Si votre environnement fait passer le TLS sortant par
un proxy interceptant (autorité privée), déposez ici son certificat au format PEM
avec l'extension `.crt` avant de construire :

```sh
cp /chemin/vers/ca-du-proxy.crt certs/
make up   # ou make image / make build
```

Les `*.crt` déposés sont installés dans le magasin de certificats de la seule
image de développement (l'image de production ne fait aucun appel TLS à la
construction et n'en reçoit aucun) et `pip` lit le magasin système. Ils sont
**ignorés par git** : aucun certificat d'environnement n'entre dans le dépôt.
La vérification TLS n'est jamais désactivée.
