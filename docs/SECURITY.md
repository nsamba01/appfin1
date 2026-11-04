# Sécurité

Priorité absolue du projet. Ce document décrit les mesures **effectivement implémentées**
et testées, leur correspondance avec l'OWASP Top 10, et les limites connues.

---

## 1. Mots de passe

| Mesure | Implémentation |
|--------|----------------|
| Hachage | **Argon2id** (`Argon2PasswordHasher` en premier, PBKDF2 en repli) |
| Stockage | uniquement l'empreinte, colonne `password` — jamais de clair |
| Transmission | HTTPS (prod) ; jamais renvoyé par l'API ni écrit dans les logs |
| Initialisation | `bootstrap_users` lit les variables d'environnement, hache, puis n'affiche jamais le mot de passe |
| Premier login | `must_change_password=True` → API bloquée (403) hors *me* / *change-password* / *logout* |
| Réinitialisation | hachage + révocation de toutes les sessions + changement forcé |
| Politique | 10 caractères min., similarité, mots de passe communs, tout numérique |
| Journalisation | filtre `RedactSecretsFilter` sur tous les handlers (password, token, secret, bearer…) |

Vérifications automatisées : `test_password_hash_is_argon2`,
`test_login_never_returns_password_fields`, `test_audit_metadata_never_contains_passwords`,
`test_logging_filter_redacts_secrets`, `test_settings_do_not_embed_initial_passwords`,
`test_initial_password_flow_creates_hashed_users`.

> **Aucun mot de passe n'est présent dans le dépôt Git.** `.env` est ignoré ;
> `.env.example` ne contient que des valeurs vides ; l'archive livrée exclut `.env`.

---

## 2. Authentification & sessions

- **JWT** signés HS256, durée d'accès **15 minutes**.
- **Refresh token** (8 h) stocké dans un cookie `HttpOnly`, `SameSite=Lax`, `Secure`
  en production, limité au chemin `/api/auth/` → inaccessible au JavaScript.
- **Jeton d'accès conservé en mémoire** uniquement (jamais `localStorage`/`sessionStorage`).
- **Rotation** du refresh à chaque rafraîchissement + **blacklist** SimpleJWT.
- **Révocation immédiate** : un changement / reset de mot de passe invalide les jetons
  d'accès existants via le claim `pwd_ts` (comparé à `password_changed_at`).
- **Déconnexion** : blacklist du refresh + suppression du cookie.
- Table `UserSession` : traçabilité IP / user-agent / expiration / révocation.

---

## 3. Autorisations (RBAC)

