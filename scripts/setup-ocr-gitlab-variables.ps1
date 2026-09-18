param(
    [switch]$ShowGenerated = $true
)

# Generate OCR_DATA_ENCRYPTION_KEY (AES-256-GCM: 32 bytes in Base64)
$bytes = New-Object byte[] 32
[Security.Cryptography.RNGCryptoServiceProvider]::Create().GetBytes($bytes)
$ocrKey = [Convert]::ToBase64String($bytes)

Write-Host ""
Write-Host "===================================================================="
Write-Host "OCR v2 - GitLab CI Variables Setup"
Write-Host "===================================================================="
Write-Host ""

Write-Host "Three variables need to be configured in GitLab:"
Write-Host "  Settings > CI/CD > Variables"
Write-Host ""

Write-Host "1. FLY_API_TOKEN"
Write-Host "   Type: Variable"
Write-Host "   Scope: main"
Write-Host "   Flags: Masked, Protected"
Write-Host "   Where: https://fly.io/account/access-tokens"
Write-Host "   Value: [Your Fly.io API token]"
Write-Host ""

Write-Host "2. OCR_DATA_ENCRYPTION_KEY"
Write-Host "   Type: Variable"
Write-Host "   Scope: main"
Write-Host "   Flags: Masked, Protected"
Write-Host "   Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "   Value: (see below)"
Write-Host ""

Write-Host "3. SLACK_WEBHOOK_OCR"
Write-Host "   Type: Variable"
Write-Host "   Scope: main"
Write-Host "   Flags: Masked, Protected"
Write-Host "   Where: https://api.slack.com/apps > Incoming Webhooks"
Write-Host "   Value: [Your Slack webhook URL]"
Write-Host ""

Write-Host "===================================================================="
Write-Host "Generated Values"
Write-Host "===================================================================="
Write-Host ""

Write-Host "Copy the following value to GitLab:"
Write-Host ""
Write-Host "OCR_DATA_ENCRYPTION_KEY (AES-256-GCM, 32 bytes Base64):"
Write-Host "  $ocrKey"
Write-Host ""

Write-Host "===================================================================="
Write-Host "Next Steps"
Write-Host "===================================================================="
Write-Host ""
Write-Host "1. Go to: https://gitlab.com/ericson-j-santos/reqsys-v2-enterprise-real"
Write-Host "2. Click: Settings > CI/CD > Variables"
Write-Host "3. Add 3 variables:"
Write-Host "   - FLY_API_TOKEN (from fly.io)"
Write-Host "   - OCR_DATA_ENCRYPTION_KEY (copy above)"
Write-Host "   - SLACK_WEBHOOK_OCR (from Slack)"
Write-Host ""
Write-Host "4. Test deployment:"
Write-Host "   - Go to: CI/CD > Pipelines"
Write-Host "   - Click Play on: ocr_deploy_staging_fly"
Write-Host "   - Wait ~5 minutes"
Write-Host ""
Write-Host "5. Verify:"
Write-Host "   - Health: https://reqsys-api-stg.fly.dev/health"
Write-Host "   - Readiness: https://reqsys-api-stg.fly.dev/v1/ocr/readiness"
Write-Host ""

Write-Host "===================================================================="
Write-Host "Documentation"
Write-Host "===================================================================="
Write-Host ""
Write-Host "- Deployment Strategy: docs/architecture/ocr-deployment-strategy.md"
Write-Host "- Migration Plan: docs/architecture/ocr-pc24x7-migration-plan.md"
Write-Host "- Action Items: docs/runbooks/ocr-deployment-action-items.md"
Write-Host "- Deploy Job: gitlab/ci/ocr-deploy-staging.yml"
Write-Host ""
