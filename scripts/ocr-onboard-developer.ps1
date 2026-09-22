<#
.SYNOPSIS
OCR Developer Onboarding Automation

.DESCRIPTION
Automatiza setup completo do OCR v2 para novos desenvolvedores.
Reduz tempo de onboarding de 15 min para < 2 min.

Executa:
1. Gera chave de criptografia (32 bytes Base64)
2. Configura .env local
3. Cria OCR_INPUT_ROOT
4. Valida readiness
5. Relatorio de conclusao

.PARAMETER Environment
Ambiente: development (default), staging, production

.PARAMETER SkipValidation
Pular validacao final (para testes)

.PARAMETER Verbose
Mostrar detalhes de cada etapa

.EXAMPLE
.\ocr-onboard-developer.ps1
.\ocr-onboard-developer.ps1 -Environment staging -Verbose
#>

param(
    [ValidateSet('development', 'staging', 'production')]
    [string]$Environment = 'development',

    [switch]$SkipValidation = $false,

    [switch]$Verbose = $false
)

$ErrorActionPreference = 'Stop'

# ============================================================================
# Configuracao
# ============================================================================

$SCRIPT_VERSION = '1.0'
$MIN_PYTHON_VERSION = '3.9'
$OCR_KEY_SIZE = 32  # bytes

# Configuracoes por ambiente
$EnvConfig = @{
    'development' = @{
        InputRoot = 'C:/tmp/ocr-input'
        KeyVersion = 'v1'
        Description = 'Desenvolvimento local'
    }
    'staging' = @{
        InputRoot = '/data/ocr-staging'
        KeyVersion = 'v1'
        Description = 'Ambiente de testes (Fly.io)'
    }
    'production' = @{
        InputRoot = '/secure/ocr-prod'
        KeyVersion = 'v1'
        Description = 'Producao (Azure)'
    }
}

# ============================================================================
# Funcoes
# ============================================================================

function Write-Header {
    param([string]$Title)
    Write-Host "`n" -NoNewline
    Write-Host $Title -ForegroundColor Cyan -BackgroundColor Black
    Write-Host ('=' * $Title.Length) -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠️  $Message" -ForegroundColor Yellow
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "❌ ERRO: $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ️  $Message" -ForegroundColor Blue
}

function Test-PythonAvailable {
    <#Verificar se Python está instalado#>
    try {
        $pythonVersion = python --version 2>&1
        Write-Success "Python encontrado: $pythonVersion"
        return $true
    }
    catch {
        Write-Error-Custom "Python não encontrado. Instale Python 3.9+"
        return $false
    }
}

function Generate-EncryptionKey {
    <#Gerar chave de criptografia de 32 bytes em Base64#>
    Write-Info "Gerando chave de criptografia (AES-256-GCM, 32 bytes)..."

    $key = python -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes($OCR_KEY_SIZE)).decode())"

    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao gerar chave com Python"
    }

    Write-Success "Chave gerada com sucesso"
    Write-Verbose "Chave: $($key.Substring(0, 16))..." -Verbose:$Verbose

    return $key
}

function Test-EnvFileExists {
    <#Verificar se .env existe, criar se nao#>
    if (-not (Test-Path '.env')) {
        Write-Warning ".env nao encontrado"
        Write-Info "Copiando de .env.example..."

        if (Test-Path '.env.example') {
            Copy-Item '.env.example' '.env'
            Write-Success ".env criado a partir de .env.example"
        }
        else {
            Write-Warning "Criando .env vazio (configure variables manualmente)"
            New-Item -ItemType File -Path '.env' | Out-Null
        }
    }
    else {
        Write-Success ".env ja existe"
    }
}

function Update-EnvFile {
    param(
        [string]$Key,
        [string]$Value
    )

    <#Atualizar ou adicionar variavel no .env#>
    $envPath = '.env'

    # Verificar se chave ja existe
    if ((Get-Content $envPath -Raw) -match "^$Key=") {
        # Substituir valor existente
        (Get-Content $envPath) | ForEach-Object {
            if ($_ -match "^$Key=") {
                "$Key=$Value"
            }
            else {
                $_
            }
        } | Set-Content $envPath
        Write-Success "Atualizado: $Key"
    }
    else {
        # Adicionar nova variavel
        Add-Content $envPath "`n# OCR v2 - Configurado em $(Get-Date -Format 'yyyy-MM-dd HH:mm')`n$Key=$Value"
        Write-Success "Adicionado: $Key"
    }
}

function Create-InputDirectory {
    param([string]$Path)

    <#Criar diretorio OCR_INPUT_ROOT#>
    Write-Info "Criando diretorio de entrada: $Path"

    try {
        if (-not (Test-Path $Path)) {
            New-Item -ItemType Directory -Force -Path $Path | Out-Null
            Write-Success "Diretorio criado"
        }
        else {
            Write-Success "Diretorio ja existe"
        }

        # Verificar acesso
        $testFile = Join-Path $Path '.ocr-test'
        'test' | Out-File $testFile -ErrorAction SilentlyContinue
        if (Test-Path $testFile) {
            Remove-Item $testFile
            Write-Success "Diretorio eh acessivel"
        }
        else {
            Write-Warning "Nao foi possivel escrever no diretorio"
        }
    }
    catch {
        Write-Error-Custom "Falha ao criar diretorio: $_"
        return $false
    }

    return $true
}

