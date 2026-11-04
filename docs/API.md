# Référence de l'API REST

Base : `/api` — JSON uniquement. Authentification : `Authorization: Bearer <access_token>`.
Les erreurs sont normalisées : `{"detail": "..."}` (+ `code` pour les cas métiers).

---

## 1. Authentification

| Méthode | URL | Accès | Description |
|---------|-----|-------|-------------|
| POST | `/auth/login/` | public | Connexion. Retourne `access` + `user`, pose le cookie de refresh. |
| POST | `/auth/refresh/` | cookie | Rotation du refresh, nouveau `access`. |
| POST | `/auth/logout/` | public | Blacklist du refresh, suppression du cookie. |
| GET | `/auth/me/` | authentifié | Profil, permissions, paramètres d'application. |
| POST | `/auth/change-password/` | authentifié | Changement de mot de passe (révoque les sessions). |
| GET | `/auth/roles/` | authentifié | Les deux rôles disponibles. |

**Login**

```json
{ "username": "Emanuel", "password": "..." }
```

Réponses : `200` succès · `400` champs manquants · `401` identifiants invalides
(`attempts_remaining`) · `403` compte désactivé · `423` compte verrouillé
(`code: account_locked`) · `429` throttling.

**Changement de mot de passe**

```json
{ "current_password": "...", "new_password": "...", "confirm_password": "..." }
```

Tant que `must_change_password` est vrai, toutes les routes métier répondent
`403 {"code": "password_change_required"}` (sauf `me`, `change-password`, `logout`, `refresh`).

---

## 2. Opérations financières

| Méthode | URL | Accès |
|---------|-----|-------|
| GET | `/finance/operations/` | FINANCE + ADMIN |
| POST | `/finance/operations/` | FINANCE + ADMIN |
| GET | `/finance/operations/{id}/` | FINANCE + ADMIN |
| PATCH/PUT | `/finance/operations/{id}/` | FINANCE + ADMIN (selon règles) |
| DELETE | `/finance/operations/{id}/` | FINANCE + ADMIN (archivage) |
| GET | `/finance/operations/{id}/history/` | FINANCE + ADMIN |
| GET | `/finance/operations/export/?file_format=xlsx\|pdf` | FINANCE + ADMIN |
| GET | `/finance/balances/` | FINANCE + ADMIN |
| GET | `/finance/history/` | FINANCE + ADMIN |

Filtres de liste : `date_from`, `date_to`, `operation_type` (`ENTRY`/`EXIT`), `search`
(libellé, référence, observation), `page`, `page_size` (max 200), `ordering`,
`include_deleted=true` (ADMIN uniquement).

**Création**

```json
{
  "date": "2026-11-01",
  "label": "Financement reçu",
  "amount": "5000.00",
  "operation_type": "ENTRY",
  "reference": "FIN-001",
  "observation": "Apport initial"
}
```

Réponse `201` : objet complet avec `signed_amount`, `operation_type_label`,
`created_by_username`.

**Balances**

```json
{
  "currency": "USD",
  "totals": { "total_entries": "5000.00", "total_exits": "1500.00",
              "balance": "3500.00", "operation_count": 3 },
  "financial_balance": "3500.00",
  "monthly_series": [{ "period": "2026-11", "entries": "5000.00",
                       "exits": "1500.00", "balance": "3500.00" }],
  "daily_series": [...]
}
```

Export : `Content-Disposition: attachment`, `.xlsx` ou `.pdf`, limité aux 5 000
premières lignes filtrées ; chaque export est audité.

---

## 3. Tableau de bord

| Méthode | URL | Description |
|---------|-----|-------------|
| GET | `/dashboard/summary/` | Cartes, comparaison, écart, alertes, non rapprochés |
| GET | `/dashboard/charts/` | Séries mensuelles, historique bancaire, écarts, comparaison |
| GET | `/dashboard/comparison/` | Tableau indicateurs financier/bancaire |

Paramètres optionnels : `date_from`, `date_to` (`YYYY-MM-DD`).

`comparison.status` ∈ `EQUAL` · `FINANCIAL_HIGHER` · `BANK_HIGHER` · `UNAVAILABLE`.
`bank.is_sandbox = true` ⇒ l'écart est `UNAVAILABLE` (jamais calculé sur des données simulées).

---

## 4. Banque

| Méthode | URL | Accès |
|---------|-----|-------|
| GET | `/banking/status/` | FINANCE + ADMIN |
| GET | `/banking/history/?days=90` | FINANCE + ADMIN |
| GET | `/banking/config/` | ADMIN |
| PATCH/PUT | `/banking/config/` | ADMIN |
| POST | `/banking/config/test/` | ADMIN |
| POST | `/banking/config/clear-secrets/` | ADMIN |
| POST | `/banking/sync/` | ADMIN |
| GET | `/banking/logs/` | ADMIN |

`/banking/status/` ne contient **aucun secret** : compte masqué, soldes, état de
connexion, dates, messages. `secret_key`, `subscription_key` et `account_no` sont
*write-only* ; omettre un champ secret conserve la valeur enregistrée.

---

## 5. Administration

| Méthode | URL | Description |
|---------|-----|-------------|
| GET/POST | `/admin/users/` | Liste / création |
| GET/PATCH/PUT/DELETE | `/admin/users/{id}/` | Détail / modification / désactivation |
| POST | `/admin/users/{id}/password/` | Réinitialisation |
| POST | `/admin/users/{id}/toggle-active/` | Activer / désactiver |
| POST | `/admin/users/{id}/unlock/` | Déverrouiller |
| GET/PATCH | `/admin/settings/` | Paramètres généraux |
| GET | `/admin/audit-logs/` | Journal d'audit (filtres `action`, `actor`, `search`, dates) |
| GET | `/admin/login-logs/` | Tentatives de connexion (`successful`, `username`, dates) |

**Création d'utilisateur**

```json
{
  "username": "nouvelle.finance",
  "full_name": "Nouvelle Financière",
  "email": "nf@example.com",
  "role": "FINANCE",
  "password": "SolideSecret#2026",
  "force_password_change": true
}
```

Le mot de passe n'est **jamais** renvoyé. `DELETE` désactive le compte (aucune
suppression physique).

**Paramètres généraux**

```json
{
  "company_name": "ICHESS Finance",
  "currency": "USD",
  "timezone_label": "Africa/Kinshasa",
  "allow_finance_edit_operations": true,
  "allow_finance_delete_operations": true,
  "operation_edit_window_days": 0,
  "bank_sync_interval_minutes": 30
}
```

---

## 6. Divers

| Méthode | URL | Description |
|---------|-----|-------------|
| GET | `/healthz` | Sonde de santé (hors `/api`) |
| GET | `/admin/` | Administration technique Django (optionnelle) |

Pagination : `{"count": n, "next": url|null, "previous": url|null, "results": [...]}`.

Codes fréquents : `400` validation · `401` non authentifié / jeton expiré ·
`403` rôle insuffisant ou changement de mot de passe requis · `404` introuvable ·
`423` compte verrouillé · `429` trop de requêtes · `500` erreur interne (message générique).
