[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [string]$ProjetoDir = "",
    [switch]$RemoverVolumes
)

$ErrorActionPreference = 'Stop'

function Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Get-CanonicalPath([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw "Caminho de working_dir vazio. Nenhum volume foi removido."
    }

    if (Test-Path -LiteralPath $Path -PathType Container) {
        $fullPath = (Resolve-Path -LiteralPath $Path).Path
    }
    else {
        $fullPath = [System.IO.Path]::GetFullPath($Path)
    }

    return $fullPath.TrimEnd([char[]]@(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    ))
}

function Assert-ComposeWorkingDirectory(
    [string]$ProjectName,
    [string]$ExpectedWorkingDirectory
) {
    $containerIds = @(
        & docker ps --all --quiet --filter "label=com.docker.compose.project=$ProjectName"
    )
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao consultar containers da stack $ProjectName. Nenhum volume foi removido."
    }
    if ($containerIds.Count -eq 0) {
        throw "Nao ha containers da stack $ProjectName para comprovar o working_dir. Nenhum volume foi removido."
    }

    $expectedPath = Get-CanonicalPath -Path $ExpectedWorkingDirectory
    foreach ($containerId in $containerIds) {
        $inspectJson = & docker inspect $containerId
        if ($LASTEXITCODE -ne 0) {
            throw "Falha ao inspecionar ownership do container $containerId. Nenhum volume foi removido."
        }

        $container = @($inspectJson | ConvertFrom-Json)
        if ($container.Count -ne 1) {
            throw "Resposta invalida ao inspecionar ownership do container $containerId. Nenhum volume foi removido."
        }

        $containerName = $container[0].Name.TrimStart('/')
        $workingDirectory = [string]$container[0].Config.Labels.'com.docker.compose.project.working_dir'
        $workingDirectory = $workingDirectory.Trim()
        if ([string]::IsNullOrWhiteSpace($workingDirectory) -or $workingDirectory -eq '<no value>') {
            throw "Container $containerName sem label com.docker.compose.project.working_dir. Nenhum volume foi removido."
        }

        $actualPath = Get-CanonicalPath -Path $workingDirectory
        if (-not [string]::Equals($actualPath, $expectedPath, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Stack $ProjectName pertence a outra copia: $containerName usa '$actualPath', esperado '$expectedPath'. Nenhum volume foi removido."
        }
    }
}

if ([string]::IsNullOrWhiteSpace($ProjetoDir)) {
    $ProjetoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

$preflightScript = Join-Path $PSScriptRoot 'testar-preflight-docker.ps1'
if (-not (Test-Path -LiteralPath $preflightScript -PathType Leaf)) {
    throw "Preflight Docker nao encontrado: $preflightScript"
}
$preflight = & $preflightScript -ProjetoDir $ProjetoDir -Ambiente dev -Quiet
$ProjetoDir = $preflight.ProjetoDir

if (-not $RemoverVolumes) {
    throw "Limpeza destrutiva bloqueada. Informe -RemoverVolumes explicitamente."
}

$projectName = 'reqsys-dev'
$composeArgs = @(
    'compose',
    '--project-directory', $ProjetoDir,
    '--project-name', $projectName,
    '-f', (Join-Path $ProjetoDir 'docker-compose.yml'),
    '-f', (Join-Path $ProjetoDir 'docker-compose.dev.yml')
)

Step "Projeto: $ProjetoDir"

Step "Validando configuracao Compose"
& docker @composeArgs config --quiet
if ($LASTEXITCODE -ne 0) {
    throw "Configuracao Docker Compose dev invalida. Nenhum volume foi removido."
}

Step "Verificando ownership da stack Compose"
Assert-ComposeWorkingDirectory -ProjectName $projectName -ExpectedWorkingDirectory $ProjetoDir

$target = "stack $projectName em $ProjetoDir"
if (-not $PSCmdlet.ShouldProcess($target, 'Derrubar a stack e remover volumes nomeados')) {
    Write-Host "Operacao destrutiva cancelada. Nenhum build ou restart foi executado." -ForegroundColor Yellow
    return
}

Step "Derrubando stack e removendo volumes"
& docker @composeArgs down -v --remove-orphans
if ($LASTEXITCODE -ne 0) { throw "Falha ao derrubar a stack dev." }

Step "Build sem cache (api, frontend, nginx)"
& docker @composeArgs build --no-cache
if ($LASTEXITCODE -ne 0) { throw "Falha no build da stack dev." }

Step "Subindo stack"
& docker @composeArgs up -d --wait --wait-timeout 120
if ($LASTEXITCODE -ne 0) { throw "Falha ao iniciar a stack dev ou aguardar servicos saudaveis." }

Step "Status dos containers"
& docker @composeArgs ps

Step "Ultimos logs do frontend"
& docker @composeArgs logs --no-color --tail=80 frontend

Step "Ultimos logs do nginx"
& docker @composeArgs logs --no-color --tail=40 nginx

Write-Host "`nStack reiniciada com sucesso." -ForegroundColor Green
