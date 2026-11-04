#requires -Version 5.1
<#
.SYNOPSIS
    Génère le fichier .env de ICHESS Finance (équivalent Windows de init-secrets.sh).

.DESCRIPTION
    - génère DJANGO_SECRET_KEY, le mot de passe PostgreSQL et FIELD_ENCRYPTION_KEY ;
    - demande SANS AFFICHAGE les mots de passe initiaux (laisser vide = aléatoire) ;
    - écrit .env en UTF-8 sans BOM avec des fins de ligne Unix (LF) ;
    - restreint les droits du fichier au compte courant.

    Aucun mot de passe n'est écrit ailleurs que dans .env (exclu de Git).
    Aucune dépendance : Windows PowerShell 5.1 suffit (pas besoin de Python).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\init-secrets.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\init-secrets.ps1 -Force
#>
[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$root    = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root '.env'

# --------------------------------------------------------------------------
# Générateurs cryptographiques
# --------------------------------------------------------------------------
function New-RandomBytes {
    param([int]$Length)
    $bytes = [byte[]]::new($Length)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    # La virgule évite l'éclatement du tableau par le pipeline PowerShell.
    return ,$bytes
}

function Get-RandomInt {
    param([int]$Max)
    $bytes = New-RandomBytes 4
    $value = [BitConverter]::ToUInt32($bytes, 0)
    return [int]($value % [uint32]$Max)
}

function New-UrlSafeToken {
    param([int]$ByteLength)
    $b64 = [Convert]::ToBase64String((New-RandomBytes $ByteLength))
    return $b64.TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function New-FernetKey {
    # Clé Fernet = 32 octets en base64 URL-safe, padding conservé (44 caractères).
    $b64 = [Convert]::ToBase64String((New-RandomBytes 32))
    return $b64.Replace('+', '-').Replace('/', '_')
}

function New-RandomPassword {
    $upper   = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
    $lower   = 'abcdefghijkmnpqrstuvwxyz'
    $digits  = '23456789'
    $symbols = '!@#%*-_'
    $all     = "$upper$lower$digits$symbols"

    $chars = New-Object System.Collections.ArrayList
    [void]$chars.Add($upper[(Get-RandomInt $upper.Length)])
    [void]$chars.Add($lower[(Get-RandomInt $lower.Length)])
    [void]$chars.Add($digits[(Get-RandomInt $digits.Length)])
    [void]$chars.Add($symbols[(Get-RandomInt $symbols.Length)])
    for ($i = 0; $i -lt 16; $i++) {
        [void]$chars.Add($all[(Get-RandomInt $all.Length)])
    }
    # Mélange de Fisher-Yates.
    for ($i = $chars.Count - 1; $i -gt 0; $i--) {
        $j = Get-RandomInt ($i + 1)
        $tmp = $chars[$i]
        $chars[$i] = $chars[$j]
        $chars[$j] = $tmp
    }
    return -join $chars
}

function Read-Secret {
    param([string]$Prompt)
    $secure = Read-Host -Prompt $Prompt -AsSecureString
    if ($null -eq $secure -or $secure.Length -eq 0) { return '' }
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

# Caractères sûrs pour un fichier .env : ni espace, ni guillemet, ni $, ni \.
$PasswordPattern = '^[A-Za-z0-9!@#%*\-_+.:?=/]{10,}$'

function Read-InitialPassword {
    param([string]$Label)

    while ($true) {
        $pwd = Read-Secret "Mot de passe initial $Label - laisser vide pour un mot de passe aleatoire"
        if ([string]::IsNullOrEmpty($pwd)) {
            return @{ Value = (New-RandomPassword); Generated = $true }
        }
        if ($pwd.Length -lt 10) {
            Write-Host '  Le mot de passe doit contenir au moins 10 caracteres.' -ForegroundColor Yellow
            continue
        }
        if ($pwd -notmatch $PasswordPattern) {
            Write-Host '  Caracteres autorises : lettres, chiffres et ! @ # % * - _ + . : ? = /' -ForegroundColor Yellow
            continue
        }
        $confirm = Read-Secret 'Confirmer le mot de passe'
        if ($pwd -ne $confirm) {
            Write-Host '  Les deux saisies different, recommencez.' -ForegroundColor Yellow
            continue
        }
        return @{ Value = $pwd; Generated = $false }
    }
}

# --------------------------------------------------------------------------
# Confirmation / sauvegarde
# --------------------------------------------------------------------------
Write-Host ''
Write-Host '=== Initialisation de la configuration ICHESS Finance ===' -ForegroundColor Cyan
Write-Host 'Les mots de passe saisis ne sont ni affiches ni journalises.'
Write-Host ''

if ((Test-Path $envFile) -and (-not $Force)) {
    $answer = Read-Host '.env existe deja. Le remplacer ? [o/N]'
    if ($answer -notmatch '^[oOyY]') {
        Write-Host 'Operation annulee.'
        exit 0
    }
    $backup = "$envFile.bak.$(Get-Date -Format 'yyyyMMddHHmmss')"
    Copy-Item -Path $envFile -Destination $backup -Force
    Write-Host "Ancien fichier sauvegarde : $backup"
}

# --------------------------------------------------------------------------
# Mots de passe initiaux (jamais affichés, jamais journalisés)
# --------------------------------------------------------------------------
$generated = @()

$admin = Read-InitialPassword 'administrateur (Ichessfinadmin)'
if ($admin.Generated) {
    $generated += "Administrateur (Ichessfinadmin) : $($admin.Value)"
    Write-Host '  -> mot de passe administrateur genere automatiquement.' -ForegroundColor Yellow
}

$finance = Read-InitialPassword 'financier (Emanuel)'
if ($finance.Generated) {
    $generated += "Financier (Emanuel) : $($finance.Value)"
    Write-Host '  -> mot de passe financier genere automatiquement.' -ForegroundColor Yellow
}

# --------------------------------------------------------------------------
# Secrets techniques
# --------------------------------------------------------------------------
$djangoSecret = New-UrlSafeToken 48
$postgresPass = New-UrlSafeToken 32
$fernetKey    = New-FernetKey

# --------------------------------------------------------------------------
# Écriture du .env  (UTF-8 sans BOM, fins de ligne LF)
# --------------------------------------------------------------------------
$timestamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')

$lines = @(
    "# Genere par scripts/init-secrets.ps1 le $timestamp"
    '# FICHIER SECRET - ne jamais committer. Exclu par .gitignore.'
    ''
    '# --- Django -----------------------------------------------------------'
    "DJANGO_SECRET_KEY=$djangoSecret"
    'DJANGO_DEBUG=False'
    'DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1'
    'DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8080'
    'CORS_ALLOWED_ORIGINS=http://localhost:8080'
    'DJANGO_SECURE_COOKIES=False'
    'DJANGO_SECURE_SSL_REDIRECT=False'
    'DJANGO_SECURE_HSTS_SECONDS=0'
    ''
    '# --- PostgreSQL -------------------------------------------------------'
    'POSTGRES_DB=finbank'
    'POSTGRES_USER=finbank'
    "POSTGRES_PASSWORD=$postgresPass"
    ''
    '# --- Chiffrement des secrets bancaires (Fernet) -----------------------'
    '# A sauvegarder separement : sans elle, les identifiants Ecobank doivent'
    '# etre ressaisis.'
    "FIELD_ENCRYPTION_KEY=$fernetKey"
    ''
    '# --- Comptes initiaux (premier demarrage uniquement) ------------------'
    '# Haches en Argon2id. Videz les deux mots de passe apres la premiere'
    '# connexion (voir docs/INSTALLATION.md section 2.7).'
    'INITIAL_ADMIN_USERNAME=Ichessfinadmin'
    "INITIAL_ADMIN_PASSWORD=$($admin.Value)"
    'INITIAL_FINANCE_USERNAME=Emanuel'
    "INITIAL_FINANCE_PASSWORD=$($finance.Value)"
    ''
    '# --- Sessions & authentification --------------------------------------'
    'JWT_ACCESS_MINUTES=15'
    'JWT_REFRESH_MINUTES=480'
    'SESSION_COOKIE_AGE=3600'
    'MAX_LOGIN_ATTEMPTS=5'
    'LOGIN_LOCKOUT_MINUTES=15'
    'THROTTLE_LOGIN=20/min'
    ''
    '# --- Application ------------------------------------------------------'
    'APP_COMPANY_NAME=ICHESS Finance'
    'APP_CURRENCY=USD'
    'TIME_ZONE=Africa/Kinshasa'
    'LANGUAGE_CODE=fr-fr'
    'DJANGO_LOG_LEVEL=INFO'
    ''
    '# --- Ecobank ----------------------------------------------------------'
    'ECOBANK_BASE_URL=https://apimuat-gateway.ecobank.com'
    'ECOBANK_AUTH_PATH=/corp-auth/api/v2/integration/auth/app/token'
    'ECOBANK_BALANCE_PATH=/corp-account-inquiry/api/v2/integration/account/inquiry/balance'
    'ECOBANK_HTTP_TIMEOUT=30'
    'BANK_SYNC_INTERVAL_MINUTES=30'
    'BANK_SYNC_WORKER_ENABLED=True'
    ''
    '# --- Reverse proxy & sauvegardes --------------------------------------'
    'NGINX_HTTP_PORT=8080'
    'BACKUP_INTERVAL_SECONDS=86400'
    'BACKUP_RETENTION_DAYS=7'
)

$content = ($lines -join "`n") + "`n"
[System.IO.File]::WriteAllText($envFile, $content, ([System.Text.UTF8Encoding]::new($false)))

$aclApplied = $true
try {
    & icacls "$envFile" /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null
    if ($LASTEXITCODE -ne 0) { $aclApplied = $false }
}
catch {
    $aclApplied = $false
}

Write-Host ''
Write-Host "OK : fichier .env cree ($envFile)." -ForegroundColor Green
if (-not $aclApplied) {
    Write-Host 'ATTENTION : droits restreints non appliques - verifiez les permissions du fichier.' -ForegroundColor Yellow
}

if ($generated.Count -gt 0) {
    Write-Host ''
    Write-Host 'Mots de passe generes automatiquement - notez-les MAINTENANT (ils ne seront plus affiches) :' -ForegroundColor Yellow
    foreach ($line in $generated) { Write-Host "   $line" }
}

Write-Host ''
Write-Host 'Etape suivante :' -ForegroundColor Cyan
Write-Host '   docker compose up -d --build'
Write-Host '   docker compose ps'
Write-Host ''
Write-Host 'Puis ouvrez http://localhost:8080 - le changement de mot de passe est obligatoire' -ForegroundColor Cyan
Write-Host 'a la premiere connexion.' -ForegroundColor Cyan
