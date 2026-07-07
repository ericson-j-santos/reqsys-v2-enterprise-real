# Automatiza a descoberta/captura das credenciais Graph para a mensageria Teams
# (AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, TEAMS_GRAPH_APP_SERVICE_PRINCIPAL_ID)
# e, opcionalmente, resolve a pendencia de permissao de aplicacao no Azure AD.
#
# Requer: Azure CLI (az) instalado e autenticado (`az login`) com uma conta que
# tenha direitos sobre o app registration (dono/Application Administrator) e,
# para -GrantPermissions, direitos para conceder consentimento de admin
# (Global Administrator / Privileged Role Administrator / Cloud Application Administrator).
#
# Uso:
#   .\scripts\configurar-teams-graph.ps1                              # so relatorio (read-only, seguro)
#   .\scripts\configurar-teams-graph.ps1 -UpdateEnvFile                # + grava valores nao-sensiveis no .env
#   .\scripts\configurar-teams-graph.ps1 -GrantPermissions             # + adiciona Chat.Create/Chat.ReadWrite.All e concede admin consent
#   .\scripts\configurar-teams-graph.ps1 -CreateSecret -UpdateEnvFile  # + gera novo client secret e grava no .env (nunca impresso no console)
#
# O script e idempotente: rodar de novo so relata o que ja esta OK.

param(
    [string]$AppDisplayName = "ReqSys Enterprise",
    [string]$AppId = "",
    [switch]$GrantPermissions,
    [switch]$CreateSecret,
    [switch]$UpdateEnvFile
)

# Continue (nao Stop): comandos nativos do az escrevem avisos em stderr (ex.: o
# aviso de credential reset) que o PowerShell 5.1 converte em ErrorRecord: com
# ErrorActionPreference=Stop isso aborta o script no meio de um comando ja
# executado (ex.: secret ja criado no Azure, porem nunca capturado/gravado).
$ErrorActionPreference = "Continue"
$MicrosoftGraphAppId = "00000003-0000-0000-c000-000000000000"

# App-only (nao existe "ChatMessage.Send" como permissao de aplicacao no Graph;
# enviar mensagem app-only exige Chat.ReadWrite.All, que e uma permissao
# altamente privilegiada e sujeita a revisao adicional da Microsoft para uso
# em producao fora do tenant de desenvolvimento).
$PermissoesNecessarias = @(
    @{ Value = "Chat.Create"; Id = "d9c48af6-9ad9-47ad-82c3-63757137b9af" }
    @{ Value = "Chat.ReadWrite.All"; Id = "294ce7c9-31ba-490a-ad7d-97a7d075e4ed" }
)

function Write-Secao($texto) {
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host " $texto" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
}

Write-Secao "Teams via Graph API - captura de credenciais e diagnostico de permissoes"

# ---- 0. Pre-requisitos ----
$azVersion = az version 2>$null
if (-not $azVersion) {
    Write-Host "[ERRO] Azure CLI (az) nao encontrado no PATH. Instale: https://learn.microsoft.com/cli/azure/install-azure-cli" -ForegroundColor Red
    exit 1
}

$conta = az account show 2>$null | ConvertFrom-Json
if (-not $conta) {
    Write-Host "[ERRO] Nao autenticado no Azure CLI. Rode 'az login' primeiro." -ForegroundColor Red
    exit 1
}
Write-Host "  Logado como: $($conta.user.name)"
Write-Host "  Tenant: $($conta.tenantId)"

# ---- 1. Localizar app registration ----
Write-Host ""
Write-Host "[1/4] Localizando app registration..." -ForegroundColor Yellow

if ($AppId) {
    $app = az ad app show --id $AppId 2>$null | ConvertFrom-Json
} else {
    $apps = az ad app list --display-name $AppDisplayName 2>$null | ConvertFrom-Json
    if ($apps.Count -eq 0) {
        Write-Host "[ERRO] Nenhum app com display name '$AppDisplayName' encontrado. Informe -AppId explicitamente." -ForegroundColor Red
        exit 1
    }
    if ($apps.Count -gt 1) {
        Write-Host "[AVISO] Mais de um app encontrado com esse nome; usando o primeiro (appId=$($apps[0].appId))." -ForegroundColor Yellow
    }
    $app = $apps[0]
}

$clientId = $app.appId
$tenantId = $conta.tenantId
Write-Host "  App: $($app.displayName)  (AZURE_CLIENT_ID=$clientId)" -ForegroundColor Green

$sp = az ad sp show --id $clientId 2>$null | ConvertFrom-Json
if (-not $sp) {
    Write-Host "[ERRO] Service principal nao encontrado para esse app (nao foi consentido ainda no tenant)." -ForegroundColor Red
    exit 1
}
$servicePrincipalId = $sp.id
Write-Host "  Service Principal Object ID (TEAMS_GRAPH_APP_SERVICE_PRINCIPAL_ID)=$servicePrincipalId" -ForegroundColor Green

# ---- 2. Diagnosticar permissoes concedidas ----
Write-Host ""
Write-Host "[2/4] Verificando permissoes de aplicacao concedidas (admin consent)..." -ForegroundColor Yellow

$graphSpId = az ad sp show --id $MicrosoftGraphAppId --query id -o tsv
$assignments = az rest --method GET --url "https://graph.microsoft.com/v1.0/servicePrincipals/$servicePrincipalId/appRoleAssignments" 2>$null | ConvertFrom-Json
$concedidas = $assignments.value | ForEach-Object { $_.appRoleId }

$faltantes = @()
foreach ($perm in $PermissoesNecessarias) {
    if ($concedidas -contains $perm.Id) {
        Write-Host "  [OK] $($perm.Value) ja concedida" -ForegroundColor Green
    } else {
        Write-Host "  [FALTA] $($perm.Value) nao concedida" -ForegroundColor Red
        $faltantes += $perm
    }
}

