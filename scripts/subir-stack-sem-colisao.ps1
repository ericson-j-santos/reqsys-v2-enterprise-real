param(
    [string]$ProjetoDir = "",
    [int]$GatewayPort = 8083,
    [switch]$ForcarAjusteGateway
)

$ErrorActionPreference = 'Stop'

function Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Info([string]$Message) {
    Write-Host "[info] $Message" -ForegroundColor Gray
}

function Ok([string]$Message) {
    Write-Host "[ok]   $Message" -ForegroundColor Green
}

function Warn([string]$Message) {
    Write-Host "[warn] $Message" -ForegroundColor Yellow
}

function Fail([string]$Message) {
    Write-Host "[fail] $Message" -ForegroundColor Red
}

function Test-DockerDisponivel {
    try {
        $null = docker version --format '{{.Server.Version}}' 2>$null
        return $true
    }
    catch {
        return $false
    }
}

function Get-ProcessoPorta([int]$Porta) {
    $conn = Get-NetTCPConnection -State Listen -LocalPort $Porta -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $conn) {
        return $null
    }

    $procNome = 'Desconhecido'
    try {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction Stop
        $procNome = $proc.ProcessName
    }
    catch {
        # Keep fallback name.
    }

    return [PSCustomObject]@{
        Porta = $Porta
        PID = $conn.OwningProcess
        Processo = $procNome
    }
}

function Ler-Env([string]$EnvPath) {
    $map = @{}
    foreach ($line in Get-Content $EnvPath) {
        if ($line -match '^\s*#') { continue }
        if ($line -match '^\s*$') { continue }
        if ($line -match '^\s*([^=\s]+)\s*=\s*(.*)\s*$') {
            $map[$matches[1]] = $matches[2]
        }
    }
    return $map
}

function Set-EnvValue([string]$EnvPath, [string]$Key, [string]$Value) {
    $lines = Get-Content $EnvPath
    $updated = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*$([Regex]::Escape($Key))\s*=") {
            $lines[$i] = "$Key=$Value"
            $updated = $true
            break
        }
    }

    if (-not $updated) {
        $lines += "$Key=$Value"
    }

    Set-Content -Path $EnvPath -Value $lines -Encoding UTF8
}

function Test-Url([string]$Nome, [string]$Url, [int[]]$StatusAceitos) {
    try {
        $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 8
        $status = [int]$resp.StatusCode
        if ($StatusAceitos -contains $status) {
            Ok "$Nome -> $Url (HTTP $status)"
            return $true
        }

        Fail "$Nome -> $Url retornou HTTP $status"
        return $false
    }
    catch {
        $status = $null
        try { $status = [int]$_.Exception.Response.StatusCode } catch {}

        if ($null -ne $status -and $StatusAceitos -contains $status) {
            Ok "$Nome -> $Url (HTTP $status, esperado para este endpoint)"
            return $true
        }

        $msg = $_.Exception.Message
        if ($null -ne $status) {
            Fail "$Nome -> $Url falhou (HTTP $status): $msg"
        }
        else {
            Fail "$Nome -> $Url falhou: $msg"
        }
        return $false
    }
}

if ([string]::IsNullOrWhiteSpace($ProjetoDir)) {
    $ProjetoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

$composePath = Join-Path $ProjetoDir 'docker-compose.yml'
$envPath = Join-Path $ProjetoDir '.env'

if (-not (Test-Path $composePath)) {
    throw "docker-compose.yml nao encontrado em: $ProjetoDir"
}
if (-not (Test-Path $envPath)) {
    throw ".env nao encontrado em: $ProjetoDir"
}

Step "Projeto: $ProjetoDir"
Set-Location $ProjetoDir

$envMap = Ler-Env -EnvPath $envPath
$gatewayAtual = 8082
if ($envMap.ContainsKey('GATEWAY_PORT') -and $envMap['GATEWAY_PORT'] -match '^\d+$') {
    $gatewayAtual = [int]$envMap['GATEWAY_PORT']
}

$backendPort = 8210
if ($envMap.ContainsKey('BACKEND_PORT') -and $envMap['BACKEND_PORT'] -match '^\d+$') {
    $backendPort = [int]$envMap['BACKEND_PORT']
}

$colisao = $false
$owner = Get-ProcessoPorta -Porta $gatewayAtual
if ($owner -and $owner.Processo -ieq 'System') {
    $colisao = $true
    Warn "Porta $gatewayAtual ocupada por System (HTTP.SYS/SSRS provavel)."
}
elseif ($owner) {
    Warn "Porta $gatewayAtual ocupada por processo $($owner.Processo) (PID $($owner.PID))."
}
else {
    Info "Porta $gatewayAtual livre no host."
}

$novoGateway = $gatewayAtual
if ($ForcarAjusteGateway -or $colisao) {
    $novoGateway = $GatewayPort
    Step "Ajustando apenas GATEWAY_PORT no .env ($gatewayAtual -> $novoGateway)"
    $backup = "$envPath.bak.$(Get-Date -Format 'yyyyMMddHHmmss')"
    Copy-Item $envPath $backup
    Set-EnvValue -EnvPath $envPath -Key 'GATEWAY_PORT' -Value "$novoGateway"
    Ok "Arquivo .env atualizado. Backup: $backup"
}
else {
    Info "Sem ajuste de GATEWAY_PORT. Valor atual: $gatewayAtual"
}

Step "Validando Docker"
$dockerOk = Test-DockerDisponivel
if (-not $dockerOk) {
    Warn "Docker ainda indisponivel. Nao foi possivel subir o compose agora."
    Warn "Quando o Docker voltar, execute novamente este script."
    exit 2
}

Ok "Docker disponivel."

Step "Subindo stack"
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao executar docker compose up -d"
}

Step "Status dos containers"
docker compose ps

$gatewayFinal = $novoGateway
$ssrsBase = 'http://localhost:8082/ReportServer'
if ($envMap.ContainsKey('SSRS_BASE_URL') -and -not [string]::IsNullOrWhiteSpace($envMap['SSRS_BASE_URL'])) {
    $ssrsBase = $envMap['SSRS_BASE_URL']
}

Step "Validacao em sequencia (frontend -> api -> ssrs)"
$okFrontend = Test-Url -Nome 'Frontend via gateway' -Url "http://reqsys.local:$gatewayFinal/" -StatusAceitos @(200)
$okApi = Test-Url -Nome 'API health' -Url "http://api.reqsys.local:$backendPort/health" -StatusAceitos @(200)
$okSsrs = Test-Url -Nome 'SSRS' -Url $ssrsBase -StatusAceitos @(200, 401)

Step "Resumo"
if ($okFrontend -and $okApi -and $okSsrs) {
    Ok "Tudo validado sem colisao de porta."
    Ok "Frontend: http://reqsys.local:$gatewayFinal/"
    Ok "API:      http://api.reqsys.local:$backendPort/health"
    Ok "SSRS:     $ssrsBase"
    exit 0
}

Fail "Ha falhas de validacao. Revise os logs acima."
exit 1
