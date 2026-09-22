param(
    [string]$ProjetoDir = "",
    [switch]$SubirStackReqSys,
    [int]$TimeoutSegundos = 120
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

function Test-DockerEngine {
    try {
        $null = docker version --format '{{.Server.Version}}' 2>$null
        return $true
    }
    catch {
        return $false
    }
}

function Test-IsAdmin {
    try {
        $current = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($current)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    }
    catch {
        return $false
    }
}

if ([string]::IsNullOrWhiteSpace($ProjetoDir)) {
    $ProjetoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

$composePath = Join-Path $ProjetoDir 'docker-compose.yml'

Step "1) Teste inicial do Docker Engine"
if (Test-DockerEngine) {
    Ok "Docker ja esta respondendo."
}
else {
    Warn "Docker nao esta respondendo. Tentando recuperacao segura..."

    Step "2) Garantir servico com.docker.service"
    $isAdmin = Test-IsAdmin
    if (-not $isAdmin) {
        Warn "Sessao atual nao esta elevada (Administrador)."
    }
    try {
        $svc = Get-Service -Name 'com.docker.service' -ErrorAction Stop
        if ($svc.Status -ne 'Running') {
            Start-Service -Name 'com.docker.service'
            Ok "Servico com.docker.service iniciado."
        }
        else {
            Info "Servico com.docker.service ja estava em execucao."
        }
    }
    catch {
        Warn "Nao foi possivel consultar/iniciar com.docker.service (pode exigir admin)."
        Warn "Em PowerShell como Administrador, execute: Start-Service com.docker.service"
    }

    Step "3) Garantir processo Docker Desktop"
    $desktopProc = Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue
    if (-not $desktopProc) {
        $desktopExe = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
        if (Test-Path $desktopExe) {
            Start-Process -FilePath $desktopExe | Out-Null
            Ok "Docker Desktop iniciado."
        }
        else {
            Warn "Docker Desktop.exe nao encontrado em $desktopExe"
        }
    }
    else {
        Info "Docker Desktop ja estava em execucao."
    }

    Step "4) Aguardar Engine responder"
    $inicio = Get-Date
    $up = $false
    while (-not $up) {
        $up = Test-DockerEngine
        if ($up) { break }

        $segundos = [int]((Get-Date) - $inicio).TotalSeconds
        if ($segundos -ge $TimeoutSegundos) {
            break
        }

        Start-Sleep -Seconds 4
    }

    if (-not (Test-DockerEngine)) {
        Fail "Docker nao respondeu dentro de $TimeoutSegundos segundos."
        exit 2
    }

    Ok "Docker voltou a responder."
}

Step "5) Sanidade do Docker"
try {
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}
catch {
    Warn "Nao foi possivel listar containers: $($_.Exception.Message)"
}

if ($SubirStackReqSys) {
    if (-not (Test-Path $composePath)) {
        Fail "docker-compose.yml nao encontrado em $ProjetoDir"
        exit 3
    }

    Step "6) Subir stack do ReqSys"
    Set-Location $ProjetoDir
    docker compose up -d
    if ($LASTEXITCODE -ne 0) {
        Fail "Falha no docker compose up -d"
        exit 4
    }

    Ok "Stack do ReqSys iniciada."
}

Step "Concluido"
Ok "Reinicio seguro finalizado sem limpeza destrutiva."
exit 0
