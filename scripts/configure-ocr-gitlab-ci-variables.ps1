<#
.SYNOPSIS
    Configure OCR v2 deployment variables in GitLab CI/CD

.DESCRIPTION
    This script guides you through configuring the 3 required variables for OCR v2
    deployment to Fly.io via GitLab CI:
    - FLY_API_TOKEN
    - OCR_DATA_ENCRYPTION_KEY
    - SLACK_WEBHOOK_OCR

.EXAMPLE
    .\scripts\configure-ocr-gitlab-ci-variables.ps1

.NOTES
    Required: GitLab project access with Settings > CI/CD > Variables permission
#>

param(
    [switch]$NonInteractive = $false,
    [string]$GitLabProjectUrl = "https://gitlab.com/ericson-j-santos/reqsys-v2-enterprise-real"
)

Write-Host @"

╔════════════════════════════════════════════════════════════════╗
║     OCR v2 — GitLab CI Variables Configuration                ║
║     Deploy para Fly.io Staging                                ║
╚════════════════════════════════════════════════════════════════╝

Este script ajuda você a configurar as variáveis necessárias para
o deploy automático de OCR v2 em Fly.io via GitLab CI.

@"

# ============================================================================
# 1. FLY_API_TOKEN
# ============================================================================

Write-Host @"

📋 PASSO 1: FLY_API_TOKEN
═══════════════════════════════════════════════════════════════

O que é: Token de autenticação do Fly.io para deploy

Como obter:
  1. Ir para: https://fly.io/account/access-tokens
  2. Clicar em "+ Create API Token"
  3. Nome: "reqsys-ocr-gitlab-ci" (ou similar)
  4. Permissions: deploy-apps (mínimo necessário)
  5. Copiar o token gerado

Ou, se já tiver um token genérico para Fly, pode reusar.

" -ForegroundColor Cyan

if (-not $NonInteractive) {
    $flyToken = Read-Host "Cola aqui seu FLY_API_TOKEN (ou deixa em branco para pular)"
    if (-not [string]::IsNullOrWhiteSpace($flyToken)) {
        Write-Host "✅ FLY_API_TOKEN capturado (primeiros 8 chars: $($flyToken.Substring(0, 8))***)" -ForegroundColor Green
    } else {
        Write-Host "⏭️  Pulando FLY_API_TOKEN (configure manualmente)" -ForegroundColor Yellow
        $flyToken = $null
    }
} else {
    Write-Host "⏭️  Modo não-interativo: você precisará configurar FLY_API_TOKEN manualmente" -ForegroundColor Yellow
    $flyToken = $null
}

# ============================================================================
# 2. OCR_DATA_ENCRYPTION_KEY
# ============================================================================

Write-Host @"

📋 PASSO 2: OCR_DATA_ENCRYPTION_KEY
═══════════════════════════════════════════════════════════════

O que é: Chave de criptografia AES-256-GCM para dados OCR (32 bytes em Base64)

" -ForegroundColor Cyan

# Generate the key
$bytes = New-Object byte[] 32
[Security.Cryptography.RNGCryptoServiceProvider]::Create().GetBytes($bytes)
$ocrKey = [Convert]::ToBase64String($bytes)

Write-Host "🔑 Chave gerada: $ocrKey" -ForegroundColor Green
Write-Host @"

Esta chave foi gerada aleatoriamente agora e é CRÍTICA para:
  ✓ Criptografar dados OCR em repouso
  ✓ Decriptar dados salvos
  ✓ Secret rotation (guardar versão anterior com chave v1)

⚠️  IMPORTANTE:
  - Guarde esta chave de forma segura
  - NÃO compartilhe em mensagens ou logs
  - Use a mesma chave em staging e produção
  - Para rotation: manter chave anterior como v1

" -ForegroundColor Yellow

if (-not $NonInteractive) {
    $confirm = Read-Host "Usar esta chave gerada? (S/n)"
    if ($confirm -eq 'n' -or $confirm -eq 'N') {
        $ocrKey = Read-Host "Cola a chave aqui (32 bytes em Base64)"
        Write-Host "✅ Chave customizada capturada" -ForegroundColor Green
    } else {
        Write-Host "✅ OCR_DATA_ENCRYPTION_KEY pronta" -ForegroundColor Green
    }
}

# ============================================================================
# 3. SLACK_WEBHOOK_OCR
# ============================================================================

Write-Host @"

📋 PASSO 3: SLACK_WEBHOOK_OCR
═══════════════════════════════════════════════════════════════

O que é: Webhook do Slack para notificações de deploy (sucesso/falha)

