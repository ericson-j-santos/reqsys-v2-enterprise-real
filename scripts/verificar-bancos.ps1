# Verifica bancos de dados ativos/inativos na maquina (Docker + servicos nativos Windows)
# Uso: .\scripts\verificar-bancos.ps1
#       .\scripts\verificar-bancos.ps1 -SqlServerInstance localhost -PgUser postgres
#
# Nao exige nada do projeto ReqSys especificamente - roda em qualquer maquina Windows
# com Docker Desktop e/ou SQL Server/PostgreSQL nativos instalados.
#
# Exit code sempre 0 (script de diagnostico, nao de gate).

param(
    [string]$SqlServerInstance = "localhost",
    [string]$PgHost            = "localhost",
    [int]   $PgPort            = 5432,
    [string]$PgUser            = "postgres",
    [string]$PgPassword        = ""
)

function Write-Header([string]$text) {
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host " $text" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
}

# ---- Containers Docker com motor de banco de dados ----
Write-Header "Containers Docker (bancos de dados)"
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Host "  Docker nao encontrado no PATH. Pulando esta secao." -ForegroundColor Yellow
} else {
    $linhas = docker ps -a --format "{{.Names}}`t{{.Image}}`t{{.Status}}`t{{.Ports}}" 2>$null
    if (-not $linhas) {
        Write-Host "  Docker instalado, mas o daemon nao respondeu (Docker Desktop rodando?)." -ForegroundColor Yellow
    } else {
        $padrao = "postgres|mssql|sqlserver|mysql|mongo|redis|mariadb|oracle|cockroach"
        $filtradas = $linhas | Select-String -Pattern $padrao -CaseSensitive:$false
        if (-not $filtradas) {
            Write-Host "  Nenhum container com imagem de banco de dados encontrado." -ForegroundColor Yellow
        } else {
            "{0,-45} {1,-40} {2}" -f "NOME", "IMAGEM", "STATUS" | Write-Host -ForegroundColor White
            foreach ($l in $filtradas) {
                $campos = $l.Line -split "`t"
                $cor = if ($campos[2] -match "^Up") { "Green" } else { "Red" }
                "{0,-45} {1,-40} {2}" -f $campos[0], $campos[1], $campos[2] | Write-Host -ForegroundColor $cor
            }
        }
    }
}

# ---- Servicos nativos Windows ----
Write-Header "Servicos nativos Windows (bancos de dados)"
$servicos = Get-Service | Where-Object { $_.DisplayName -match "SQL|Postgres|MySQL|Mongo|Redis|Maria|Oracle" }
if (-not $servicos) {
    Write-Host "  Nenhum servico de banco de dados nativo encontrado." -ForegroundColor Yellow
} else {
    $servicos | ForEach-Object {
        $cor = if ($_.Status -eq "Running") { "Green" } else { "DarkGray" }
        "  [{0,-9}] {1}" -f $_.Status, $_.DisplayName | Write-Host -ForegroundColor $cor
    }
}

# ---- SQL Server nativo: listar bancos ----
Write-Header "SQL Server nativo ($SqlServerInstance) - bancos"
$sqlcmdCmd = Get-Command sqlcmd -ErrorAction SilentlyContinue
if (-not $sqlcmdCmd) {
    Write-Host "  sqlcmd nao encontrado no PATH. Pulando (instale o 'SQL Server Command Line Utilities')." -ForegroundColor Yellow
} else {
    $resultado = sqlcmd -S $SqlServerInstance -E -C -Q "SET NOCOUNT ON; SELECT name, state_desc, create_date FROM sys.databases ORDER BY database_id" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Falha ao conectar em '$SqlServerInstance' (servico rodando? auth Windows habilitada?)." -ForegroundColor Yellow
        Write-Host "  Detalhe: $resultado" -ForegroundColor DarkGray
    } else {
        $resultado | ForEach-Object { Write-Host "  $_" }
    }
}

# ---- PostgreSQL nativo: listar bancos ----
Write-Header "PostgreSQL nativo ($PgHost`:$PgPort) - bancos"
$psqlPath = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psqlPath) {
    # psql geralmente nao fica no PATH por padrao no Windows; procurar instalacoes conhecidas
    $achado = Get-ChildItem "C:\Program Files\PostgreSQL" -Recurse -Filter "psql.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($achado) { $psqlPath = $achado.FullName }
}
if (-not $psqlPath) {
    Write-Host "  psql.exe nao encontrado. Pulando (instale o PostgreSQL client ou informe o caminho manualmente)." -ForegroundColor Yellow
} else {
    if (-not $PgPassword) {
        Write-Host "  Nenhuma -PgPassword informada - pulando para evitar travar esperando senha interativa." -ForegroundColor Yellow
        Write-Host "  Rode novamente com -PgPassword 'suasenha' para listar os bancos." -ForegroundColor DarkGray
    } else {
        $env:PGPASSWORD = $PgPassword
        & $psqlPath -U $PgUser -h $PgHost -p $PgPort -l 2>&1 | ForEach-Object { Write-Host "  $_" }
        $env:PGPASSWORD = ""
    }
}

Write-Header "Resumo"
Write-Host "  Verificacao concluida. Nada e alterado por este script (somente leitura)." -ForegroundColor Green
exit 0
