# Installation et exploitation

## 1. Prérequis

| Outil | Version minimale |
|-------|------------------|
| Docker Engine | 24.x |
| Docker Compose | v2 (`docker compose`) |
| Git | 2.x |
| Navigateur | Chrome / Firefox / Safari / Edge récent |

Pour le développement hors Docker : Python 3.11, Node.js 20, PostgreSQL 16.

---

## 2. Installation en production (Docker)

### 2.1 Récupérer le code

```bash
git clone <votre-depot> financial-management
cd financial-management
```

### 2.2 Générer la configuration

```bash
./scripts/init-secrets.sh
```

Le script :

1. génère `DJANGO_SECRET_KEY`, le mot de passe PostgreSQL et `FIELD_ENCRYPTION_KEY`
   (clé Fernet) ;
2. demande **sans écho** les deux mots de passe initiaux (ou en génère) ;
3. écrit `.env` avec les droits `600` — fichier **exclu de Git**.

> ⚠️ **Ne perdez pas `FIELD_ENCRYPTION_KEY`** : sans elle, les identifiants Ecobank
> enregistrés ne peuvent plus être déchiffrés (il faudra les ressaisir). Conservez-la
> dans un coffre-fort de secrets, en sauvegarde séparée de la base.

### 2.3 Adapter le domaine

Dans `.env` :

```ini
DJANGO_ALLOWED_HOSTS=votre-domaine.com,www.votre-domaine.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://votre-domaine.com
CORS_ALLOWED_ORIGINS=https://votre-domaine.com
DJANGO_SECURE_COOKIES=True
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SECURE_HSTS_SECONDS=31536000
NGINX_HTTP_PORT=80
```

### 2.4 Démarrer

```bash
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f backend
```

Séquence automatique au démarrage du conteneur `backend` :

1. attente de PostgreSQL (`wait_for_db`) ;
2. `migrate` (migrations contrôlées) ;
3. `collectstatic` ;
4. `bootstrap_users` (création **idempotente** des comptes initiaux, mots de passe
   hachés Argon2id) ;
5. lancement de gunicorn.

Le service `bank-sync-worker` attend que le backend soit sain, puis synchronise
périodiquement le solde bancaire (aucun appel si l'API n'est pas configurée).

### 2.5 Vérifier

```bash
curl -i http://localhost:8080/healthz        # {"status": "ok"}
docker compose ps                            # tous les services healthy
docker inspect --format '{{.State.Health.Status}}' $(docker compose ps -q backend)
```

### 2.6 Première connexion

Ouvrir `http://localhost:8080` :

1. identifiant `Emanuel` (financier) ou `Ichessfinadmin` (administrateur) ;
2. mot de passe initial défini lors de l'initialisation ;
3. **changement de mot de passe obligatoire** avant tout accès aux modules.

### 2.7 Purger les mots de passe initiaux (après la première connexion)

`bootstrap_users` est idempotent : il ne crée les comptes que s'ils n'existent pas et ne
modifie jamais un mot de passe existant. Une fois les deux comptes créés et leurs mots de
passe changés :

```bash
sed -i 's/^INITIAL_ADMIN_PASSWORD=.*/INITIAL_ADMIN_PASSWORD=/;
        s/^INITIAL_FINANCE_PASSWORD=.*/INITIAL_FINANCE_PASSWORD=/' .env
docker compose up -d backend bank-sync-worker
```

Ainsi, plus aucun mot de passe initial ne subsiste dans l'environnement des conteneurs
ni dans `.env`. À conserver ensuite dans votre coffre-fort de secrets uniquement si votre
procédure de reprise après sinistre l'exige.

---

## 3. HTTPS

1. Placer les certificats dans `./certs` (`fullchain.pem`, `privkey.pem`).
2. Copier `nginx/conf.d/https.conf.example` vers `nginx/conf.d/https.conf` et adapter
   `server_name`.
3. Exposer le port 443 dans `docker-compose.yml` :

```yaml
  nginx:
    ports:
      - "${NGINX_HTTP_PORT:-8080}:80"
      - "443:443"
    volumes:
      - ./certs:/etc/nginx/certs:ro
```

4. Redémarrer : `docker compose up -d nginx`.

Pour un certificat Let's Encrypt, utilisez certbot sur l'hôte et montez
`/etc/letsencrypt/live/<domaine>/`. Activez ensuite HSTS et les cookies sécurisés
dans `.env`.

---

## 4. Sauvegardes et restauration

### 4.1 Automatique

Le service `db-backup` exécute `pg_dump` (format custom) toutes les
`BACKUP_INTERVAL_SECONDS` (24 h par défaut) dans `./backups`, avec rotation de
`BACKUP_RETENTION_DAYS` (7 jours).

```bash
ls -lh backups/
docker compose logs db-backup
```

