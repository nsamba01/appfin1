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

## 3. Commandes à exécuter sur un hôte Docker

```bash
cp .env.example .env && ./scripts/init-secrets.sh
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f
docker compose --profile test run --rm backend-test
```

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
