param(
    [string]$GitLabToken = "",
    [string]$FlyToken = "",
    [string]$SlackWebhook = "",
    [switch]$DryRun = $false,
    [switch]$ValidateOnly = $false
)

# Configuration
$ProjectId = "48896143"
$ApiUrl = "https://gitlab.com/api/v4"
$OcrKey = "h8WvWKaXtGICrDGaPzyWVU68VRJfcB46OA2c99LrZA4="

Write-Host ""
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  OCR v2 - GitLab CI Setup Automation" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

if ($DryRun) {
    Write-Host "[DRY-RUN MODE] Nenhuma alteracao sera feita" -ForegroundColor Yellow
    Write-Host ""
}

# Get token if not provided
if ([string]::IsNullOrWhiteSpace($GitLabToken)) {
    Write-Host "GitLab Personal Access Token obrigatorio" -ForegroundColor Red
    Write-Host "Obter em: https://gitlab.com/-/user_settings/personal_access_tokens" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

# Test token
Write-Host "Testando GitLab token..." -ForegroundColor Cyan

$headers = @{
    "PRIVATE-TOKEN" = $GitLabToken
}

try {
    $user = Invoke-RestMethod -Uri "$ApiUrl/user" -Headers $headers -Method Get -TimeoutSec 10
    Write-Host "[OK] Token valido. Usuario: $($user.username)" -ForegroundColor Green
} catch {
    Write-Host "[ERRO] Token invalido: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Configurando variaveis GitLab..." -ForegroundColor Cyan
Write-Host ""

# Variables to create
$variables = @(
    @{
        Name = "FLY_API_TOKEN"
        Value = if ([string]::IsNullOrWhiteSpace($FlyToken)) { "[NAO FORNECIDO]" } else { $FlyToken }
        Optional = $true
    },
    @{
        Name = "OCR_DATA_ENCRYPTION_KEY"
        Value = $OcrKey
        Optional = $false
    },
    @{
        Name = "SLACK_WEBHOOK_OCR"
        Value = if ([string]::IsNullOrWhiteSpace($SlackWebhook)) { "[NAO FORNECIDO]" } else { $SlackWebhook }
        Optional = $true
    }
)

$success = $true

foreach ($var in $variables) {
    Write-Host "Processando: $($var.Name)" -ForegroundColor Yellow

    if ($var.Value -eq "[NAO FORNECIDO]") {
        Write-Host "  [PULADO] Valor nao fornecido (opcional)" -ForegroundColor Gray
        continue
    }

    if ($DryRun) {
        Write-Host "  [DRY-RUN] Seria criada/atualizada com valor: $($var.Value.Substring(0, 20))..." -ForegroundColor Gray
        continue
    }

    if ($ValidateOnly) {
        Write-Host "  [VALIDANDO] Verificando se existe..." -ForegroundColor Gray

        try {
            $existing = Invoke-RestMethod `
                -Uri "$ApiUrl/projects/$ProjectId/variables/$($var.Name)" `
                -Headers $headers `
                -Method Get `
                -TimeoutSec 10

            Write-Host "  [OK] Ja existe (Masked: $($existing.masked), Protected: $($existing.protected))" -ForegroundColor Green
        } catch {
            Write-Host "  [FALTA] Nao encontrada" -ForegroundColor Yellow
            $success = $false
        }
        continue
    }

    # Create or update variable
    $body = @{
        key = $var.Name
        value = $var.Value
        protected = $true
        masked = $true
    } | ConvertTo-Json

    try {
        # Try to get existing
        $existing = $null
        try {
            $existing = Invoke-RestMethod `
                -Uri "$ApiUrl/projects/$ProjectId/variables/$($var.Name)" `
                -Headers $headers `
                -Method Get `
                -TimeoutSec 10
        } catch {
            # Doesnt exist yet
        }

        if ($null -ne $existing) {
            # Update
            Invoke-RestMethod `
                -Uri "$ApiUrl/projects/$ProjectId/variables/$($var.Name)" `
                -Headers $headers `
                -Body $body `
                -Method Put `
                -TimeoutSec 10 `
                -ContentType "application/json" | Out-Null

            Write-Host "  [ATUALIZADO] $($var.Name)" -ForegroundColor Green
        } else {
            # Create
            Invoke-RestMethod `
                -Uri "$ApiUrl/projects/$ProjectId/variables" `
                -Headers $headers `
                -Body $body `
                -Method Post `
                -TimeoutSec 10 `
                -ContentType "application/json" | Out-Null

            Write-Host "  [CRIADO] $($var.Name)" -ForegroundColor Green
        }
    } catch {
        Write-Host "  [ERRO] $($_.Exception.Message)" -ForegroundColor Red
        $success = $false
    }
}

Write-Host ""
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

if ($DryRun) {
    Write-Host "[DRY-RUN COMPLETO] Sem alteracoes foram feitas" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Para executar para valer, remova -DryRun:" -ForegroundColor Cyan
    Write-Host "  .\scripts\setup-ocr-gitlab-ci-vars.ps1 -GitLabToken 'glpat-...'" -ForegroundColor Gray
} elseif ($ValidateOnly) {
    if ($success) {
        Write-Host "[OK] Todas as variaveis estao configuradas!" -ForegroundColor Green
    } else {
        Write-Host "[AVISO] Algumas variaveis faltam" -ForegroundColor Yellow
    }
} else {
    Write-Host "[OK] Variaveis configuradas com sucesso!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Proximos passos:" -ForegroundColor Cyan
    Write-Host "  1. IR para: https://gitlab.com/ericson-j-santos/reqsys-v2-enterprise-real/pipelines" -ForegroundColor Gray
    Write-Host "  2. Clicar em: Play no job 'ocr_deploy_staging_fly'" -ForegroundColor Gray
    Write-Host "  3. Aguardar ~5-8 minutos" -ForegroundColor Gray
    Write-Host "  4. Validar: https://reqsys-api-stg.fly.dev/health" -ForegroundColor Gray
}

Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
