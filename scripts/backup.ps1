#requires -Version 5.1
<#
.SYNOPSIS
    Sauvegarde PostgreSQL (équivalent Windows de scripts/backup.sh).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

New-Item -ItemType Directory -Force -Path 'backups' | Out-Null
$stamp  = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$target = Join-Path 'backups' "finbank_$stamp.dump"
$tmp    = '/tmp/finbank_backup.dump'

Write-Host "Sauvegarde vers $target ..."

# Vidage dans le conteneur puis copie binaire (aucune corruption d'encodage).
docker compose exec -T db sh -c 'pg_dump --format=custom --no-owner --no-privileges -U "$POSTGRES_USER" "$POSTGRES_DB" -f /tmp/finbank_backup.dump'
if ($LASTEXITCODE -ne 0) { throw 'pg_dump a échoué.' }

docker compose cp "db:$tmp" $target
if ($LASTEXITCODE -ne 0) { throw 'Copie de la sauvegarde impossible.' }
docker compose exec -T db rm -f $tmp | Out-Null

$size = (Get-Item $target).Length
if ($size -le 0) {
    Remove-Item $target -Force
    throw 'Échec : fichier de sauvegarde vide.'
}
Write-Host ("OK : sauvegarde terminée ({0:N0} octets)." -f $size) -ForegroundColor Green
