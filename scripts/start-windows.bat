@echo off
rem ===========================================================================
rem  ICHESS Finance - demarrage complet sous Windows (Docker Desktop)
rem  1. cree .env s'il est absent (secrets + mots de passe initiaux)
rem  2. construit les images et demarre la pile
rem  3. affiche l'etat des services
rem ===========================================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0.."

docker version >nul 2>&1
if errorlevel 1 (
  echo [ERREUR] Docker n'est pas demarre ou n'est pas installe.
  echo          Lancez Docker Desktop puis reessayez.
  pause
  exit /b 1
)

if not exist ".env" (
  echo [1/3] Fichier .env absent : generation des secrets...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0init-secrets.ps1"
  if errorlevel 1 (
    echo [ERREUR] La generation du fichier .env a echoue.
    pause
    exit /b 1
  )
) else (
  echo [1/3] Fichier .env deja present.
)

echo [2/3] Construction des images et demarrage des services...
docker compose up -d --build
if errorlevel 1 (
  echo [ERREUR] docker compose a echoue. Consultez les messages ci-dessus.
  pause
  exit /b 1
)

echo [3/3] Etat des services :
docker compose ps
echo.
echo Application : http://localhost:8080
echo Journaux   : docker compose logs -f backend
pause
