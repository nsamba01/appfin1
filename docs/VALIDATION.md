# Rapport de validation

Ce document etat exactement ce qui a été exécuté, avec quels résultats, et ce qui n'a
pas pu l'être dans l'environnement de construction — sans extrapolation.

Date : 4 novembre 2026.

---

## 1. Environnement de construction

| Élément | Disponible |
|---------|-----------|
| Python 3.11 + virtualenv | ✅ |
| Node.js 20 / npm | ✅ |
| PostgreSQL 16.2 (accord local, `pgserver`) | ✅ |
| gunicorn | ✅ |
| Docker / Docker Compose | ❌ **absent du bac à sable** |

Conséquence : les images n'ont pas pu être construites ici. La pile a donc été exécutée
**nativement avec les mêmes composants** (PostgreSQL 16, gunicorn, build React de
production servie par le serveur de développement Vite en amont du proxy), et les
fichiers Docker ont été validés statiquement (analyse YAML, cohérence des variables,
chemins de volumes, healthchecks, dépendances). Les commandes à exécuter sur un hôte
Docker sont fournies ci-dessous et dans [INSTALLATION.md](INSTALLATION.md).

---

## 2. Résultats exécutés

### 2.1 Backend

```text
$ pytest -q                       → 132 passed  (SQLite)
$ TEST_DATABASE_URL=… pytest -q   → 132 passed in 32.26s  (PostgreSQL 16.2)
$ manage.py check                 → System check identified no issues
$ manage.py migrate               → OK (PostgreSQL 16.2)
$ manage.py makemigrations --check --dry-run → No changes detected
$ manage.py collectstatic         → 163 fichiers
$ manage.py bootstrap_users       → Comptes créés : Ichessfinadmin (ADMIN), Emanuel (FINANCE)
$ manage.py check --deploy        → uniquement les avertissements du secret de développement
```

`check --deploy` signale W004/W008/W009/W012/W016/W018 uniquement parce que
l'environnement de test utilise une clé de développement ; `config/settings.py` active
HSTS, redirection SSL, cookies sécurisés, `DEBUG=False` et `ALLOWED_HOSTS` explicite dès
que `DJANGO_DEBUG=False` et que les variables de production sont fournies (voir `.env.example`).

### 2.2 Frontend

```text
$ npx tsc --noEmit   → 0 erreur
$ npm run build      → succès (react 164 kB, charts 407 kB, http 35 kB, index 142 kB)
$ npx vitest run     → 6 fichiers, 39 tests passés
```

### 2.3 Application complète (bout en bout)

Voir le tableau détaillé dans [TESTS.md §3](TESTS.md). Points saillants :

- RBAC vérifié en conditions réelles : finance → config bancaire `403`, utilisateurs `403` ;
- verrouillage après 5 échecs → `423` ;
- exports xlsx/pdf réellement téléchargés (signatures de fichier vérifiées) ;
- synchronisation sans configuration → échec explicite, **aucun solde inventé** ;
- réponse de configuration bancaire sans `secret_key` ;
- en-têtes de sécurité complets sur l'API et le SPA ;
- base remise à l'état initial (2 comptes, 0 opération, changement de mot de passe requis).

### 2.4 Validation statique de Docker

| Contrôle | Méthode | Résultat |
|----------|---------|----------|
| Syntaxe et structure `docker-compose.yml` | analyse PyYAML, schéma interne | valide |
| Cohérence des variables `.env` ↔ services | revue croisée | toutes résolues, valeurs par défaut présentes |
| Volumes persistants | `pgdata`, `staticfiles`, `media`, `nginx_logs` | déclarés |
| Publication des ports | seul `nginx` publie un port | `db` non exposé |
| Healthchecks | `db` (`pg_isready`), `backend` (`/healthz`) | présents |
| Ordre de démarrage | `depends_on: service_healthy` | correct |
| Dockerfiles | base officielle épinglée, utilisateur non-root, multi-stage frontend | conformes |
| `.dockerignore` | exclut `node_modules`, `.venv`, `__pycache__`, `.env` | présents |

