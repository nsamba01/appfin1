#!/usr/bin/env bash
# Sauvegarde manuelle de la base PostgreSQL (format custom, restaurable).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="backups/finbank_${STAMP}.dump"
mkdir -p backups

echo "Sauvegarde vers ${TARGET}…"
docker compose exec -T db sh -c 'pg_dump --format=custom --no-owner --no-privileges -U "$POSTGRES_USER" "$POSTGRES_DB"' > "${TARGET}"

if [[ -s "${TARGET}" ]]; then
  echo "✔ Sauvegarde terminée : ${TARGET} ($(du -h "${TARGET}" | cut -f1))"
else
  rm -f "${TARGET}"
  echo "✖ Échec : fichier de sauvegarde vide." >&2
  exit 1
fi
