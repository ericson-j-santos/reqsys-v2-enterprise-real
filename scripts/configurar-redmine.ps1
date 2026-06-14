# Configura integração Redmine no ReqSys (Fly.io secrets + .env local)
# Uso: .\scripts\configurar-redmine.ps1 -ApiKey "abc123" -ProjectId 1
#       .\scripts\configurar-redmine.ps1 -ApiKey "abc123" -ProjectId 1 -Env dev
#
# O que faz:
#   1. Seta REDMINE_API_KEY e REDMINE_PROJECT_ID nos secrets Fly.io do backend
#   2. Atualiza o .env local com os mesmos valores
#   3. Verifica o status via API do ReqSys

param(
    [Parameter(Mandatory)]
    [string]$ApiKey,

    [Parameter(Mandatory)]
    [int]$ProjectId,

    [ValidateSet("prod","dev","staging")]
    [string]$Env = "prod",

    [string]$BaseUrl = ""
)

$fly = "$env:USERPROFILE\.fly\bin\flyctl.exe"
$root = Split-Path $PSScriptRoot -Parent

$apiApp = switch ($Env) {
    "prod"    { "reqsys-api" }
    "dev"     { "reqsys-api-dev" }
    "staging" { "reqsys-api-stg" }
}
$apiHost = switch ($Env) {
    "prod"    { "https://reqsys-api.fly.dev" }
    "dev"     { "https://reqsys-api-dev.fly.dev" }
    "staging" { "https://reqsys-api-stg.fly.dev" }
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " Configurar Redmine no ReqSys - ambiente: $Env ($apiApp)" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

# ---- 1. Setar secrets no Fly.io ----
Write-Host ""
Write-Host "[1/3] Configurando secrets no Fly.io ($apiApp)..." -ForegroundColor Yellow

& $fly secrets set `
    REDMINE_API_KEY="$ApiKey" `
    REDMINE_PROJECT_ID="$ProjectId" `
    --app $apiApp

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO ao setar secrets no Fly.io!" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Secrets configurados em $apiApp" -ForegroundColor Green

# ---- 2. Atualizar .env local ----
Write-Host ""
Write-Host "[2/3] Atualizando .env local..." -ForegroundColor Yellow

$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
    $content = Get-Content $envFile -Raw
    $content = $content -replace "REDMINE_API_KEY=.*", "REDMINE_API_KEY=$ApiKey"
    $content = $content -replace "REDMINE_PROJECT_ID=.*", "REDMINE_PROJECT_ID=$ProjectId"
    $content | Set-Content $envFile -Encoding UTF8 -NoNewline
    Write-Host "  [OK] .env atualizado" -ForegroundColor Green
} else {
    Write-Host "  [AVS] Arquivo .env nao encontrado em $root - pulando" -ForegroundColor Yellow
}

# ---- 3. Verificar via API do ReqSys ----
Write-Host ""
Write-Host "[3/3] Verificando status via API do ReqSys ($apiHost)..." -ForegroundColor Yellow

Start-Sleep -Seconds 5  # aguarda restart do app apos secrets

try {
    $r = Invoke-RestMethod "$apiHost/v1/sistema/segredos-status" -ErrorAction Stop
    $secrets = $r.data
    $redmineUrl   = ($secrets | Where-Object { $_.nome -eq "REDMINE_BASE_URL"   }).status
    $redmineKey   = ($secrets | Where-Object { $_.nome -eq "REDMINE_API_KEY"    }).status
    $redmineProj  = ($secrets | Where-Object { $_.nome -eq "REDMINE_PROJECT_ID" }).status
    Write-Host "  REDMINE_BASE_URL   : $redmineUrl"
    Write-Host "  REDMINE_API_KEY    : $redmineKey"
    Write-Host "  REDMINE_PROJECT_ID : $redmineProj"

    $allOk = ($redmineKey -ne "ausente") -and ($redmineProj -ne "ausente")
    if ($allOk) {
        Write-Host ""
        Write-Host "  [OK] Integracao Redmine configurada com sucesso!" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "  [AVS] Algum secret ainda aparece como ausente. Aguarde o restart completo e verifique." -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [AVS] Nao foi possivel verificar via API: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " Concluido. Para testar a integracao:" -ForegroundColor Cyan
Write-Host "  $apiHost/docs  ->  POST /v1/backlog/publicar-redmine/{id}" -ForegroundColor White
Write-Host "================================================================" -ForegroundColor Cyan