### 2.5 Test du `docker-compose.yml` sans démon Docker

Le binaire Docker n'existe pas dans cet environnement. Le fichier a donc été vérifié par
`scripts/validate-compose.py`, qui reproduit l'interpolation Compose (`${VAR}`,
`${VAR:-défaut}`, `${VAR:?message}`) et contrôle la structure complète :

```text
$ python scripts/validate-compose.py
66/66 vérifications OK
docker-compose.yml : structure valide (équivalent de `docker compose config`)
```

Points contrôlés : 7 services, images et contextes de build, Dockerfiles présents,
réseaux déclarés, volumes nommés et chemins montés existants, `depends_on` +
conditions `service_healthy` réellement adossées à un healthcheck, un seul port publié
(nginx) et PostgreSQL jamais exposé, cohérence des `upstream` nginx avec les noms de
services, `/healthz` exposé, absence de secret littéral, scripts et commandes de gestion
présents. Le validateur vérifie aussi que **sans `.env`** l'erreur affichée est bien le
message actionnable (`... creez .env avec scripts/init-secrets.bat`).

### 2.6 Démarrage réel du conteneur backend (sans Docker)

Le script que le conteneur exécute (`backend/entrypoint.sh`) a été lancé tel quel, avec
les variables d'environnement résolues par Compose, sur une base PostgreSQL **vide** :

```text
[entrypoint] Démarrage du backend Django (config.settings)
Base de données disponible.
[entrypoint] Application des migrations...        → 38 migrations appliquées
[entrypoint] Collecte des fichiers statiques...   → 163 fichiers
[entrypoint] Initialisation sécurisée des comptes → Comptes créés : Ichessfinadmin (ADMIN), Emanuel (FINANCE)
[entrypoint] Exécution : gunicorn config.wsgi:application ...
```

Puis, contre cette instance fraîchement initialisée :

| Vérification | Résultat |
|--------------|----------|
| `/healthz` | `{"status": "ok"}` |
| Connexion initiale `Emanuel` | `200`, `must_change_password: true` |
| Accès aux opérations avant changement | `403` |
| Changement de mot de passe | `200` |
| Création de 3 opérations | `201` ×3 |
| Balances calculées | entrées `5000.00`, sorties `1750.00`, solde `3250.00` |
| Dashboard | `financial.balance 3250.00`, écart `null`, comparaison `UNAVAILABLE` |
| Config bancaire (financier) | `403` |
| Export xlsx | `200` |

C'est exactement la séquence que produit `docker compose up -d` pour le service
`backend` ; seule la couche de conteneurisation elle-même n'a pas pu être exercée ici.

## 3. Commandes à exécuter sur un hôte Docker

```bash
./scripts/init-secrets.sh        # Windows : scripts\init-secrets.bat
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f
docker compose --profile test run --rm backend-test
```

Sous Windows, `scripts\start-windows.bat` enchaîne la création de `.env`, le build et le
démarrage. Les scripts PowerShell fournis ont été validés syntaxiquement (analyse par
grammaire PowerShell) mais n'ont pas pu être exécutés ici : l'environnement de
construction est Linux sans PowerShell — à rejouer sur le poste Windows cible.

Attendu : 5 services `running` (dont `db` et `backend` `healthy`), application sur
`http://localhost:8080`, 132 tests verts dans le conteneur de test.

---

## 4. Limites assumées

1. **Pas de `docker compose up` dans cet environnement** : la construction des images est
   la seule étape non exécutée ici. Les binaires et versions qu'elles embarquent ont été
   testés nativement.
2. **Pas d'accès aux vraies API Ecobank** : aucun identifiant n'a été fourni. L'écart
   financier/bancaire est donc `UNAVAILABLE` et aucun solde bancaire n'est affiché — c'est
   le comportement attendu et testé. La signature est implémentée selon le protocole
   documenté, à confirmer avec vos identifiants via *Tester la connexion*.
3. **Mots de passe initiaux** : fournis via `.env` (exclu de Git) et non dans le code. Ils
   doivent être changés à la première connexion (contrôle serveur, pas seulement UI).
