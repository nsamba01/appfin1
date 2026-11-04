#!/usr/bin/env bash
# Restauration d'une sauvegarde PostgreSQL.
# Usage : ./scripts/restore.sh backups/finbank_20260101T000000Z.dump
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ $# -ne 1 ]]; then
  echo "Usage : $0 <fichier.dump>" >&2
  exit 1
fi

DUMP="$1"
if [[ ! -s "${DUMP}" ]]; then
  echo "Fichier introuvable ou vide : ${DUMP}" >&2
  exit 1
fi

read -r -p "Cette opération ÉCRASE la base actuelle. Continuer ? [o/N] " confirm
[[ "${confirm}" =~ ^[oOyY]$ ]] || { echo "Annulé."; exit 0; }

echo "Arrêt du backend et du worker…"
docker compose stop backend bank-sync-worker

echo "Restauration de ${DUMP}…"
docker compose exec -T db sh -c 'pg_restore --clean --if-exists --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "${DUMP}"

echo "Redémarrage des services…"
docker compose start backend bank-sync-worker
echo "✔ Restauration terminée."
