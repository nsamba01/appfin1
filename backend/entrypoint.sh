#!/bin/sh
# Container entrypoint: waits for the database, applies controlled migrations,
# collects static files and (once) creates the initial accounts.
set -eu

echo "[entrypoint] Démarrage du backend Django (${DJANGO_SETTINGS_MODULE:-config.settings})"

if [ "${WAIT_FOR_DB:-1}" = "1" ]; then
  python manage.py wait_for_db --timeout "${DB_WAIT_TIMEOUT:-90}"
fi

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "[entrypoint] Application des migrations..."
  python manage.py migrate --noinput
  echo "[entrypoint] Collecte des fichiers statiques..."
  python manage.py collectstatic --noinput
  if [ "${BOOTSTRAP_USERS:-1}" = "1" ]; then
    echo "[entrypoint] Initialisation sécurisée des comptes (mots de passe hachés)..."
    python manage.py bootstrap_users || echo "[entrypoint] ATTENTION: initialisation des comptes incomplète."
  fi
fi

echo "[entrypoint] Exécution : $*"
exec "$@"