# ---- 3. Resolver pendencia (opcional, requer -GrantPermissions) ----
if ($faltantes.Count -gt 0) {
    if ($GrantPermissions) {
        Write-Host ""
        Write-Host "[3/4] Concedendo permissoes faltantes (grava no manifesto + admin consent)..." -ForegroundColor Yellow
        foreach ($perm in $faltantes) {
            Write-Host "  Adicionando $($perm.Value) ao requiredResourceAccess..."
            az ad app permission add --id $clientId --api $MicrosoftGraphAppId --api-permissions "$($perm.Id)=Role" | Out-Null

            Write-Host "  Concedendo admin consent (appRoleAssignment) para $($perm.Value)..."
            $body = @{
                principalId = $servicePrincipalId
                resourceId  = $graphSpId
                appRoleId   = $perm.Id
            } | ConvertTo-Json -Compress

            $tmpFile = New-TemporaryFile
            $body | Set-Content -Path $tmpFile -Encoding UTF8
            try {
                az rest --method POST `
                    --url "https://graph.microsoft.com/v1.0/servicePrincipals/$servicePrincipalId/appRoleAssignments" `
                    --body "@$tmpFile" `
                    --headers "Content-Type=application/json" | Out-Null
                Write-Host "  [OK] $($perm.Value) concedida" -ForegroundColor Green
            } catch {
                Write-Host "  [ERRO] Falha ao conceder $($perm.Value): $($_.Exception.Message)" -ForegroundColor Red
                Write-Host "         Provavel causa: sua conta nao tem papel Global Administrator / Privileged Role Administrator / Cloud Application Administrator." -ForegroundColor Yellow
                Write-Host "         Alternativa: peça a um admin do tenant para conceder no Portal (Entra ID > Enterprise Applications > $($app.displayName) > API permissions > Grant admin consent)." -ForegroundColor Yellow
            } finally {
                Remove-Item $tmpFile -ErrorAction SilentlyContinue
            }
        }
    } else {
        Write-Host ""
        Write-Host "[3/4] Permissoes faltantes detectadas. Rode com -GrantPermissions para tentar conceder automaticamente" -ForegroundColor Yellow
        Write-Host "      (precisa de papel de admin no Azure AD para o admin consent funcionar)." -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "[3/4] Todas as permissoes necessarias ja estao concedidas." -ForegroundColor Green
}

# ---- 4. Client secret + .env ----
Write-Host ""
Write-Host "[4/4] Client secret e .env..." -ForegroundColor Yellow

$root = Split-Path $PSScriptRoot -Parent
$envFile = Join-Path $root ".env"
$novoSecret = $null

if ($CreateSecret) {
    Write-Host "  Gerando novo client secret (valido 12 meses)..."
    $cred = az ad app credential reset --id $clientId --years 1 --append 2>$null | ConvertFrom-Json
    if ($cred -and $cred.password) {
        $novoSecret = $cred.password
        Write-Host "  [OK] Secret gerado (nao sera impresso no console)." -ForegroundColor Green
    } else {
        Write-Host "  [ERRO] Falha ao gerar o client secret." -ForegroundColor Red
    }
} else {
    Write-Host "  (pulando criacao de secret; rode com -CreateSecret se AZURE_CLIENT_SECRET ainda nao existir)"
}

if ($UpdateEnvFile) {
    if (-not (Test-Path $envFile)) {
        New-Item -ItemType File -Path $envFile | Out-Null
    }
    $content = Get-Content $envFile -Raw -ErrorAction SilentlyContinue
    if (-not $content) { $content = "" }

    function Set-EnvVar([string]$conteudo, [string]$chave, [string]$valor) {
        if ($conteudo -match "(?m)^$chave=.*$") {
            return ($conteudo -replace "(?m)^$chave=.*$", "$chave=$valor")
        }
        return $conteudo.TrimEnd() + "`n$chave=$valor"
    }

    $content = Set-EnvVar $content "AZURE_TENANT_ID" $tenantId
    $content = Set-EnvVar $content "AZURE_CLIENT_ID" $clientId
    $content = Set-EnvVar $content "TEAMS_GRAPH_APP_SERVICE_PRINCIPAL_ID" $servicePrincipalId
    if ($novoSecret) {
        $content = Set-EnvVar $content "AZURE_CLIENT_SECRET" $novoSecret
    }
    $content | Set-Content $envFile -Encoding UTF8 -NoNewline
    Write-Host "  [OK] .env atualizado (AZURE_TENANT_ID, AZURE_CLIENT_ID, TEAMS_GRAPH_APP_SERVICE_PRINCIPAL_ID$(if ($novoSecret) { ', AZURE_CLIENT_SECRET' }))" -ForegroundColor Green
} else {
    Write-Host "  (pulando gravacao no .env; rode com -UpdateEnvFile para persistir os valores capturados)"
}

Write-Secao "Resumo"
Write-Host "  AZURE_TENANT_ID                      = $tenantId"
Write-Host "  AZURE_CLIENT_ID                      = $clientId"
Write-Host "  TEAMS_GRAPH_APP_SERVICE_PRINCIPAL_ID  = $servicePrincipalId"
Write-Host "  AZURE_CLIENT_SECRET                  = $(if ($novoSecret) { '[gerado agora - ver .env]' } elseif ($CreateSecret) { '[FALHOU]' } else { '[nao gerado nesta execucao]' })"
Write-Host "  Permissoes Chat.Create/Chat.ReadWrite.All: $(if ($faltantes.Count -eq 0) { 'OK' } else { 'PENDENTE' })"
Write-Host ""