Como criar:
  1. Ir para: https://api.slack.com/apps
  2. Selecionar seu app (ou criar novo)
  3. Ir para: Incoming Webhooks
  4. Clicar em "Add New Webhook to Workspace"
  5. Selecionar o canal (ex: #ocr-deploys)
  6. Copiar a URL do webhook

Format: https://hooks.slack.com/services/T0000000/B0000000/XXXXXXXXXXXXXXXXXXXX

" -ForegroundColor Cyan

if (-not $NonInteractive) {
    $slackWebhook = Read-Host "Cola aqui seu SLACK_WEBHOOK_OCR (ou deixa em branco para pular)"
    if (-not [string]::IsNullOrWhiteSpace($slackWebhook)) {
        Write-Host "✅ SLACK_WEBHOOK_OCR capturado (primeiros 30 chars: $($slackWebhook.Substring(0, 30))***)" -ForegroundColor Green
    } else {
        Write-Host "⏭️  Pulando SLACK_WEBHOOK_OCR (configure manualmente)" -ForegroundColor Yellow
        $slackWebhook = $null
    }
} else {
    Write-Host "⏭️  Modo não-interativo: você precisará configurar SLACK_WEBHOOK_OCR manualmente" -ForegroundColor Yellow
    $slackWebhook = $null
}

# ============================================================================
# 4. SUMÁRIO E PRÓXIMAS AÇÕES
# ============================================================================

Write-Host @"

╔════════════════════════════════════════════════════════════════╗
║     📋 RESUMO DAS VARIÁVEIS                                   ║
╚════════════════════════════════════════════════════════════════╝

" -ForegroundColor Green

$summary = @{
    "FLY_API_TOKEN" = if ($flyToken) { "$($flyToken.Substring(0, 8))*** (capturado)" } else { "❌ NÃO CONFIGURADO" }
    "OCR_DATA_ENCRYPTION_KEY" = "✅ Gerado"
    "SLACK_WEBHOOK_OCR" = if ($slackWebhook) { "$($slackWebhook.Substring(0, 30))*** (capturado)" } else { "❌ NÃO CONFIGURADO" }
}

foreach ($var in $summary.GetEnumerator()) {
    Write-Host "$($var.Name): $($var.Value)"
}

Write-Host @"

╔════════════════════════════════════════════════════════════════╗
║     ✅ PRÓXIMAS AÇÕES                                         ║
╚════════════════════════════════════════════════════════════════╝

1. Ir para GitLab UI:
   $GitLabProjectUrl/settings/ci_cd

2. Expandir "Variables"

3. Clicar em "Add variable"

4. Adicionar 3 variáveis (uma por vez):

   ┌─ Variável 1: FLY_API_TOKEN
   │  Tipo: File ou Variable (fica sua escolha)
   │  Scope: main
   │  Flags: Masked, Protected
   │  Valor:
   │  $( if ($flyToken) { $flyToken } else { "[Cole aqui seu FLY_API_TOKEN]" })
   └─

   ┌─ Variável 2: OCR_DATA_ENCRYPTION_KEY
   │  Tipo: Variable
   │  Scope: main
   │  Flags: Masked, Protected
   │  Valor:
   │  $ocrKey
   └─

   ┌─ Variável 3: SLACK_WEBHOOK_OCR
   │  Tipo: Variable
   │  Scope: main
   │  Flags: Masked, Protected
   │  Valor:
   │  $( if ($slackWebhook) { $slackWebhook } else { "[Cole aqui seu SLACK_WEBHOOK_OCR]" })
   └─

5. Após configurar, testar o job:
   - Ir para: Pipelines
   - Clicar em seu pipeline
   - Clicar em "Play" no job: ocr_deploy_staging_fly
   - Aguardar ~5 minutos

6. Validar resultado:
   - Health: https://reqsys-api-stg.fly.dev/health
   - Readiness: https://reqsys-api-stg.fly.dev/v1/ocr/readiness
   - Slack: Verificar notificação no canal

7. Revisar evidência de deploy:
   - GitLab: CI/CD > Artifacts > ocr_publish_staging_evidence
   - Arquivo: audit/ocr/staging-deploy-evidence.json

╔════════════════════════════════════════════════════════════════╗
║     📚 DOCUMENTAÇÃO                                           ║
╚════════════════════════════════════════════════════════════════╝

- Deployment Strategy: docs/architecture/ocr-deployment-strategy.md
- Migration Plan: docs/architecture/ocr-pc24x7-migration-plan.md
- Action Items: docs/runbooks/ocr-deployment-action-items.md
- Deploy Job: gitlab/ci/ocr-deploy-staging.yml

" -ForegroundColor Cyan

Write-Host "✅ Script concluído!" -ForegroundColor Green
