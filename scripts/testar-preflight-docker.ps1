[CmdletBinding()]
param(
    [string]$ProjetoDir = "",
    [ValidateSet('dev', 'test', 'prod')]
    [string]$Ambiente = 'dev',
    [switch]$ExigirEnv,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($ProjetoDir)) {
    $ProjetoDir = Join-Path $PSScriptRoot '..'
}

if (-not (Test-Path -LiteralPath $ProjetoDir -PathType Container)) {
    throw "Diretorio do projeto nao encontrado: $ProjetoDir. Nenhum comando Docker foi executado."
}

$ProjetoDir = (Resolve-Path -LiteralPath $ProjetoDir).Path
$requiredFiles = @(
    'docker-compose.yml',
    "docker-compose.$Ambiente.yml",
    'backend\Dockerfile',
    'frontend\Dockerfile',
    'frontend\package.json'
)

if ($Ambiente -eq 'prod') {
    $requiredFiles += 'infra\nginx\default.prod.conf'
}
else {
    $requiredFiles += 'infra\nginx\default.dev.conf'
}

if ($ExigirEnv) {
    $requiredFiles += '.env'
}

$missingFiles = @(
    foreach ($relativePath in $requiredFiles) {
        $absolutePath = Join-Path $ProjetoDir $relativePath
        if (-not (Test-Path -LiteralPath $absolutePath -PathType Leaf)) {
            $absolutePath
        }
    }
)

if ($missingFiles.Count -gt 0) {
    $details = $missingFiles -join [Environment]::NewLine
    throw "Preflight Docker bloqueado. Arquivos obrigatorios ausentes ou invalidos:$([Environment]::NewLine)$details$([Environment]::NewLine)Nenhum comando Docker foi executado."
}

if (-not $Quiet) {
    Write-Host "[ok] Preflight Docker ($Ambiente): $ProjetoDir" -ForegroundColor Green
}

[PSCustomObject]@{
    ProjetoDir = $ProjetoDir
    Ambiente = $Ambiente
    ArquivosValidados = $requiredFiles.Count
}
