#requires -Version 5.1
<#
.SYNOPSIS
    Restauration d'une sauvegarde PostgreSQL (équivalent Windows de scripts/restore.sh).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\restore.ps1 backups\finbank_20261104T120000Z.dump
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$DumpFile
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path $DumpFile) -or (Get-Item $DumpFile).Length -le 0) {
    throw "Fichier introuvable ou vide : $DumpFile"
}

$answer = Read-Host 'Cette opération ÉCRASE la base actuelle. Continuer ? [o/N]'
if ($answer -notmatch '^[oOyY]') { Write-Host 'Annulé.'; exit 0 }

Write-Host 'Arrêt du backend et du worker...'
docker compose stop backend bank-sync-worker | Out-Null

Write-Host "Restauration de $DumpFile ..."
$tmp = '/tmp/restore.dump'
docker compose cp $DumpFile "db:$tmp"
docker compose exec -T db sh -c 'pg_restore --clean --if-exists --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB" /tmp/restore.dump'
$code = $LASTEXITCODE
docker compose exec -T db rm -f $tmp | Out-Null

Write-Host 'Redémarrage des services...'
docker compose start backend bank-sync-worker | Out-Null

if ($code -ne 0) { throw "pg_restore a signalé des erreurs (code $code)." }
Write-Host 'OK : restauration terminée.' -ForegroundColor Green
