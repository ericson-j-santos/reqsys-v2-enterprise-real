# Verifica todos os endpoints do ReqSys backend
# Uso: .\scripts\verificar-endpoints.ps1
# Opcional: .\scripts\verificar-endpoints.ps1 -BaseUrl http://localhost:8000
#
# Exit code 0 = tudo OK, 1 = falhas encontradas.
# Execute antes de documentar ou fazer deploy.

param(
    [string]$BaseUrl   = "http://127.0.0.1:8000",
    [string]$Email     = "ericsonjosedossantos@tieri659.onmicrosoft.com",
    [switch]$Verbose
)

$erros   = 0
$passou  = 0
$aviso   = 0

function Test-Endpoint {
    param([string]$Label, [string]$Url, [string]$Method = "GET",
          [hashtable]$Headers = @{}, [string]$Body = $null,
          [int[]]$ExpectedCodes = @(200), [switch]$Warn)
    try {
        $params = @{ Uri=$Url; Method=$Method; Headers=$Headers; ErrorAction="Stop" }
        if ($Body) { $params.Body = $Body; $params.ContentType = "application/json" }
        $null = Invoke-RestMethod @params
        $script:passou++
        Write-Host ("  [OK]   {0}" -f $Label) -ForegroundColor Green
        return $true
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        if ($code -in $ExpectedCodes) {
            $script:passou++
            Write-Host ("  [OK]   {0} (HTTP $code esperado)" -f $Label) -ForegroundColor Green
            return $true
        }
        if ($Warn) {
            $script:aviso++
            Write-Host ("  [AVS]  {0} -> HTTP $code (servico externo pode estar offline)" -f $Label) -ForegroundColor Yellow
            return $false
        }
        $script:erros++
        Write-Host ("  [FAIL] {0} -> HTTP $code" -f $Label) -ForegroundColor Red
        return $false
    }
}

Write-Host ""
Write-Host "================================================================"
Write-Host " ReqSys -- verificacao de endpoints: $BaseUrl"
Write-Host "================================================================"
Write-Host ""

# [1/6] Autenticacao
Write-Host "[1/6] Autenticacao"
$token = $null
try {
    $r = Invoke-RestMethod "$BaseUrl/v1/auth/login" -Method Post `
        -ContentType "application/json" -Body "{`"email`":`"$Email`"}" -ErrorAction Stop
    $token = $r.data.access_token
    $papel = $r.data.usuario.papel
    $passou++
    Write-Host ("  [OK]   POST /v1/auth/login -> papel=$papel") -ForegroundColor Green
} catch {
    $erros++
    Write-Host ("  [FAIL] POST /v1/auth/login -> $_") -ForegroundColor Red
}

$h = if ($token) { @{ Authorization = "Bearer $token" } } else { @{} }

# [2/6] Health e Sistema
Write-Host ""
Write-Host "[2/6] Health e Sistema"
$null = Test-Endpoint "GET /health"                             "$BaseUrl/health"                          -Headers $h
$null = Test-Endpoint "GET /v1/sistema/info"                    "$BaseUrl/v1/sistema/info"                 -Headers $h
$null = Test-Endpoint "GET /v1/sistema/health-check"            "$BaseUrl/v1/sistema/health-check"         -Headers $h
$null = Test-Endpoint "GET /v1/sistema/endpoints"               "$BaseUrl/v1/sistema/endpoints"            -Headers $h
$null = Test-Endpoint "GET /v1/sistema/segredos-status"         "$BaseUrl/v1/sistema/segredos-status"      -Headers $h

# [3/6] Dashboard
Write-Host ""
Write-Host "[3/6] Dashboard"
$null = Test-Endpoint "GET /v1/dashboard/requisitos"            "$BaseUrl/v1/dashboard/requisitos"         -Headers $h
$null = Test-Endpoint "GET /v1/dashboard/info"                  "$BaseUrl/v1/dashboard/info"               -Headers $h

# [4/6] Requisitos e Pipeline
Write-Host ""
Write-Host "[4/6] Requisitos e Pipeline"
$null = Test-Endpoint "GET  /v1/requisitos"                     "$BaseUrl/v1/requisitos"                   -Headers $h
$null = Test-Endpoint "POST /v1/requisitos (cria)"              "$BaseUrl/v1/requisitos" -Method Post `
    -Headers $h -Body '{"titulo":"Endpoint check","descricao":"Verificacao automatica de endpoint pela suite de testes","urgencia":"baixa","area":"QA","sistema":"ReqSys","solicitante":"verificar-endpoints.ps1"}'
$null = Test-Endpoint "POST /v1/requisitos/validar"             "$BaseUrl/v1/requisitos/validar" -Method Post `
    -Headers $h -Body '{"titulo":"Titulo de teste","descricao":"Descricao para validacao automatica do endpoint"}'
$null = Test-Endpoint "POST /v1/solicitacoes"                   "$BaseUrl/v1/solicitacoes" -Method Post `
    -Headers $h -Body '{"origem":"teste","titulo":"Titulo teste","descricao":"Descricao completa para solicitacao de teste automatizado","solicitante":"ci","area":"QA","sistema":"ReqSys"}'

# [5/6] Qualidade IA e Auditoria
Write-Host ""
Write-Host "[5/6] Qualidade IA e Auditoria"
$null = Test-Endpoint "GET  /v1/qualidade-ia/resumo"            "$BaseUrl/v1/qualidade-ia/resumo"          -Headers $h
$null = Test-Endpoint "GET  /v1/qualidade-ia/tendencia"         "$BaseUrl/v1/qualidade-ia/tendencia"       -Headers $h
$null = Test-Endpoint "POST /v1/qualidade-ia/snapshot"          "$BaseUrl/v1/qualidade-ia/snapshot" -Method Post -Headers $h -Body '{}'
$null = Test-Endpoint "GET  /v1/auditoria/eventos"              "$BaseUrl/v1/auditoria/eventos"            -Headers $h
$null = Test-Endpoint "GET  /v1/auditoria/eventos/config-infra" "$BaseUrl/v1/auditoria/eventos/config-infra" -Headers $h

# [6/6] Cofre, Specs e Relatorios
Write-Host ""
Write-Host "[6/6] Cofre, Specs e Relatorios"
$null = Test-Endpoint "GET /v1/cofre/status"                    "$BaseUrl/v1/cofre/status"                 -Headers $h
$null = Test-Endpoint "GET /v1/specs"                           "$BaseUrl/v1/specs"                        -Headers $h
$null = Test-Endpoint "GET /v1/specs/exemplos"                  "$BaseUrl/v1/specs/exemplos"               -Headers $h
$null = Test-Endpoint "GET /v1/specs/templates"                 "$BaseUrl/v1/specs/templates"              -Headers $h
$null = Test-Endpoint "GET /v1/relatorios/ssrs"                 "$BaseUrl/v1/relatorios/ssrs"              -Headers $h -Warn
$null = Test-Endpoint "GET /v1/relatorios/ssrs/status"          "$BaseUrl/v1/relatorios/ssrs/status"       -Headers $h -Warn
$null = Test-Endpoint "GET /v1/relatorios/ssrs/health"          "$BaseUrl/v1/relatorios/ssrs/health"       -Headers $h -Warn

# Resultado final
Write-Host ""
Write-Host "================================================================"
$cor = if ($erros -eq 0) { "Green" } else { "Red" }
Write-Host (" PASSOU: $passou  |  AVISO: $aviso (externos)  |  FALHOU: $erros") -ForegroundColor $cor
Write-Host "================================================================"
Write-Host ""

exit $(if ($erros -gt 0) { 1 } else { 0 })