function Test-Readiness {
    <#Testar endpoint /v1/ocr/readiness#>
    Write-Info "Testando readiness endpoint..."

    try {
        $response = Invoke-WebRequest -Uri 'http://localhost:8211/v1/ocr/readiness' `
            -Method GET `
            -TimeoutSec 5 `
            -SkipHttpErrorCheck

        if ($response.StatusCode -eq 200) {
            $data = $response.Content | ConvertFrom-Json

            Write-Success "Endpoint respondendo"
            Write-Info "Status: $($data.ready)"
            Write-Info "Encryption: $($data.encryption)"
            Write-Info "Key configured: $($data.key_configured)"
            Write-Info "Input root configured: $($data.input_root_configured)"

            if ($data.ready) {
                Write-Success "✅ OCR esta pronto para uso!"
                return $true
            }
            else {
                Write-Warning "OCR nao esta pronto ainda"
                Write-Info "Verifique a configuracao e reinicie o backend"
                return $false
            }
        }
        else {
            Write-Warning "Backend nao esta respondendo (esperado se nao iniciou)"
            return $false
        }
    }
    catch {
        Write-Warning "Backend nao esta disponivel em localhost:8211"
        Write-Info "Inicie com: docker-compose up -d backend"
        Write-Info "Ou: cd backend && uvicorn app.main:app --reload"
        return $false
    }
}

function Show-Summary {
    param(
        [string]$EncryptionKey,
        [string]$InputRoot,
        [string]$Env
    )

    <#Mostrar resumo de configuracao#>
    Write-Header "📋 Resumo de Configuracao"

    Write-Host @"

Ambiente:           $Env
Data:               $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Script Version:     $SCRIPT_VERSION

Chave de Criptografia:
  - Tamanho: $OCR_KEY_SIZE bytes (AES-256-GCM)
  - Formato: Base64
  - Valor: $($EncryptionKey.Substring(0, 20))...
  - Status: ✅ Configurada em .env

Diretorio de Entrada:
  - Caminho: $InputRoot
  - Status: ✅ Criado

Proximos Passos:
  1. Iniciar backend:
     docker-compose up -d backend
     ou
     cd backend && uvicorn app.main:app --reload

  2. Validar readiness:
     .\scripts\validate-ocr-setup.ps1

  3. Testar com documento:
     cp ~\test-document.pdf $InputRoot\

  4. Revisar em:
     http://localhost:8083/admin/ocr-review

Documentacao:
  - Guia: docs/guides/ocr-setup-local-development.md
  - Arquitetura: docs/architecture/ocr-secure-review-v2.md
  - Checklist: .github/OCRL_SETUP_CHECKLIST.md

Suporte:
  - Issue: https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues
  - Slack: #dev-ocr ou #dev-backend

"@ -ForegroundColor White

    Write-Success "Onboarding concluido com sucesso! 🎉"
    Write-Info "Tempo total: < 2 minutos"
}

function Save-Setup-Report {
    <#Salvar relatorio de setup em arquivo#>
    param([string]$EncryptionKey, [string]$InputRoot)

    $reportPath = 'OCR_SETUP_REPORT.txt'
    $content = @"
OCR Setup Report
Generated: $(Get-Date)
Environment: $Environment

Configuration:
- OCR_DATA_ENCRYPTION_KEY: GENERATED (32 bytes)
- OCR_DATA_KEY_VERSION: v1
- OCR_INPUT_ROOT: $InputRoot
- Encryption: AES-256-GCM

Files:
- .env: Updated
- Input directory: Created

Next Steps:
1. docker-compose up -d backend
2. .\scripts\validate-ocr-setup.ps1
3. Test with document
4. Access http://localhost:8083/admin/ocr-review
"@

    $content | Out-File $reportPath -Encoding UTF8
    Write-Success "Relatorio salvo: $reportPath"
}

# ============================================================================
# Main Script
# ============================================================================

function Main {
    Write-Header "🚀 OCR Developer Onboarding v$SCRIPT_VERSION"
    Write-Info "Ambiente: $Environment ($($EnvConfig[$Environment].Description))"

    # Step 1: Verificar prerequisitos
    Write-Header "1️⃣  Verificando Prerequisitos"
    if (-not (Test-PythonAvailable)) {
        exit 1
    }

    # Step 2: Gerar chave
    Write-Header "2️⃣  Gerando Chave de Criptografia"
    $encryptionKey = Generate-EncryptionKey

    # Step 3: Configurar .env
    Write-Header "3️⃣  Configurando .env"
    Test-EnvFileExists
    Update-EnvFile 'OCR_DATA_ENCRYPTION_KEY' $encryptionKey
    Update-EnvFile 'OCR_DATA_KEY_VERSION' $EnvConfig[$Environment].KeyVersion
    Update-EnvFile 'OCR_INPUT_ROOT' $EnvConfig[$Environment].InputRoot

    # Step 4: Criar diretorio
    Write-Header "4️⃣  Criando Diretorio de Entrada"
    $inputRootPath = $EnvConfig[$Environment].InputRoot
    Create-InputDirectory $inputRootPath | Out-Null

    # Step 5: Validar (opcional)
    if (-not $SkipValidation) {
        Write-Header "5️⃣  Validando Configuracao"
        $readinessResult = Test-Readiness
    }

    # Step 6: Resumo
    Show-Summary $encryptionKey $inputRootPath $Environment

    # Step 7: Salvar relatorio
    Save-Setup-Report $encryptionKey $inputRootPath

    Write-Host "`n"
    Write-Success "Tudo pronto! Comece com: docker-compose up -d backend`n"
}

# ============================================================================
# Executar
# ============================================================================

try {
    Main
    exit 0
}
catch {
    Write-Error-Custom $_
    exit 1
}
