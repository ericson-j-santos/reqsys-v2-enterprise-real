param(
    [string]$ProjetoDir = "",
    [string]$TaskName = "ReqSys - Subir Docker Stack",
    [ValidateSet('AtStartup', 'AtLogon', 'Daily')]
    [string]$TriggerType = 'AtStartup',
    [int]$Hora = 8,
    [int]$Minuto = 0,
    [int]$GatewayPort = 8083,
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

if ([string]::IsNullOrWhiteSpace($ProjetoDir)) {
    $ProjetoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

$subirScript = Join-Path $PSScriptRoot 'subir-stack-sem-colisao.ps1'
if (-not (Test-Path $subirScript)) {
    throw "Script de subida nao encontrado: $subirScript"
}

if (-not (Test-Path (Join-Path $ProjetoDir 'docker-compose.yml'))) {
    throw "docker-compose.yml nao encontrado em: $ProjetoDir"
}

$quotedProjetoDir = '"' + $ProjetoDir + '"'
$quotedSubirScript = '"' + $subirScript + '"'

# Usa cmd /c + cd /d para garantir diretorio correto quando executado pelo Scheduler
$runner = "cd /d $quotedProjetoDir && powershell.exe -NoProfile -ExecutionPolicy Bypass -File $quotedSubirScript -ProjetoDir $quotedProjetoDir -GatewayPort $GatewayPort"

Step "Projeto alvo: $ProjetoDir"

if ($Desagendar) {
    Step "Removendo tarefa agendada"
    schtasks /Delete /TN "$TaskName" /F | Out-Null
    Ok "Tarefa removida: $TaskName"
    exit 0
}

Step "Criando/atualizando tarefa agendada"

# /RL HIGHEST reduz falhas por permissao para docker service.
if ($TriggerType -eq 'AtStartup') {
    schtasks /Create /TN "$TaskName" /SC ONSTART /TR "cmd.exe /c $runner" /RU "$env:USERNAME" /RL HIGHEST /F | Out-Null
}
elseif ($TriggerType -eq 'AtLogon') {
    schtasks /Create /TN "$TaskName" /SC ONLOGON /TR "cmd.exe /c $runner" /RU "$env:USERNAME" /RL HIGHEST /F | Out-Null
}
else {
    $hora = '{0:d2}:{1:d2}' -f $Hora, $Minuto
    schtasks /Create /TN "$TaskName" /SC DAILY /ST $hora /TR "cmd.exe /c $runner" /RU "$env:USERNAME" /RL HIGHEST /F | Out-Null
}

Ok "Tarefa registrada: $TaskName"
Ok "Trigger: $TriggerType"

if ($ExecutarAgora) {
    Step "Executando tarefa agora"
    schtasks /Run /TN "$TaskName" | Out-Null
    Ok "Disparo manual enviado para o Task Scheduler"
}

Step "Como validar"
Write-Host "1) Abra Task Scheduler e procure por: $TaskName"
Write-Host "2) Verifique Last Run Result"
Write-Host "3) Rode: schtasks /Query /TN \"$TaskName\" /V /FO LIST"
Write-Host "4) Verifique containers: docker compose -f docker-compose.yml ps"
