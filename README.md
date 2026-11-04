# ICHESS Finance — Gestion financière, bancaire & administrative

Application web professionnelle de gestion des opérations financières internes, de
consultation du solde bancaire **Ecobank** et de comparaison automatique entre la
situation financière interne et la situation bancaire réelle.

> **Stack** : Python 3.11 · Django 5 + Django REST Framework · PostgreSQL 16 · React 18 +
> TypeScript · Tailwind CSS · Recharts · Docker / Docker Compose · Nginx (reverse proxy)

---

## 1. Fonctionnalités

### Espace financier (`FINANCE`)
- Tableau de bord financier **et** bancaire (page d'accueil après connexion).
- Enregistrement des opérations (entrée / sortie) avec date, libellé, montant, référence
  et observation.
- Calcul **côté serveur** en `Decimal` : total des entrées, total des sorties, solde
  financier, balance financière.
- Recherche, filtres par période et par type, pagination, détail et historique d'une
  opération.
- Export **Excel** (.xlsx) et **PDF** des opérations filtrées.
- Consultation du solde bancaire Ecobank (masqué, horodaté, avec état de connexion),
  de l'historique des synchronisations et des balances.
- **Aucun** accès à l'administration, aux utilisateurs ou à la configuration bancaire.

### Espace administrateur (`ADMIN`)
- Création / modification d'utilisateurs, attribution de rôle, activation / désactivation,
  déverrouillage, réinitialisation de mot de passe, changement forcé.
- Journal des connexions et journal d'audit complet (filtres, recherche).
- Configuration de l'API Ecobank (identifiants, environnement, fréquence, timeout),
  test de connexion, synchronisation manuelle, journal des synchronisations.
- Paramètres généraux (identité, devise, règles métier applicables aux financiers).
- Peut créer autant de comptes financiers que nécessaire **sans toucher au code**.

### Sécurité (résumé — détail dans [docs/SECURITY.md](docs/SECURITY.md))
Argon2id · JWT court + refresh en cookie `HttpOnly` · RBAC serveur · verrouillage
anti-force brute · rotation et révocation des sessions · protection CSRF/XSS/injection ·
CORS restrictif · en-têtes de sécurité (CSP, HSTS, etc.) · chiffrement Fernet des
secrets bancaires au repos · journalisation filtrée (aucun secret dans les logs) ·
PostgreSQL non exposé · sauvegardes automatiques.

---

## 2. Démarrage rapide (Docker)

Prérequis : Docker 24+ et Docker Compose v2.

```bash
git clone <votre-depot> financial-management
cd financial-management

# 1. Générer la configuration sécurisée (.env) — les mots de passe ne sont jamais
#    écrits dans Git et sont saisis sans écho.
./scripts/init-secrets.sh

# 2. Construire et démarrer
docker compose build
docker compose up -d

# 3. Vérifier
docker compose ps
docker compose logs -f backend
```

L'application est disponible sur **http://localhost:8080** (port configurable via
`NGINX_HTTP_PORT`).

### Comptes initiaux

Créés automatiquement au premier démarrage à partir des variables
`INITIAL_*_USERNAME` / `INITIAL_*_PASSWORD` du fichier `.env` (jamais dans le code,
jamais dans Git) :

| Rôle | Identifiant | Mot de passe initial |
|------|-------------|----------------------|
| Financier | `Emanuel` | communiqué avec la livraison (`INITIAL_FINANCE_PASSWORD`) |
| Administrateur | `Ichessfinadmin` | communiqué avec la livraison (`INITIAL_ADMIN_PASSWORD`) |

> **Le changement de mot de passe est obligatoire à la première connexion** : tant
> qu'il n'est pas effectué, l'API refuse toute autre action (`403 password_change_required`).
> Les mots de passe sont hachés en **Argon2id** avant insertion en base ; ils ne sont
> jamais affichés, renvoyés par l'API ni écrits dans les journaux.

Le fichier `.env` livré localement contient ces identifiants initiaux et est exclu de
Git. En production, exécutez `./scripts/init-secrets.sh` pour générer des secrets neufs
et saisir vos propres mots de passe initiaux.

---

## 3. Architecture