Deux rôles stricts : `FINANCE` et `ADMIN`, contrôlés **côté serveur** par
`RolePermission` (et non par l'interface).

| Endpoint | FINANCE | ADMIN |
|----------|:-------:|:-----:|
| Dashboard, soldes, graphiques | ✅ | ✅ |
| Opérations (CRUD) | ✅ | ✅ |
| Statut / historique bancaire | ✅ (lecture) | ✅ |
| Configuration Ecobank | ❌ 403 | ✅ |
| Synchronisation manuelle, test de connexion | ❌ 403 | ✅ |
| Utilisateurs, audit, connexions, paramètres | ❌ 403 | ✅ |

Chaque refus est vérifié par des tests (`test_finance_cannot_*`, `TestRoleIsolation`,
`TestAccessControl`). Le rôle ne peut pas être modifié via un payload d'opération.

---

## 4. Protection contre la force brute

- Compteur `failed_login_attempts` + `locked_until` par compte.
- **5 échecs** → verrouillage **15 minutes** (configurable).
- Message générique pour les identifiants inconnus (pas d'énumération de comptes).
- **Throttling DRF** : 20 connexions/min par IP, 6 synchronisations bancaires/min.
- **Nginx** : `limit_req` 20 req/min sur `/api/auth/login/`, 30 req/s sur `/api/`.
- Chaque tentative est enregistrée (`LoginAttempt`) avec IP, user-agent et motif.
- Déverrouillage possible par un administrateur.

---

## 5. Validation & injections

- ORM Django exclusivement → requêtes **paramétrées**, aucune concaténation SQL.
- Serializers DRF stricts : types, longueurs, plages, `DecimalField(max_digits=18,
  decimal_places=2)`, montant `> 0`, type d'opération énuméré, dates ISO.
- Contrainte base `CHECK (amount > 0)` en défense supplémentaire.
- Test d'injection SQL (`'; DROP TABLE ...`) : la requête reste sans effet.
- Corps JSON malformé → 400, jamais 500.

---

## 6. XSS / CSRF / en-têtes

- React échappe par défaut ; l'API ne renvoie que du JSON (`Content-Type` vérifié).
- **CSP** restrictive : `default-src 'self'`, `frame-ancestors 'none'`,
  `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`.
  Aucune ressource externe (polices incluses dans la pile système).
- `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`,
  `Permissions-Policy`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`.
- `Cache-Control: no-store` sur toutes les réponses `/api/`.
- **CSRF** : middleware Django actif (formulaire admin), cookies `SameSite`,
  `CSRF_TRUSTED_ORIGINS` explicite ; le refresh token n'est pas utilisable en
  lecture libre par le JavaScript (HttpOnly) et ne permet pas d'action métier.
- **CORS** : liste blanche d'origines, `credentials` autorisés, aucune origine `*`.
- HSTS / redirection HTTPS activables par variables d'environnement.

---

## 7. Données bancaires

- `Client Secret`, clé d'abonnement et numéro de compte **chiffrés au repos** (Fernet,
  clé dédiée `FIELD_ENCRYPTION_KEY`).
- Ces secrets sont **write-only** dans l'API : jamais renvoyés (`test_admin_updates_config_and_secrets_are_never_returned`).
- Numéro de compte **masqué** partout (4 derniers chiffres).
- Le frontend ne connaît aucun secret ; tous les appels Ecobank partent du backend.
- Cache de jeton chiffré, par service et par identité.
- Chaque consultation des données bancaires est auditée (`BANK_DATA_ACCESSED`).
- Seul l'administrateur peut modifier la configuration ou supprimer les identifiants.

---

## 8. Base de données & infrastructure

- PostgreSQL **sans port publié** : joignable uniquement sur le réseau Docker interne.
- Utilisateur applicatif dédié (`POSTGRES_USER`), jamais `postgres` en production.
- Volumes persistants, healthchecks, `restart: unless-stopped`.
- Sauvegardes automatiques `pg_dump` (rotation 7 jours) + script de restauration.
- Conteneurs backend exécutés en utilisateur non privilégié (`app`).
- Reverse proxy Nginx : seule surface exposée ; `server_tokens off`.
- Journaux applicatifs sur stdout (collectés par Docker), sans secrets.

---

## 9. Journalisation & audit

Évènements tracés : connexions (succès/échec), déconnexion, changements de mot de passe,
création/modification/désactivation d'utilisateurs, création/modification/archivage
d'opérations, exports, configuration bancaire, tests de connexion, synchronisations,
accès aux données bancaires, paramètres généraux.

Chaque entrée contient acteur, action, entité, identifiant, description, métadonnées,
IP, user-agent et horodatage. L'audit n'est ni modifiable ni supprimable depuis
l'application.

---

## 10. Correspondance OWASP Top 10 (2021)

| Risque | Traitement |
|--------|------------|
| A01 Broken Access Control | RBAC serveur, permissions par vue, tests de non-régression |
| A02 Cryptographic Failures | Argon2id, HTTPS, Fernet au repos, cookies Secure/HttpOnly |
| A03 Injection | ORM, serializers, contraintes base, test d'injection |
| A04 Insecure Design | séparation des rôles, principe du moindre privilège, écarts bancaires explicites |
| A05 Security Misconfiguration | `.env`, DEBUG=False en prod, en-têtes, CORS/CSP stricts, conteneur non-root |
| A06 Vulnerable Components | versions épinglées (Django 5.1.6, DRF 3.15.2, React 18.3.1…) |
| A07 Auth Failures | verrouillage, throttling, rotation/révocation, politique de mot de passe |
| A08 Integrity Failures | migrations contrôlées, images officielles, journal d'audit immuable |
| A09 Logging Failures | audit complet, redaction des secrets, aucun mot de passe journalisé |
| A10 SSRF | une seule destination sortante (API Ecobank), URL HTTPS validée et administrée |

---

## 11. Limites connues et recommandations

1. **Rotation des secrets** : changer `FIELD_ENCRYPTION_KEY` nécessite de ressaisir les
   identifiants Ecobank. Prévoyez une procédure de rotation documentée.
2. **2FA** : non implémentée (hors périmètre). Recommandée pour les comptes
   administrateurs en production.
3. **Verrouillage par IP** : uniquement par compte ; un attaquant peut verrouiller un
   compte connu (déni de service limité, déverrouillable par l'admin). Le throttling IP
   atténue ce risque.
4. **Sauvegardes** : le service `db-backup` écrit sur l'hôte ; répliquez ce volume vers
   un stockage externe chiffré.
5. **Journalisation centralisée** : brancher un collecteur (Loki/ELK) pour la rétention
   long terme et l'alerting.
6. **Tests de pénétration** : un audit externe reste recommandé avant mise en production
   bancaire, ainsi qu'une revue de la signature Ecobank avec votre chargé de compte.
