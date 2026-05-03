param(
    [string]$ProjetoDir = ""
)

$ErrorActionPreference = 'Stop'

function Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

if ([string]::IsNullOrWhiteSpace($ProjetoDir)) {
    $ProjetoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

if (-not (Test-Path (Join-Path $ProjetoDir 'docker-compose.yml'))) {
    throw "docker-compose.yml nao encontrado em: $ProjetoDir"
}

Step "Projeto: $ProjetoDir"
Set-Location $ProjetoDir

Step "Derrubando stack e removendo volumes"
docker compose down -v --remove-orphans

Step "Build sem cache (api, frontend, nginx)"
docker compose build --no-cache

Step "Subindo stack"
docker compose up -d

Step "Status dos containers"
docker compose ps

Step "Ultimos logs do frontend"
docker compose logs --no-color --tail=80 frontend

Step "Ultimos logs do nginx"
docker compose logs --no-color --tail=40 nginx

Write-Host "`nStack reiniciada com sucesso." -ForegroundColor Green