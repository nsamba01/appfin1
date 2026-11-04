#!/usr/bin/env bash
# Génère un fichier .env sécurisé (clés aléatoires) et demande les mots de passe
# initiaux sans les afficher. Les valeurs ne sont jamais écrites dans Git.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

if [[ -f "${ENV_FILE}" ]]; then
  read -r -p ".env existe déjà. Le remplacer ? [o/N] " confirm
  if [[ ! "${confirm}" =~ ^[oOyY]$ ]]; then
    echo "Opération annulée."
    exit 0
  fi
  cp "${ENV_FILE}" "${ENV_FILE}.bak.$(date +%Y%m%d%H%M%S)"
  echo "Ancien fichier sauvegardé."
fi

gen_secret() { python3 -c "import secrets; print(secrets.token_urlsafe(64))"; }
gen_password() { python3 -c "import secrets; print(secrets.token_urlsafe(32))"; }
gen_fernet() { python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || openssl rand -base64 32 | tr '+/' '-_'; }

prompt_password() {
  local label="$1" value=""
  while true; do
    read -r -s -p "${label} (laisser vide pour un mot de passe aléatoire) : " value; echo
    if [[ -z "${value}" ]]; then
      value="$(gen_password)"
      echo "  → Mot de passe aléatoire généré (il s'affichera une seule fois ci-dessous)."
      GENERATED+=("${label}: ${value}")
      break
    fi
    read -r -s -p "Confirmer : " confirm; echo
    if [[ "${value}" == "${confirm}" ]]; then break; fi
    echo "  Les valeurs ne correspondent pas, recommencez."
  done
  printf '%s' "${value}"
}

GENERATED=()
echo "=== Initialisation de la configuration ICHESS Finance ==="
echo "Les mots de passe saisis ne sont ni affichés ni journalisés."
echo

ADMIN_PASSWORD="$(prompt_password "Mot de passe initial administrateur (${INITIAL_ADMIN_USERNAME:-Ichessfinadmin})")"
FINANCE_PASSWORD="$(prompt_password "Mot de passe initial financier (${INITIAL_FINANCE_USERNAME:-Emanuel})")"

cat > "${ENV_FILE}" <<ENVEOF
# Généré par scripts/init-secrets.sh le $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# FICHIER SECRET — ne jamais committer.
DJANGO_SECRET_KEY=$(gen_secret)
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=${DJANGO_ALLOWED_HOSTS:-localhost,127.0.0.1}
DJANGO_CSRF_TRUSTED_ORIGINS=${DJANGO_CSRF_TRUSTED_ORIGINS:-http://localhost:8080}
CORS_ALLOWED_ORIGINS=${CORS_ALLOWED_ORIGINS:-http://localhost:8080}
DJANGO_SECURE_COOKIES=${DJANGO_SECURE_COOKIES:-False}
DJANGO_SECURE_SSL_REDIRECT=${DJANGO_SECURE_SSL_REDIRECT:-False}
DJANGO_SECURE_HSTS_SECONDS=${DJANGO_SECURE_HSTS_SECONDS:-0}

POSTGRES_DB=${POSTGRES_DB:-finbank}
POSTGRES_USER=${POSTGRES_USER:-finbank}
POSTGRES_PASSWORD=$(gen_password)

FIELD_ENCRYPTION_KEY=$(gen_fernet)

INITIAL_ADMIN_USERNAME=${INITIAL_ADMIN_USERNAME:-Ichessfinadmin}
INITIAL_ADMIN_PASSWORD=${ADMIN_PASSWORD}
INITIAL_FINANCE_USERNAME=${INITIAL_FINANCE_USERNAME:-Emanuel}
INITIAL_FINANCE_PASSWORD=${FINANCE_PASSWORD}

JWT_ACCESS_MINUTES=15
JWT_REFRESH_MINUTES=480
SESSION_COOKIE_AGE=3600
MAX_LOGIN_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=15
THROTTLE_LOGIN=20/min

APP_COMPANY_NAME=${APP_COMPANY_NAME:-ICHESS Finance}
APP_CURRENCY=${APP_CURRENCY:-USD}
TIME_ZONE=${TIME_ZONE:-Africa/Kinshasa}
LANGUAGE_CODE=fr-fr
DJANGO_LOG_LEVEL=INFO

ECOBANK_BASE_URL=${ECOBANK_BASE_URL:-https://apimuat-gateway.ecobank.com}
ECOBANK_AUTH_PATH=/corp-auth/api/v2/integration/auth/app/token
ECOBANK_BALANCE_PATH=/corp-account-inquiry/api/v2/integration/account/inquiry/balance
ECOBANK_HTTP_TIMEOUT=30
BANK_SYNC_INTERVAL_MINUTES=30
BANK_SYNC_WORKER_ENABLED=True

NGINX_HTTP_PORT=${NGINX_HTTP_PORT:-8080}
BACKUP_INTERVAL_SECONDS=86400
BACKUP_RETENTION_DAYS=7
ENVEOF

chmod 600 "${ENV_FILE}"
echo
echo "✔ Fichier .env créé avec des secrets aléatoires (droits 600)."
if [[ ${#GENERATED[@]} -gt 0 ]]; then
  echo
  echo "⚠ Mots de passe générés automatiquement — notez-les maintenant, ils ne seront plus affichés :"
  printf '   %s\n' "${GENERATED[@]}"
fi
echo
echo "Étape suivante : docker compose build && docker compose up -d"
