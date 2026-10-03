<#
.SYNOPSIS
Valida a configuração local do OCR v2 sem expor segredos.

.DESCRIPTION
Executa quatro verificações:
1. fonte de configuração disponível (.env ou variáveis de processo);
2. OCR_DATA_ENCRYPTION_KEY válida em Base64 com 32 bytes;
3. OCR_INPUT_ROOT configurado e acessível como diretório;
4. endpoint de readiness respondendo com estado seguro e ready=true.

O script nunca imprime o valor da chave de criptografia.
#>

[CmdletBinding()]
param(
    [ValidateNotNullOrEmpty()]
    [string]$EnvFile = '.env',

    [ValidateNotNullOrEmpty()]
    [string]$ReadinessUrl = 'http://localhost:8211/v1/ocr/readiness'
)

$ErrorActionPreference = 'Stop'

function Get-DotEnvValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) {
            continue
        }

        $parts = $trimmed.Split('=', 2)
        if ($parts.Count -eq 2 -and $parts[0].Trim() -eq $Name) {
            return $parts[1].Trim()
        }
    }

    return $null
}

function Get-ConfigValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $processValue = [Environment]::GetEnvironmentVariable($Name, 'Process')
    if (-not [string]::IsNullOrWhiteSpace($processValue)) {
        return $processValue
    }

    return Get-DotEnvValue -Path $EnvFile -Name $Name
}

$results = [System.Collections.Generic.List[object]]::new()

function Add-ValidationResult {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [bool]$Passed,

        [Parameter(Mandatory = $true)]
        [string]$Detail
    )

    $results.Add([pscustomobject]@{
        Name = $Name
        Passed = $Passed
        Detail = $Detail
    }) | Out-Null
}

# 1. Fonte de configuração
$hasEnvFile = Test-Path -LiteralPath $EnvFile -PathType Leaf
$hasProcessConfig = -not [string]::IsNullOrWhiteSpace(
    [Environment]::GetEnvironmentVariable('OCR_DATA_ENCRYPTION_KEY', 'Process')
) -and -not [string]::IsNullOrWhiteSpace(
    [Environment]::GetEnvironmentVariable('OCR_INPUT_ROOT', 'Process')
)

Add-ValidationResult `
    -Name 'Fonte de configuração' `
    -Passed ($hasEnvFile -or $hasProcessConfig) `
    -Detail $(if ($hasEnvFile) { ".env disponível em $EnvFile" } elseif ($hasProcessConfig) { 'variáveis de processo disponíveis' } else { 'nenhuma fonte de configuração válida encontrada' })

# 2. Chave AES-256
$key = Get-ConfigValue -Name 'OCR_DATA_ENCRYPTION_KEY'
$keyValid = $false
$keyDetail = 'OCR_DATA_ENCRYPTION_KEY ausente'

if (-not [string]::IsNullOrWhiteSpace($key)) {
    try {
        $decodedKey = [Convert]::FromBase64String($key)
        $keyValid = $decodedKey.Length -eq 32
        $keyDetail = if ($keyValid) {
            'chave Base64 válida com 32 bytes'
        }
        else {
            "chave decodifica para $($decodedKey.Length) bytes; esperado: 32"
        }
    }
    catch {
        $keyDetail = 'chave não é Base64 válida'
    }
}

Add-ValidationResult -Name 'OCR_DATA_ENCRYPTION_KEY' -Passed $keyValid -Detail $keyDetail

# 3. Diretório de entrada
$inputRoot = Get-ConfigValue -Name 'OCR_INPUT_ROOT'
$inputRootValid = -not [string]::IsNullOrWhiteSpace($inputRoot) -and (Test-Path -LiteralPath $inputRoot -PathType Container)
$inputRootDetail = if ([string]::IsNullOrWhiteSpace($inputRoot)) {
    'OCR_INPUT_ROOT ausente'
}
elseif ($inputRootValid) {
    'diretório configurado e existente'
}
else {
    'diretório configurado não existe ou não é acessível'
}

Add-ValidationResult -Name 'OCR_INPUT_ROOT' -Passed $inputRootValid -Detail $inputRootDetail

# 4. Readiness do backend
$readinessValid = $false
$readinessDetail = 'endpoint de readiness indisponível'

try {
    $readiness = Invoke-RestMethod -Uri $ReadinessUrl -Method Get -TimeoutSec 5

    $hasExpectedContract = $null -ne $readiness.ready -and
        $null -ne $readiness.key_configured -and
        $null -ne $readiness.input_root_configured -and
        $null -ne $readiness.plaintext_storage_allowed

    $readinessValid = $hasExpectedContract -and
        [bool]$readiness.ready -and
        [bool]$readiness.key_configured -and
        [bool]$readiness.input_root_configured -and
        -not [bool]$readiness.plaintext_storage_allowed

    if (-not $hasExpectedContract) {
        $readinessDetail = 'resposta não atende ao contrato esperado'
    }
    elseif ($readinessValid) {
        $readinessDetail = 'ready=true e armazenamento plaintext bloqueado'
    }
    else {
        $readinessDetail = 'backend respondeu, mas não está em estado OCR pronto e seguro'
    }
}
catch {
    $readinessDetail = 'não foi possível consultar o endpoint de readiness'
}

Add-ValidationResult -Name 'readiness' -Passed $readinessValid -Detail $readinessDetail

Write-Host '========================================'
Write-Host '  Validação OCR v2'
Write-Host '========================================'

foreach ($result in $results) {
    $status = if ($result.Passed) { 'PASS' } else { 'FAIL' }
    Write-Host ("[{0}] {1}: {2}" -f $status, $result.Name, $result.Detail)
}

$passed = @($results | Where-Object { $_.Passed }).Count
$total = $results.Count
Write-Host '========================================'
Write-Host ("Resultado: {0}/{1} checks passaram" -f $passed, $total)
Write-Host '========================================'

if ($passed -ne $total) {
    exit 1
}

Write-Host 'Todas as verificações passaram. OCR pronto para uso.'
exit 0
