# Verifica projetos e issues no Redmine
# Uso: .\scripts\verificar-redmine.ps1
#       .\scripts\verificar-redmine.ps1 -Login admin -Password suasenha
#       .\scripts\verificar-redmine.ps1 -ApiKey abc123 -ProjectId 1
#
# Exit code 0 = OK, 1 = falha de autenticacao ou rede.

param(
    [string]$BaseUrl   = "https://redmine-c5i6.onrender.com",
    [string]$Login     = "admin",
    [string]$Password  = "",
    [string]$ApiKey    = "",
    [int]$ProjectId    = 0
)

$erros = 0

function Write-Header([string]$text) {
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host " $text" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
}

function Invoke-Redmine([string]$path, [hashtable]$headers) {
    try {
        return Invoke-RestMethod "$BaseUrl$path" -Headers $headers -ErrorAction Stop
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        Write-Host "  [FAIL] $path -> HTTP $code" -ForegroundColor Red
        $script:erros++
        return $null
    }
}

# ---- Autenticacao ----
Write-Header "Redmine: $BaseUrl"

$h = @{}

if ($ApiKey) {
    $h["X-Redmine-API-Key"] = $ApiKey
    Write-Host "Usando API Key fornecida." -ForegroundColor Yellow
} else {
    if (-not $Password) {
        $secPwd = Read-Host "Senha do usuario '$Login'" -AsSecureString
        $Password = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secPwd))
    }
    $creds = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${Login}:${Password}"))
    $h["Authorization"] = "Basic $creds"

    # Capturar API key do usuario
    $me = Invoke-Redmine "/users/current.json" $h
    if ($me) {
        $ApiKey = $me.user.api_key
        Write-Host "  [OK]   Login como: $($me.user.login) | API Key: $ApiKey" -ForegroundColor Green
        # Trocar para API Key (mais estavel)
        $h = @{ "X-Redmine-API-Key" = $ApiKey }
    }
}

# ---- Projetos ----
Write-Header "Projetos"
$proj = Invoke-Redmine "/projects.json?limit=100" $h
if ($proj) {
    if ($proj.total_count -eq 0) {
        Write-Host "  Nenhum projeto encontrado. O Redmine esta em estado inicial." -ForegroundColor Yellow
    } else {
        Write-Host ("  Total: {0}" -f $proj.total_count)
        $proj.projects | ForEach-Object {
            Write-Host ("  [{0,3}] {1,-40} identifier={2}" -f $_.id, $_.name, $_.identifier) -ForegroundColor White
        }
    }
}

# ---- Trackers e Status ----
Write-Header "Trackers disponiveis"
$tk = Invoke-Redmine "/trackers.json" $h
if ($tk) { $tk.trackers | ForEach-Object { Write-Host ("  [{0}] {1}" -f $_.id, $_.name) } }

Write-Header "Status de issues"
$st = Invoke-Redmine "/issue_statuses.json" $h
if ($st) { $st.issue_statuses | ForEach-Object { Write-Host ("  [{0}] {1}" -f $_.id, $_.name) } }

# ---- Issues (filtrado por projeto se informado) ----
Write-Header "Issues abertas"
$issuePath = "/issues.json?limit=50&status_id=open"
if ($ProjectId -gt 0) { $issuePath += "&project_id=$ProjectId" }
$issues = Invoke-Redmine $issuePath $h
if ($issues) {
    if ($issues.total_count -eq 0) {
        Write-Host "  Nenhuma issue aberta." -ForegroundColor Yellow
    } else {
        Write-Host ("  Total abertas: {0}" -f $issues.total_count)
        $issues.issues | ForEach-Object {
            $proj_name = $_.project.name
            Write-Host ("  [#{0,4}] [{1,-15}] {2}" -f $_.id, $proj_name, $_.subject) -ForegroundColor White
        }
    }
}

# ---- Resumo ----
Write-Header "Resumo"
if ($ApiKey) {
    Write-Host "  API Key capturada: $ApiKey" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Para configurar no ReqSys, execute:" -ForegroundColor Cyan
    Write-Host "  .\scripts\configurar-redmine.ps1 -ApiKey '$ApiKey' -ProjectId <ID>" -ForegroundColor White
}
Write-Host ""
if ($erros -gt 0) {
    Write-Host "  ERROS: $erros" -ForegroundColor Red
    exit 1
}
Write-Host "  Verificacao concluida sem erros." -ForegroundColor Green
exit 0
