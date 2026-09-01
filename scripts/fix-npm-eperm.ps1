param(
    [string]$FrontendDir = "",
    [switch]$KillVSCode,
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'

function Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Warn([string]$Message) {
    Write-Host "[AVISO] $Message" -ForegroundColor Yellow
}

if ([string]::IsNullOrWhiteSpace($FrontendDir)) {
    $FrontendDir = (Resolve-Path (Join-Path $PSScriptRoot '..\\frontend')).Path
}

if (-not (Test-Path $FrontendDir)) {
    throw "Diretório frontend não encontrado: $FrontendDir"
}

if (-not (Test-Path (Join-Path $FrontendDir 'package.json'))) {
    throw "package.json não encontrado em: $FrontendDir"
}

Step "FrontendDir: $FrontendDir"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm não encontrado no PATH. Instale Node.js (npm) antes de executar este script."
}

Step "Encerrando processos que podem travar node_modules"
Get-Process -Name node -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name npm -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name pnpm -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name yarn -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

if ($KillVSCode) {
    Warn "Fechando VS Code (Code.exe) por solicitação (-KillVSCode)."
    Get-Process -Name Code -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}

Set-Location $FrontendDir

Step "Limpando node_modules e lockfile"
$nodeModules = Join-Path $FrontendDir 'node_modules'
$packageLock = Join-Path $FrontendDir 'package-lock.json'

if (Test-Path $nodeModules) {
    try {
        Remove-Item -Recurse -Force $nodeModules
    }
    catch {
        Warn "Falha ao remover node_modules de primeira. Tentando renomear e remover novamente."
        $tmpName = "node_modules.__old__.$([DateTime]::Now.ToString('yyyyMMddHHmmss'))"
        $tmpPath = Join-Path $FrontendDir $tmpName
        Rename-Item -Path $nodeModules -NewName $tmpName -ErrorAction Stop
        Remove-Item -Recurse -Force $tmpPath -ErrorAction SilentlyContinue
    }
}

if (Test-Path $packageLock) {
    Remove-Item -Force $packageLock
}

Step "Limpando cache npm"
npm cache clean --force

if (-not $SkipInstall) {
    Step "Instalando dependências (npm install)"
    npm install
}
else {
    Warn "-SkipInstall informado: instalação das dependências foi pulada."
}

Write-Host "`nConcluído. Se ainda houver EPERM, execute o PowerShell como Administrador e adicione exceção de antivírus para o diretório do projeto." -ForegroundColor Green
