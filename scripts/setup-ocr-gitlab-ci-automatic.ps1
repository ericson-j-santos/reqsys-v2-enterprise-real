param(
    [string]$GitLabToken = "",
    [string]$FlyToken = "",
    [string]$SlackWebhook = "",
    [switch]$DryRun = $false,
    [switch]$ValidateOnly = $false,
    [switch]$TriggerPipeline = $false
)

# Configuration
$GitLabProjectId = "48896143"  # reqsys-v2-enterprise-real
$GitLabApiUrl = "https://gitlab.com/api/v4"
$GitLabProjectUrl = "https://gitlab.com/ericson-j-santos/reqsys-v2-enterprise-real"

# OCR encryption key (gerada anteriormente)
$OcrEncryptionKey = "h8WvWKaXtGICrDGaPzyWVU68VRJfcB46OA2c99LrZA4="

Write-Host ""
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  OCR v2 — GitLab CI Setup Automation" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# VALIDAR INPUTS
# ============================================================================

function Validate-Inputs {
    $valid = $true

    if ([string]::IsNullOrWhiteSpace($GitLabToken)) {
        Write-Host "❌ GitLab token não fornecido" -ForegroundColor Red
        Write-Host "   Use: -GitLabToken 'glpat-xxxxx'" -ForegroundColor Yellow
        $valid = $false
    }

    if ([string]::IsNullOrWhiteSpace($FlyToken)) {
        Write-Host "⚠️  Fly.io token não fornecido (será solicitado)" -ForegroundColor Yellow
    }

    if ([string]::IsNullOrWhiteSpace($SlackWebhook)) {
        Write-Host "⚠️  Slack webhook não fornecido (será solicitado)" -ForegroundColor Yellow
    }

    return $valid
}

# ============================================================================
# CAPTURAR CREDENCIAIS
# ============================================================================

function Get-Credentials {
    if ([string]::IsNullOrWhiteSpace($GitLabToken)) {
        Write-Host ""
        Write-Host "🔑 GitLab Personal Access Token (obter em: https://gitlab.com/-/user_settings/personal_access_tokens)" -ForegroundColor Cyan
        $GitLabToken = Read-Host "Token (glpat-...)"

        if ([string]::IsNullOrWhiteSpace($GitLabToken)) {
            Write-Host "❌ Token é obrigatório!" -ForegroundColor Red
            return $false
        }
    }

    if ([string]::IsNullOrWhiteSpace($FlyToken)) {
        Write-Host ""
        Write-Host "🔑 Fly.io API Token (obter em: https://fly.io/account/access-tokens)" -ForegroundColor Cyan
        $input = Read-Host "Token (fm1_...) [Enter para pular]"
        if (-not [string]::IsNullOrWhiteSpace($input)) {
            $FlyToken = $input
        }
    }

    if ([string]::IsNullOrWhiteSpace($SlackWebhook)) {
        Write-Host ""
        Write-Host "🔑 Slack Webhook URL (obter em: https://api.slack.com/apps > Incoming Webhooks)" -ForegroundColor Cyan
        $input = Read-Host "URL (https://hooks.slack.com/...) [Enter para pular]"
        if (-not [string]::IsNullOrWhiteSpace($input)) {
            $SlackWebhook = $input
        }
    }

    return $true
}

# ============================================================================
# GITLAB API FUNCTIONS
# ============================================================================

