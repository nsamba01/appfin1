# Tests et résultats

Tous les tests ont été **réellement exécutés**. Aucun résultat de ce document n'est
déclaratif.

---

## 1. Backend — 132 tests (pytest-django)

```bash
cd backend
pip install -r requirements-dev.txt
pytest -q
# ou sur PostgreSQL :
TEST_DATABASE_URL="postgresql://user:pass@host:5432/db" pytest -q
# ou dans Docker :
docker compose --profile test run --rm backend-test
```

### Répartition

| Fichier | Tests | Périmètre |
|---------|------:|-----------|
| `tests/test_auth.py` | 20 | login, verrouillage, refresh, logout, changement de mot de passe |
| `tests/test_users_admin.py` | 19 | CRUD utilisateurs, rôles, paramètres, isolation des rôles |
| `tests/test_finance.py` | 34 | opérations, calculs `Decimal`, filtres, exports, historique, audit |
| `tests/test_banking.py` | 26 | configuration Ecobank, signature, test de connexion, sync, secrets |
| `tests/test_dashboard.py` | 13 | agrégats, comparaison, écart, séries, non rapprochés |
| `tests/test_security.py` | 20 | en-têtes, RBAC, injection, XSS, fuites de secrets, logs |
| **Total** | **132** | |

### Résultats de la dernière exécution

```text
132 passed in 32.26s
```

Exécution sur **PostgreSQL 16.2** (parité avec la production) via `TEST_DATABASE_URL`,
et sur SQLite en intégration continue locale.

### Ce que couvrent les tests critiques

- Mots de passe : `argon2` dans le hash, jamais renvoyés, jamais journalisés
  (`test_password_hash_is_argon2`, `test_login_never_returns_password_fields`,
  `test_logging_filter_redacts_secrets`, `test_settings_do_not_embed_initial_passwords`).
- Changement forcé au premier login : accès métier refusé jusqu'à la modification.
- Verrouillage après 5 échecs, déverrouillage administrateur, throttling.
- Isolation FINANCE/ADMIN sur **tous** les endpoints administratifs et bancaires.
- Signature Ecobank : vecteurs SHA-512 à valeur connue, ordre des champs,
  renouvellement du jeton sur `403`, erreurs `responseCode` non `000`, **aucun solde
  fabriqué** en cas d'échec.
- Secrets bancaires : chiffrés en base, absents des réponses API et du status financier.
- Écart : `UNAVAILABLE` quand le solde bancaire est absent ou sandbox.
- Opérations : calcul exact des totaux (`5000 − 1500 = 3500`), montant nul/négatif refusé,
  archivage tracé, historique conservé.
- Sécurité : en-têtes (CSP, nosniff, X-Frame-Options…), injection SQL inopérante,
  JSON malformé → 400, CORS restreint.

---

## 2. Frontend — 39 tests (Vitest + Testing Library)

```bash
cd frontend
npm install
npm test               # vitest run
npx tsc --noEmit       # 0 erreur
npm run build          # build de production
```

| Fichier | Tests | Périmètre |
|---------|------:|-----------|
| `src/App.test.tsx` | 9 | routage par rôle, redirection, garde de changement de mot de passe |
| `src/pages/Login.test.tsx` | 5 | validation, appel API, erreurs, verrouillage |
| `src/pages/Operations.test.tsx` | 7 | liste, filtres, validation, création, erreur API, archivage, état vide |
| `src/pages/Bank.test.tsx` | 3 | compte masqué, avertissement sandbox, non configuré |
| `src/services/api.test.ts` | 6 | intercepteurs, rafraîchissement, redirections 401/403 |
| `src/utils/format.test.ts` | 9 | formatage monétaire, dates, pourcentages, masquage |
| **Total** | **39** | |

```text
Test Files  6 passed (6)
     Tests  39 passed (39)
```

### Build de production vérifié

```text
dist/assets/react-*.js    164 kB
dist/assets/charts-*.js   407 kB
dist/assets/http-*.js      35 kB
dist/assets/index-*.js    142 kB
✓ built
```

`tsc --noEmit` : **0 erreur** (mode strict).

---

## 3. Tests de bout en bout (application réelle)

Exécutés contre la pile réellement démarrée : PostgreSQL 16.2 + gunicorn (3 workers) +
build React, via un client HTTP scripté.

| # | Scénario | Résultat |
|---|----------|----------|
| 1 | Login financier initial | `200`, `must_change_password: true` |
| 2 | Accès métier avant changement de mot de passe | `403 password_change_required` |
| 3 | Changement de mot de passe + reconnexion | `200` |
| 4 | Création de 3 opérations | `201` ×3 |
| 5 | Balances serveur | entrées `5000.00`, sorties `1500.00`, solde `3500.00`, 3 opérations |
| 6 | Dashboard | solde `3500.00`, comparaison `UNAVAILABLE`, banque `NOT_CONFIGURED` |
| 7 | RBAC financier | config bancaire `403`, utilisateurs `403`, statut banque `200` |
| 8 | Exports | xlsx `200` + MIME Excel, pdf `200` + `%PDF` |
| 9 | Admin : changement de mot de passe, création d'utilisateur | `200`, `201` |
| 10 | Admin : utilisateurs, audit, connexions | `200`, `200`, `200` |
| 11 | Sync sans configuration | `success: false` + « synchronisation bancaire désactivée » — **aucun solde inventé** |
| 12 | Configuration bancaire (admin) | `200`, corps **sans** `secret_key` |
| 13 | Force brute | `401` ×5 puis `423 Compte temporairement verrouillé` |
| 14 | En-têtes de sécurité | CSP, `X-Frame-Options: DENY`, `nosniff`, Referrer-Policy, COOP/CORP |
| 15 | Cookie de refresh | présent en `HttpOnly`, rotation fonctionnelle |

---

## 4. Vérifications de configuration

| Vérification | Résultat |
|--------------|----------|
| `manage.py check` | aucune erreur |
| `manage.py check --deploy` | seuls les avertissements attendus en développement (`DJANGO_SECRET_KEY` de dev) ; la configuration de production les traite |
| `manage.py migrate` (PostgreSQL 16) | OK, aucune migration manquante |
| `manage.py makemigrations --check --dry-run` | aucune migration en attente |
| `manage.py collectstatic` | 163 fichiers |
| `manage.py bootstrap_users` | « Comptes créés : Ichessfinadmin (ADMIN), Emanuel (FINANCE) » |
| `docker compose config` | **non exécutable dans l'environnement de construction** (Docker absent) ; structure validée par analyse YAML et par déploiement natif équivalent — voir [VALIDATION.md](VALIDATION.md) |

---

## 5. Rejouer l'ensemble

```bash
# Backend
cd backend && pytest -q

# Frontend
cd frontend && npx tsc --noEmit && npm test && npm run build

# Tout, dans Docker
docker compose --profile test run --rm backend-test
```