### 4.2 Manuelle

```bash
./scripts/backup.sh
```

### 4.3 Restauration

```bash
./scripts/restore.sh backups/finbank_20261104T120000Z.dump
```

Le script arrête le backend et le worker, restaure avec `pg_restore --clean`,
puis redémarre les services. Testez la restauration sur un environnement de
recette avant de la considérer comme acquise.

---

## 5. Exploitation courante

| Besoin | Commande |
|--------|----------|
| État des services | `docker compose ps` |
| Journaux backend | `docker compose logs -f backend` |
| Journaux nginx | `docker compose logs -f nginx` |
| Migrations | `docker compose exec backend python manage.py migrate` |
| Shell Django | `docker compose exec backend python manage.py shell` |
| Tests | `docker compose --profile test run --rm backend-test` |
| Redémarrage | `docker compose restart backend bank-sync-worker` |
| Arrêt | `docker compose down` |
| Arrêt **sans** perte de données | `docker compose down` (les volumes restent) |
| Suppression **totale** (données incluses) | `docker compose down -v` ⚠️ |

### Vérifier la persistance PostgreSQL

```bash
docker compose exec backend python manage.py shell -c \
  "from apps.finance.models import Operation; print(Operation.objects.count())"
docker compose restart db
docker compose exec backend python manage.py shell -c \
  "from apps.finance.models import Operation; print(Operation.objects.count())"
```

Le volume `pgdata` conserve les données entre les redémarrages et les recréations de
conteneurs (`docker compose down` sans `-v`).

---

## 6. Mise à jour de l'application

```bash
git pull
docker compose build
docker compose up -d
docker compose ps
```

Les migrations s'appliquent automatiquement au redémarrage du backend. Sauvegardez la
base avant chaque mise à jour majeure.

---

## 7. Développement local (hors Docker)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DJANGO_DEBUG=1 DJANGO_SECRET_KEY=dev-secret
export FIELD_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())")
python manage.py migrate
python manage.py bootstrap_users
python manage.py runserver 0.0.0.0:8000
pytest -q
```

Par défaut, sans `DATABASE_URL`, le backend utilise SQLite (confort de développement).
En production et dans Docker, PostgreSQL est obligatoire.

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxy /api -> 127.0.0.1:8000
npm test
npm run build
```

---

## 8. Dépannage

| Symptôme | Cause probable | Correction |
|----------|----------------|------------|
| `DJANGO_SECRET_KEY est requis` | `.env` absent ou vide | `./scripts/init-secrets.sh` |
| Backend redémarre en boucle | PostgreSQL pas prêt / mauvais mot de passe | `docker compose logs db` ; vérifier `POSTGRES_*` |
| `Invalid HTTP_HOST` | domaine absent de `DJANGO_ALLOWED_HOSTS` | l'ajouter dans `.env` puis `docker compose up -d` |
| Erreur CSRF sur POST | origine absente de `DJANGO_CSRF_TRUSTED_ORIGINS` | ajouter `https://votre-domaine` |
| Login OK mais UI vide | cookie refusé (HTTPS + `Secure`) | servir en HTTPS ou `DJANGO_SECURE_COOKIES=False` en local |
| `Compte temporairement verrouillé` | 5 échecs consécutifs | attendre 15 min ou déverrouiller via l'admin |
| Solde bancaire `—` | API Ecobank non configurée | espace admin → Configuration Ecobank |
| Synchronisation `FAILED` | identifiants / signature / réseau | lire le message dans le journal de sync (voir [ECOBANK.md](ECOBANK.md)) |
| Port 8080 occupé | autre service | `NGINX_HTTP_PORT=8090` dans `.env` |
| Migration en erreur | base incohérente | restaurer une sauvegarde, puis `migrate` |

---

## 9. Liste de contrôle avant mise en production

- [ ] `.env` généré par `scripts/init-secrets.sh`, droits `600`, sauvegardé dans un coffre.
- [ ] `DJANGO_DEBUG=False`, `DJANGO_SECURE_COOKIES=True`, `DJANGO_SECURE_SSL_REDIRECT=True`.
- [ ] HSTS activé après validation du HTTPS.
- [ ] `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` limités au domaine réel.
- [ ] Mots de passe initiaux changés à la première connexion (vérifier dans l'audit).
- [ ] PostgreSQL sans port publié (vérifier `docker compose ps`).
- [ ] Sauvegarde automatique active + **restauration testée**.
- [ ] `FIELD_ENCRYPTION_KEY` sauvegardée séparément de la base.
- [ ] Identifiants Ecobank saisis dans l'interface admin, test de connexion réussi.
- [ ] Journal d'audit consulté, comptes inutiles désactivés.
- [ ] `docker compose ps` : tous les services `healthy`.
