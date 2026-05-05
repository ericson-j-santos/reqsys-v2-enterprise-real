param(
    [string]$ProjetoDir = ""
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($ProjetoDir)) {
    $ProjetoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

$backendDir = Join-Path $ProjetoDir 'backend'
$pythonExe = Join-Path $backendDir '.venv\Scripts\python.exe'
$scriptPy = Join-Path $backendDir 'scripts_audit\gerar_snapshot_qualidade_ia.py'
$logDir = Join-Path $backendDir 'scripts_audit\logs'

if (-not (Test-Path $pythonExe)) {
    throw "Python da venv nao encontrado em: $pythonExe"
}
if (-not (Test-Path $scriptPy)) {
    throw "Script de snapshot nao encontrado em: $scriptPy"
}
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$logPath = Join-Path $logDir ("snapshot-qualidade-ia-" + (Get-Date -Format 'yyyyMMdd') + '.log')

Push-Location $backendDir
try {
    & $pythonExe $scriptPy *>> $logPath
    Write-Host "Snapshot de qualidade IA executado com sucesso. Log: $logPath" -ForegroundColor Green
}
finally {
    Pop-Location
}