function Test-GitLabToken {
    Write-Host ""
    Write-Host "🔍 Testando GitLab token..." -ForegroundColor Cyan

    $headers = @{
        "PRIVATE-TOKEN" = $GitLabToken
    }

    try {
        $response = Invoke-RestMethod `
            -Uri "$GitLabApiUrl/user" `
            -Headers $headers `
            -Method Get `
            -TimeoutSec 10

        Write-Host "✅ Token válido. Usuário: $($response.username)" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "❌ Token inválido ou expirado: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

function Get-GitLabVariable {
    param(
        [string]$VariableName
    )

    $headers = @{
        "PRIVATE-TOKEN" = $GitLabToken
    }

    try {
        $response = Invoke-RestMethod `
            -Uri "$GitLabApiUrl/projects/$GitLabProjectId/variables/$VariableName" `
            -Headers $headers `
            -Method Get `
            -TimeoutSec 10

        return $response
    } catch {
        return $null
    }
}

function Set-GitLabVariable {
    param(
        [string]$VariableName,
        [string]$VariableValue,
        [bool]$Protected = $true,
        [bool]$Masked = $true
    )

    $headers = @{
        "PRIVATE-TOKEN" = $GitLabToken
        "Content-Type" = "application/json"
    }

    $body = @{
        key = $VariableName
        value = $VariableValue
        protected = $Protected
        masked = $Masked
    } | ConvertTo-Json

    $existing = Get-GitLabVariable -VariableName $VariableName

    if ($null -ne $existing) {
        # Update existing
        Write-Host "📝 Atualizando variável: $VariableName" -ForegroundColor Yellow

        if ($DryRun) {
            Write-Host "   [DRY RUN] PUT $GitLabApiUrl/projects/$GitLabProjectId/variables/$VariableName" -ForegroundColor Gray
            return $true
        }

        try {
            $response = Invoke-RestMethod `
                -Uri "$GitLabApiUrl/projects/$GitLabProjectId/variables/$VariableName" `
                -Headers $headers `
                -Body $body `
                -Method Put `
                -TimeoutSec 10

            Write-Host "✅ Variável atualizada: $VariableName" -ForegroundColor Green
            return $true
        } catch {
            Write-Host "❌ Erro ao atualizar variável: $($_.Exception.Message)" -ForegroundColor Red
            return $false
        }
    } else {
        # Create new
        Write-Host "➕ Criando variável: $VariableName" -ForegroundColor Cyan

        if ($DryRun) {
            Write-Host "   [DRY RUN] POST $GitLabApiUrl/projects/$GitLabProjectId/variables" -ForegroundColor Gray
            Write-Host "   Body: $body" -ForegroundColor Gray
            return $true
        }

        try {
            $response = Invoke-RestMethod `
                -Uri "$GitLabApiUrl/projects/$GitLabProjectId/variables" `
                -Headers $headers `
                -Body $body `
                -Method Post `
                -TimeoutSec 10

            Write-Host "✅ Variável criada: $VariableName" -ForegroundColor Green
            return $true
        } catch {
            Write-Host "❌ Erro ao criar variável: $($_.Exception.Message)" -ForegroundColor Red
            return $false
        }
    }
}

function Get-GitLabVariables {
    $headers = @{
        "PRIVATE-TOKEN" = $GitLabToken
    }

    try {
        $response = Invoke-RestMethod `
            -Uri "$GitLabApiUrl/projects/$GitLabProjectId/variables" `
            -Headers $headers `
            -Method Get `
            -TimeoutSec 10

        return $response
    } catch {
        Write-Host "❌ Erro ao listar variáveis: $($_.Exception.Message)" -ForegroundColor Red
        return @()
    }
}

function Trigger-GitLabPipeline {
    Write-Host ""
    Write-Host "🚀 Disparando pipeline..." -ForegroundColor Cyan

    $headers = @{
        "PRIVATE-TOKEN" = $GitLabToken
    }

    if ($DryRun) {
        Write-Host "   [DRY RUN] POST para disparar pipeline" -ForegroundColor Gray
        return $true
    }

    try {
        # Primeiro, obter o ID do branch main
        $branchResponse = Invoke-RestMethod `
            -Uri "$GitLabApiUrl/projects/$GitLabProjectId/repository/branches/main" `
            -Headers $headers `
            -Method Get `
            -TimeoutSec 10

        Write-Host "✅ Branch main encontrado. Commit: $($branchResponse.commit.id)" -ForegroundColor Green

        # Pipeline será disparado automaticamente no próximo push
        Write-Host "📝 Pipeline será disparado no próximo push para main" -ForegroundColor Yellow
        Write-Host "   Manual: Ir para CI/CD > Pipelines > Play ocr_deploy_staging_fly" -ForegroundColor Gray

        return $true
    } catch {
        Write-Host "⚠️  Não foi possível disparar pipeline: $($_.Exception.Message)" -ForegroundColor Yellow
        return $false
    }
}

# ============================================================================
# VALIDAR CONFIGURAÇÃO
# ============================================================================

function Validate-Configuration {
    Write-Host ""
    Write-Host "📋 Validando configuração..." -ForegroundColor Cyan

    $vars = Get-GitLabVariables

    $checks = @{
        "FLY_API_TOKEN" = $false
        "OCR_DATA_ENCRYPTION_KEY" = $false
        "SLACK_WEBHOOK_OCR" = $false
    }

    foreach ($var in $vars) {
        if ($checks.ContainsKey($var.key)) {
            $checks[$var.key] = $true
            Write-Host "✅ $($var.key): Configurada (Masked: $($var.masked), Protected: $($var.protected))" -ForegroundColor Green
        }
    }

    Write-Host ""
    $allConfigured = $checks.Values | Where-Object { $_ -eq $false }
    if ($allConfigured.Count -gt 0) {
        Write-Host "⚠️  Variáveis faltando:" -ForegroundColor Yellow
        foreach ($check in $checks.GetEnumerator()) {
            if (-not $check.Value) {
                Write-Host "   ❌ $($check.Name)" -ForegroundColor Yellow
            }
        }
        return $false
    } else {
        Write-Host "✅ Todas as variáveis configuradas!" -ForegroundColor Green
        return $true
    }
}

# ============================================================================
# MAIN
# ============================================================================

Write-Host "📝 Modo: $(if ($DryRun) { 'DRY RUN (nenhuma alteração será feita)' } else { 'NORMAL (alterações reais)' })" -ForegroundColor Cyan

# Step 1: Validar inputs
if (-not (Validate-Inputs)) {
    Write-Host ""
    Write-Host "❌ Inputs inválidos. Execute novamente com:" -ForegroundColor Red
    Write-Host "   .\scripts\setup-ocr-gitlab-ci-automatic.ps1 -GitLabToken 'glpat-...' -FlyToken 'fm1_...' -SlackWebhook 'https://hooks.slack.com/...'"
    exit 1
}

# Step 2: Capturar credenciais se não fornecidas
if (-not (Get-Credentials)) {
    Write-Host "❌ Falha ao obter credenciais" -ForegroundColor Red
    exit 1
}

# Step 3: Validar modo
if ($ValidateOnly) {
    Write-Host ""
    Write-Host "🔍 Modo validação apenas (sem alterações)" -ForegroundColor Cyan

    if (Test-GitLabToken) {
        $valid = Validate-Configuration
        if ($valid) {
            Write-Host ""
            Write-Host "✅ Configuração está válida!" -ForegroundColor Green
            exit 0
        } else {
            Write-Host ""
            Write-Host "❌ Configuração está incompleta" -ForegroundColor Red
            exit 1
        }
    }
    exit 1
}

# Step 4: Testar GitLab token
if (-not (Test-GitLabToken)) {
    Write-Host "❌ Falha na autenticação GitLab" -ForegroundColor Red
    exit 1
}

# Step 5: Configurar variáveis
Write-Host ""
Write-Host "⚙️  Configurando variáveis GitLab..." -ForegroundColor Cyan

$allSuccess = $true

if (-not [string]::IsNullOrWhiteSpace($FlyToken)) {
    if (-not (Set-GitLabVariable -VariableName "FLY_API_TOKEN" -VariableValue $FlyToken)) {
        $allSuccess = $false
    }
} else {
    Write-Host "⏭️  Pulando FLY_API_TOKEN (não fornecido)" -ForegroundColor Yellow
}

if (-not (Set-GitLabVariable -VariableName "OCR_DATA_ENCRYPTION_KEY" -VariableValue $OcrEncryptionKey)) {
    $allSuccess = $false
}

if (-not [string]::IsNullOrWhiteSpace($SlackWebhook)) {
    if (-not (Set-GitLabVariable -VariableName "SLACK_WEBHOOK_OCR" -VariableValue $SlackWebhook)) {
        $allSuccess = $false
    }
} else {
    Write-Host "⏭️  Pulando SLACK_WEBHOOK_OCR (não fornecido)" -ForegroundColor Yellow
}

# Step 6: Validar configuração
Write-Host ""
Write-Host "✅ Validando configuração final..." -ForegroundColor Cyan
$valid = Validate-Configuration

# Step 7: Resumo
Write-Host ""
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

if ($allSuccess -and $valid) {
    Write-Host "✅ SUCESSO! Todas as variáveis configuradas no GitLab" -ForegroundColor Green
    Write-Host ""
    Write-Host "Próximas ações:" -ForegroundColor Cyan
    Write-Host "  1. Ir para: $GitLabProjectUrl/pipelines" -ForegroundColor Gray
    Write-Host "  2. Clicar em: ▶️ Play no job 'ocr_deploy_staging_fly'" -ForegroundColor Gray
    Write-Host "  3. Aguardar ~5-8 minutos" -ForegroundColor Gray
    Write-Host "  4. Validar endpoints:" -ForegroundColor Gray
    Write-Host "     - https://reqsys-api-stg.fly.dev/health" -ForegroundColor Gray
    Write-Host "     - https://reqsys-api-stg.fly.dev/v1/ocr/readiness" -ForegroundColor Gray

    if ($TriggerPipeline) {
        Write-Host ""
        Write-Host "🚀 Disparando pipeline automático..." -ForegroundColor Cyan
        Trigger-GitLabPipeline
    }

    Write-Host ""
    Write-Host "📚 Documentação: $GitLabProjectUrl/tree/main/docs/runbooks" -ForegroundColor Gray
    Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    exit 0
} else {
    Write-Host "❌ FALHA! Algumas variáveis não foram configuradas corretamente" -ForegroundColor Red
    Write-Host ""
    Write-Host "Revisar erros acima e tentar novamente" -ForegroundColor Yellow
    Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    exit 1
}
