param(
    [string]$ProjetoDir = "",
    [string]$TaskName = "ReqSys - Subir Docker Stack",
    [ValidateSet('AtStartup', 'AtLogon', 'Daily')]
    [string]$TriggerType = 'AtLogon',
    [int]$Hora = 8,
    [int]$Minuto = 0,
    [int]$GatewayPort = 8083,
    [switch]$HabilitarAgendamento,
    [switch]$ExecutarAgora,
    [switch]$Desagendar
)

$ErrorActionPreference = 'Stop'

function Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Ok([string]$Message) {
    Write-Host "[ok]   $Message" -ForegroundColor Green
}

function Warn([string]$Message) {
    Write-Host "[warn] $Message" -ForegroundColor Yellow
}

if ($Desagendar) {
    Step "Removendo tarefa agendada"
    schtasks /Query /TN "$TaskName" *> $null
    if ($LASTEXITCODE -ne 0) {
        Warn "Tarefa nao encontrada; nada para remover: $TaskName"
        exit 0
    }

    schtasks /Delete /TN "$TaskName" /F | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao remover tarefa agendada: $TaskName"
    }

    Ok "Tarefa removida: $TaskName"
    exit 0
}

if (-not $HabilitarAgendamento) {
    throw "Agendamento bloqueado por padrao. Informe -HabilitarAgendamento explicitamente."
}

if ([string]::IsNullOrWhiteSpace($ProjetoDir)) {
    $ProjetoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

$preflightScript = Join-Path $PSScriptRoot 'testar-preflight-docker.ps1'
if (-not (Test-Path -LiteralPath $preflightScript -PathType Leaf)) {
    throw "Preflight Docker nao encontrado: $preflightScript"
}
$preflight = & $preflightScript -ProjetoDir $ProjetoDir -Ambiente dev -ExigirEnv -Quiet
$ProjetoDir = $preflight.ProjetoDir

$subirScript = Join-Path $ProjetoDir 'scripts\subir-stack-sem-colisao.ps1'
if (-not (Test-Path -LiteralPath $subirScript -PathType Leaf)) {
    throw "Script de subida nao encontrado: $subirScript"
}

$quotedProjetoDir = '"' + $ProjetoDir + '"'
$quotedSubirScript = '"' + $subirScript + '"'

# Usa cmd /c + cd /d para garantir diretorio correto quando executado pelo Scheduler
$runner = "cd /d $quotedProjetoDir && powershell.exe -NoProfile -ExecutionPolicy Bypass -File $quotedSubirScript -ProjetoDir $quotedProjetoDir -GatewayPort $GatewayPort"

Step "Projeto alvo: $ProjetoDir"

Step "Criando/atualizando tarefa agendada"

# Docker Desktop roda no contexto do usuario; privilegio elevado nao e necessario.
if ($TriggerType -eq 'AtStartup') {
    schtasks /Create /TN "$TaskName" /SC ONSTART /TR "cmd.exe /c $runner" /RU "$env:USERNAME" /RL LIMITED /F | Out-Null
}
elseif ($TriggerType -eq 'AtLogon') {
    schtasks /Create /TN "$TaskName" /SC ONLOGON /TR "cmd.exe /c $runner" /RU "$env:USERNAME" /RL LIMITED /F | Out-Null
}
else {
    $hora = '{0:d2}:{1:d2}' -f $Hora, $Minuto
    schtasks /Create /TN "$TaskName" /SC DAILY /ST $hora /TR "cmd.exe /c $runner" /RU "$env:USERNAME" /RL LIMITED /F | Out-Null
}

if ($LASTEXITCODE -ne 0) {
    throw "Falha ao criar ou atualizar tarefa agendada: $TaskName"
}

Ok "Tarefa registrada: $TaskName"
Ok "Trigger: $TriggerType"

if ($ExecutarAgora) {
    Step "Executando tarefa agora"
    schtasks /Run /TN "$TaskName" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Tarefa registrada, mas o disparo manual falhou: $TaskName"
    }
    Ok "Disparo manual enviado para o Task Scheduler"
}

Step "Como validar"
Write-Host "1) Abra Task Scheduler e procure por: $TaskName"
Write-Host "2) Verifique Last Run Result"
Write-Host "3) Rode: schtasks /Query /TN \"$TaskName\" /V /FO LIST"
Write-Host "4) Verifique containers: docker compose -p reqsys-dev -f docker-compose.yml -f docker-compose.dev.yml ps"
