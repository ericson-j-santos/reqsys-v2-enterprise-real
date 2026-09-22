[CmdletBinding()]
param(
    [string]$SSRSBaseUrl,
    [string]$SqlServerHost,          # hostname ou IP do SQL Server (quando DATABASE_URL nao esta no .env)
    [string]$SSRSReportsPath = "ReqSys",
    [string]$SSRSReportNames = "AtvIndividual,Cracha,CracháAula2,RelatorioDetalhado,RelatorioDetalhadoAula2",
    [string]$EnvFilePath = ".env",
    [switch]$RestartStack,
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"

function Resolve-ProjectRoot {
    $scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $PSCommandPath }
    return (Resolve-Path (Join-Path $scriptDir "..")).Path
}

function Read-EnvLines {
    param([string]$Path)
    if (Test-Path $Path) {
        return [System.Collections.Generic.List[string]](Get-Content $Path)
    }
    return [System.Collections.Generic.List[string]]::new()
}

function Get-EnvValue {
    param([System.Collections.Generic.List[string]]$Lines, [string]$Key)
    foreach ($line in $Lines) {
        if ($line -match "^\s*$([Regex]::Escape($Key))=(.*)$") {
            return $Matches[1].Trim()
        }
    }
    return $null
}

function Set-EnvKey {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string]$Key,
        [string]$Value
    )

    $pattern = "^\s*" + [Regex]::Escape($Key) + "="
    $updated = $false
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match $pattern) {
            $Lines[$i] = "$Key=$Value"
            $updated = $true
            break
        }
    }

    if (-not $updated) {
        $Lines.Add("$Key=$Value")
    }
}

function Test-UrlReachability {
    param([string]$Url)

    try {
        $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 8
        return @{ Reachable = $true; StatusCode = [int]$resp.StatusCode; Detail = "OK" }
    }
    catch {
        $msg = $_.Exception.Message
        return @{ Reachable = $false; StatusCode = $null; Detail = $msg }
    }
}

function Get-SqlServerHostFromDatabaseUrl {
    param([string]$DatabaseUrl)
    # Suporta formatos:
    #   mssql+pyodbc://user:pass@HOSTNAME/db?...
    #   mssql+pyodbc://user:pass@HOSTNAME:PORT/db?...
    #   mssql+pyodbc://user:pass@HOSTNAME\INSTANCE/db?...
    if ($DatabaseUrl -match '://[^@]+@([^/\\:?]+)') {
        return $Matches[1]
    }
    return $null
}

$projectRoot = Resolve-ProjectRoot
Set-Location $projectRoot

# --- Auto-detectar SSRS_BASE_URL ---
if (-not $SSRSBaseUrl) {
    $envPath0 = if ([System.IO.Path]::IsPathRooted($EnvFilePath)) { $EnvFilePath } else { Join-Path $projectRoot $EnvFilePath }
    $linesPreview = Read-EnvLines -Path $envPath0

    # 1. -SqlServerHost passado direto
    if ($SqlServerHost) {
        $SSRSBaseUrl = "http://$SqlServerHost/ReportServer"
        Write-Host "[Auto-detect] -SqlServerHost informado: $SqlServerHost"
        Write-Host "[Auto-detect] SSRS_BASE_URL: $SSRSBaseUrl"
    }

    # 2. DATABASE_URL do ambiente do shell
    if (-not $SSRSBaseUrl) {
        $dbUrl = [System.Environment]::GetEnvironmentVariable("DATABASE_URL")
        if ($dbUrl) {
            $sqlHost = Get-SqlServerHostFromDatabaseUrl -DatabaseUrl $dbUrl
            if ($sqlHost) {
                $SSRSBaseUrl = "http://$sqlHost/ReportServer"
                Write-Host "[Auto-detect] DATABASE_URL (ambiente): host=$sqlHost"
                Write-Host "[Auto-detect] SSRS_BASE_URL: $SSRSBaseUrl"
            }
        }
    }

    # 3. DATABASE_URL no arquivo .env
    if (-not $SSRSBaseUrl) {
        $dbUrl = Get-EnvValue -Lines $linesPreview -Key "DATABASE_URL"
        if ($dbUrl) {
            $sqlHost = Get-SqlServerHostFromDatabaseUrl -DatabaseUrl $dbUrl
            if ($sqlHost) {
                $SSRSBaseUrl = "http://$sqlHost/ReportServer"
                Write-Host "[Auto-detect] DATABASE_URL (.env): host=$sqlHost"
                Write-Host "[Auto-detect] SSRS_BASE_URL: $SSRSBaseUrl"
            }
        }
    }

    # 4. Perguntar interativamente
    if (-not $SSRSBaseUrl) {
        Write-Host ""
        Write-Host "Nao foi possivel detectar o servidor automaticamente."
        Write-Host "O SSRS esta no mesmo servidor que o SQL Server."
        Write-Host "Opcoes:"
        Write-Host "  a) Passe -SqlServerHost NOME_DO_SERVIDOR"
        Write-Host "  b) Passe -SSRSBaseUrl http://SERVIDOR/ReportServer"
        Write-Host "  c) Informe agora:"
        $SqlServerHost = Read-Host "Hostname ou IP do servidor SQL Server/SSRS"
        if ($SqlServerHost) {
            $SSRSBaseUrl = "http://$SqlServerHost/ReportServer"
        }
    }
}

if (-not [Uri]::IsWellFormedUriString($SSRSBaseUrl, [UriKind]::Absolute)) {
    throw "SSRS_BASE_URL invalido: $SSRSBaseUrl"
}

$check = Test-UrlReachability -Url $SSRSBaseUrl
Write-Host "[SSRS] URL: $SSRSBaseUrl"
Write-Host "[SSRS] Reachable: $($check.Reachable)"
if ($check.StatusCode) {
    Write-Host "[SSRS] HTTP: $($check.StatusCode)"
}
if (-not $check.Reachable) {
    Write-Host "[SSRS] Detalhe: $($check.Detail)"
}

if ($ValidateOnly) {
    Write-Host "Modo ValidateOnly: nenhuma alteracao em arquivo foi feita."
    exit 0
}

$envPath = if ([System.IO.Path]::IsPathRooted($EnvFilePath)) { $EnvFilePath } else { Join-Path $projectRoot $EnvFilePath }
$lines = Read-EnvLines -Path $envPath

Set-EnvKey -Lines $lines -Key "SSRS_BASE_URL" -Value $SSRSBaseUrl
Set-EnvKey -Lines $lines -Key "SSRS_REPORTS_PATH" -Value $SSRSReportsPath
Set-EnvKey -Lines $lines -Key "SSRS_REPORT_NAMES" -Value $SSRSReportNames

$dir = Split-Path -Parent $envPath
if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir | Out-Null
}

$lines | Set-Content -Path $envPath -Encoding UTF8
Write-Host "Arquivo atualizado: $envPath"

if ($RestartStack) {
    Write-Host "Reiniciando stack Docker..."
    docker compose up -d --build

    Write-Host "Validando endpoint da integracao SSRS..."
    try {
        $endpoint = "http://reqsys.localtest.me:8082/api/v1/relatorios/ssrs"
        $content = Invoke-WebRequest -Uri $endpoint -UseBasicParsing -TimeoutSec 8
        Write-Host "Endpoint OK: $($content.StatusCode)"
        Write-Host $content.Content
    }
    catch {
        Write-Host "Falha ao validar endpoint: $($_.Exception.Message)"
    }
}
else {
    Write-Host "Stack nao reiniciada. Use -RestartStack para aplicar agora."
}
