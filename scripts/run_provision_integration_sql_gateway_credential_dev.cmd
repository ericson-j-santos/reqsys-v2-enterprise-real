@echo off
setlocal
cd /d "%~dp0.."

python scripts\provision_integration_sql_gateway_credential_dev.py --output audit\user-journey\excel-sql-sharepoint-dev\gateway-sql-credential.json
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
  echo Falha ao provisionar a credencial SQL DEV. Codigo: %RC%
  exit /b %RC%
)

echo Credencial SQL DEV provisionada e validada.
type audit\user-journey\excel-sql-sharepoint-dev\gateway-sql-credential.json
exit /b 0
