# Deploy ReqSys para Fly.io
# Uso: .\scripts\fly-deploy.ps1 -Env prod|dev|staging [-SecretsOnly]
param(
    [ValidateSet("prod","dev","staging")]
    [string]$Env = "prod",
    [switch]$SecretsOnly
)

$fly = "$env:USERPROFILE\.fly\bin\flyctl.exe"
$root = Split-Path $PSScriptRoot -Parent

$apiConfig = switch ($Env) {
    "prod"    { "fly.toml" }
    "dev"     { "fly.dev.toml" }
    "staging" { "fly.staging.toml" }
}

$appConfig = $apiConfig

# Nomes dos apps (devem coincidir com os fly.toml)
$apiApp = switch ($Env) {
    "prod"    { "reqsys-api" }
    "dev"     { "reqsys-api-dev" }
    "staging" { "reqsys-api-stg" }
}
$frontendApp = switch ($Env) {
    "prod"    { "reqsys-app" }
    "dev"     { "reqsys-app-dev" }
    "staging" { "reqsys-app-stg" }
}

Write-Host "`n=== ReqSys Fly.io Deploy — ambiente: $Env ===" -ForegroundColor Cyan

# Verifica autenticacao
$authCheck = & $fly auth whoami 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Nao autenticado. Abrindo login..." -ForegroundColor Yellow
    & $fly auth login
}

# Configura secrets do backend
function Set-BackendSecrets([string]$app) {
    Write-Host "`n--- Configurando secrets do backend ($app) ---" -ForegroundColor Yellow

    $jwtSecret = Read-Host "JWT_SECRET (deixe em branco para gerar automaticamente)"
    if ([string]::IsNullOrWhiteSpace($jwtSecret)) {
        $jwtSecret = [System.Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
        Write-Host "JWT_SECRET gerado: $jwtSecret" -ForegroundColor Green
    }

    $geminiKey = Read-Host "GEMINI_API_KEY (opcional, Enter para pular)"

    & $fly secrets set JWT_SECRET="$jwtSecret" --app $app

    if (-not [string]::IsNullOrWhiteSpace($geminiKey)) {
        & $fly secrets set GEMINI_API_KEY="$geminiKey" --app $app
    }

    Write-Host "Secrets configurados para $app" -ForegroundColor Green
}

if ($SecretsOnly) {
    Set-BackendSecrets $apiApp
    exit 0
}

# ---- Deploy Backend ----
Write-Host "`n[1/2] Deploy do Backend ($apiApp)..." -ForegroundColor Cyan
Push-Location "$root\backend"

# Cria o app se nao existir
$appExists = & $fly apps list 2>&1 | Select-String $apiApp
if (-not $appExists) {
    Write-Host "Criando app $apiApp..." -ForegroundColor Yellow
    & $fly apps create $apiApp
    & $fly volumes create reqsys_data --region gru --size 1 --app $apiApp
    Set-BackendSecrets $apiApp
}

& $fly deploy --config $apiConfig --remote-only
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO no deploy do backend!" -ForegroundColor Red
    Pop-Location; exit 1
}
Write-Host "Backend OK: https://$apiApp.fly.dev" -ForegroundColor Green
Pop-Location

# ---- Deploy Frontend ----
Write-Host "`n[2/2] Deploy do Frontend ($frontendApp)..." -ForegroundColor Cyan
Push-Location "$root\frontend"

$appExists = & $fly apps list 2>&1 | Select-String $frontendApp
if (-not $appExists) {
    Write-Host "Criando app $frontendApp..." -ForegroundColor Yellow
    & $fly apps create $frontendApp
}

& $fly deploy --config $appConfig --remote-only
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO no deploy do frontend!" -ForegroundColor Red
    Pop-Location; exit 1
}
Write-Host "Frontend OK: https://$frontendApp.fly.dev" -ForegroundColor Green
Pop-Location

Write-Host "`n=== Deploy concluido ===" -ForegroundColor Green
Write-Host "API:      https://$apiApp.fly.dev/health"
Write-Host "App:      https://$frontendApp.fly.dev"
Write-Host "API Docs: https://$apiApp.fly.dev/docs"