```
financial-management/
├── backend/                        # Django 5 + DRF (Python 3.11)
│   ├── config/                     # settings, urls, wsgi, asgi
│   ├── apps/
│   │   ├── core/                   # base models, chiffrement, permissions, middlewares,
│   │   │                           # throttling, pagination, commandes de gestion
│   │   ├── users/                  # utilisateurs, rôles, tentatives de connexion
│   │   ├── authentication/         # login, refresh, logout, changement de mot de passe
│   │   ├── audit/                  # journal d'audit et journal des connexions
│   │   ├── finance/                # opérations, balances, exports Excel/PDF
│   │   ├── banking/                # configuration Ecobank, synchronisation, historique
│   │   └── dashboard/              # agrégats, comparaison, écart, séries graphiques
│   ├── tests/                      # 132 tests automatisés
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── Dockerfile
│   └── entrypoint.sh
├── frontend/                       # React 18 + TypeScript + Tailwind + Recharts
│   ├── src/{components,contexts,hooks,layouts,pages,services,types,utils}
│   ├── src/**/*.test.tsx           # 39 tests Vitest + Testing Library
│   ├── nginx.conf                  # serveur statique du SPA
│   └── Dockerfile
├── nginx/                          # reverse proxy (HTTP + exemple HTTPS)
├── scripts/                        # init-secrets, backup, restore
├── docs/                           # documentation complète
├── docker-compose.yml
├── .env.example
└── Makefile
```

### Conteneurs

| Service | Rôle | Exposition |
|---------|------|------------|
| `db` | PostgreSQL 16, volume persistant `pgdata` | interne uniquement |
| `backend` | gunicorn (3 workers), migrations + comptes initiaux au démarrage | interne :8000 |
| `bank-sync-worker` | synchronisation planifiée du solde Ecobank | interne |
| `frontend` | build React servi par nginx | interne :80 |
| `nginx` | reverse proxy, en-têtes de sécurité, limitation de débit | `8080` (hôte) |
| `db-backup` | `pg_dump` planifié + rotation | volume `./backups` |
| `backend-test` | exécution des tests (profil `test`) | à la demande |

---

## 4. Tests

```bash
# Backend — 132 tests (SQLite par défaut, PostgreSQL via TEST_DATABASE_URL)
cd backend
pip install -r requirements-dev.txt
pytest -q

# ou dans Docker
docker compose --profile test run --rm backend-test

# Frontend — 39 tests
cd frontend
npm install
npm test
npm run build
```

Résultats de la dernière exécution : **132 tests backend** (dont 132 rejoués sur
PostgreSQL 16) et **39 tests frontend**, tous verts. Détails et couverture dans
[docs/TESTS.md](docs/TESTS.md).

---

## 5. Documentation

| Document | Contenu |
|----------|---------|
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Installation pas à pas, Docker, production, HTTPS, sauvegardes |
| [docs/USAGE.md](docs/USAGE.md) | Guide utilisateur (financier & administrateur) |
| [docs/SECURITY.md](docs/SECURITY.md) | Mesures de sécurité, correspondance OWASP, limites |
| [docs/ECOBANK.md](docs/ECOBANK.md) | Intégration API Ecobank, signature, sandbox, dépannage |
| [docs/API.md](docs/API.md) | Référence des endpoints REST |
| [docs/TESTS.md](docs/TESTS.md) | Inventaire des tests et résultats |
| [docs/VALIDATION.md](docs/VALIDATION.md) | Rapport de validation technique |

---

## 6. Commandes utiles

```bash
docker compose ps                     # état des services
docker compose logs -f               # journaux
docker compose exec backend python manage.py shell
docker compose exec backend python manage.py migrate
./scripts/backup.sh                  # sauvegarde PostgreSQL
./scripts/restore.sh backups/<f>.dump
docker compose --profile test run --rm backend-test
```

---

## 7. Règles de conception respectées

- Aucune donnée bancaire inventée : sans identifiants API réels, le solde bancaire est
  indisponible (`—`) et l'écart est marqué **non calculable**. Un mode sandbox de
  démonstration existe, mais il est **explicitement identifié** et exclu du calcul de l'écart.
- Aucune suppression silencieuse : les opérations sont **archivées** (soft delete) et
  chaque création / modification / archivage est journalisée.
- Tous les calculs monétaires sont faits côté serveur en `Decimal`, jamais dans le navigateur.
- Aucun secret dans le frontend : le navigateur ne reçoit ni `Client Secret`, ni clé
  d'abonnement, ni numéro de compte complet.
- Aucune fonctionnalité factice : chaque bouton appelle une API réellement implémentée
  et testée.

---

## 8. Licence & support

Projet livré pour ICHESS Finance. Pour l'intégration bancaire, se référer à la
documentation officielle Ecobank et au support `EcobankSandboxSupport@ecobank.com`.
