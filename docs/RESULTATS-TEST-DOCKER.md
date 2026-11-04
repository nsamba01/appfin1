# Résultats du test `docker compose`

Exécution du 4 novembre 2026. **Docker n'existe pas dans l'environnement d'exécution**
(pas de démon, pas de binaire `docker`). Les tests ci-dessous reproduisent donc ce que
Compose fait, avec le maximum de fidélité : interpolation réelle des variables,
vérification structurelle complète, puis exécution **du script d'entrée du conteneur**
sur une base PostgreSQL vide.

---

## 1. Validation du fichier Compose

```text
$ python scripts/validate-compose.py
66/66 vérifications OK
docker-compose.yml : structure valide (équivalent de `docker compose config`)
```

| Contrôle | Résultat |
|----------|----------|
| Interpolation `${VAR}`, `${VAR:-défaut}`, `${VAR:?message}` | 36 variables résolues |
| Sans `.env` → message actionnable | `DJANGO_SECRET_KEY manquant - creez .env avec scripts/init-secrets.bat` |
| `.env` produit par `init-secrets.ps1` suffisant | oui (27 variables + valeurs par défaut Compose) |
| Services | db, backend, bank-sync-worker, frontend, nginx, db-backup, backend-test |
| Images / Dockerfiles | tous présents et analysables |
| Réseaux | `backend_net`, `app_net` correctement référencés |
| Volumes nommés / chemins montés | `pgdata`, `staticfiles`, `media`, `nginx_logs` + chemins existants |
| `depends_on` + `service_healthy` | chaque dépendance a bien un healthcheck |
| Ports publiés | 1 seul (nginx) ; PostgreSQL jamais exposé |
| Upstreams nginx | `backend` / `frontend` = services Compose réels |
| Secrets littéraux dans le fichier | aucun (tout passe par `.env`) |
| Scripts & commandes | `entrypoint.sh`, `wait_for_db`, `bootstrap_users` présents |

---

## 2. Démarrage réel du service `backend`

`backend/entrypoint.sh` exécuté tel quel, avec les variables résolues par Compose, sur
une base PostgreSQL **vide** :

```text
[entrypoint] Démarrage du backend Django (config.settings)
Base de données disponible.
[entrypoint] Application des migrations...        → 38 migrations appliquées
[entrypoint] Collecte des fichiers statiques...   → 163 fichiers
[entrypoint] Initialisation sécurisée des comptes → Comptes créés : Ichessfinadmin (ADMIN), Emanuel (FINANCE)
[entrypoint] Exécution : gunicorn config.wsgi:application --bind 0.0.0.0:8010 --workers 2 --threads 2
```

Puis, contre cette instance :

| Vérification | Résultat |
|--------------|----------|
| `/healthz` | `{"status": "ok"}` |
| Connexion initiale `Emanuel` | `200`, `must_change_password: true` |
| Accès métier avant changement de mot de passe | `403` |
| Changement de mot de passe | `200` |
| Création de 3 opérations | `201` ×3 |
| Balances | entrées `5000.00`, sorties `1750.00`, solde `3250.00` |
| Dashboard | `financial.balance 3250.00`, `comparison.gap null`, `UNAVAILABLE` |
| Config bancaire par un financier | `403` |
| Export Excel | `200` |

Aucun écart avec le comportement attendu : migrations, comptes initiaux hachés,
verrou de changement de mot de passe, calculs `Decimal`, RBAC et exports fonctionnent
dans la configuration exacte du conteneur.

---

## 3. Ce qui reste non couvert ici

1. **Construction des images** (`docker build`) : dépend de l'accès aux registres
   (Docker Hub / npm / PyPI) et du démon Docker.
2. **Réseau Docker** : la résolution `db` → `backend` et le partage du volume
   `staticfiles` entre `backend` et `nginx` ne peuvent être éprouvés sans démon.
3. **Nginx** : la configuration a été validée structurellement (accolades, upstreams,
   emplacements), pas démarrée.

Ces trois points sont couverts par `docker compose build && docker compose up -d`
sur votre poste. En cas d'échec, le message exact permettra de corriger immédiatement.

---

## 4. Rejouer ces tests

```bash
python scripts/validate-compose.py          # 66 contrôles, sans Docker
docker compose build                        # sur un hôte Docker
docker compose up -d
docker compose ps
```
