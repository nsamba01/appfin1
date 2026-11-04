@echo off
rem ===========================================================================
rem  ICHESS Finance - generation du fichier .env sous Windows
rem  Double-cliquez sur ce fichier (ou executez-le depuis cmd).
rem ===========================================================================
setlocal
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0init-secrets.ps1" %*
set RC=%ERRORLEVEL%
if not "%RC%"=="0" (
  echo.
  echo Echec de la generation du fichier .env ^(code %RC%^).
  pause
)
exit /b %RC%
