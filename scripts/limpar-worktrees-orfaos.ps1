#Requires -Version 5.1
<#
.SYNOPSIS
    Remove com seguranca os worktrees orfaos do ReqSys, sem -Force e sem tocar em branches.

.DESCRIPTION
    Executa o passo a passo do blueprint de acoes humanas (item 2) de forma idempotente
    e fail-closed:

      1. confere que o diretorio atual e o repositorio principal;
      2. para cada worktree alvo, verifica se ainda esta registrado;
      3. recusa a remocao quando ha alteracoes nao commitadas ou commits nao publicados,
         listando o que segurou — nunca usa 'git worktree remove --force';
      4. remove os worktrees limpos, roda 'git worktree prune' e reconfere a lista;
      5. grava evidencia JSON em artifacts/governance/.

    Nenhum branch, commit ou historico e apagado: 'git worktree remove' descarta apenas o
    diretorio de trabalho. Nao executa checkout, reset ou stash — respeitando o guardrail
    de worktrees do CLAUDE.md.

.PARAMETER RepositorioPrincipal
    Caminho do clone principal (o que contem .git como diretorio). Padrao: diretorio atual.

.PARAMETER Worktrees
    Nomes dos worktrees a remover, relativos ao pai do repositorio principal.
    Padrao: os 11 worktrees orfaos mapeados no blueprint.

.PARAMETER Evidencia
    Caminho do relatorio JSON. Padrao: artifacts/governance/worktree-cleanup.json.

.PARAMETER Simular
    Apenas relata o que seria feito, sem remover nada.

.EXAMPLE
    cd github-main
    ..\reqsys\scripts\limpar-worktrees-orfaos.ps1 -Simular

.EXAMPLE
    cd github-main
    .\scripts\limpar-worktrees-orfaos.ps1

.OUTPUTS
    Exit code 0 quando todos os alvos sairam da lista; 1 quando algum ficou bloqueado.
#>

[CmdletBinding()]
param(
    [string]$RepositorioPrincipal = (Get-Location).Path,

    [string[]]$Worktrees = @(
        'wt-1462-rebase',
        'wt-conexoes-erro-real',
        'wt-cors-fix',
        'wt-fix-bacen-gate-manifest',
        'wt-fix-deploy-erro',
        'wt-fix-flow-create',
        'wt-fix-flow-patch',
        'wt-obo-connections',
        'wt-recover-conexoes-e2e',
        'wt-scope-test',
        'wt-silent-reauth'
    ),

    [string]$Evidencia = 'artifacts/governance/worktree-cleanup.json',

    [switch]$Simular
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Invoke-Git {
    <#
        Executa git capturando stdout+stderr e o codigo de saida, sem lancar excecao.

        Varias chamadas deste script esperam exit code diferente de zero como resposta
        valida (por exemplo, 'rev-parse @{upstream}' quando o branch nao tem upstream).
        No PowerShell 7.3+ o $PSNativeCommandUseErrorActionPreference converteria esses
        casos em excecao por causa do $ErrorActionPreference='Stop' global, entao ambos
        sao neutralizados dentro desta funcao.
    #>
    param([Parameter(Mandatory)][string[]]$Argumentos)

    $ErrorActionPreference = 'Continue'
    $PSNativeCommandUseErrorActionPreference = $false

    $saida = & git @Argumentos 2>&1
    return [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Saida    = ($saida | Out-String).Trim()
    }
}

function Get-WorktreesRegistrados {
    param([Parameter(Mandatory)][string]$Repositorio)

    $resultado = Invoke-Git @('-C', $Repositorio, 'worktree', 'list', '--porcelain')
    if ($resultado.ExitCode -ne 0) {
        throw "Nao foi possivel listar worktrees em '$Repositorio': $($resultado.Saida)"
    }

    $caminhos = @()
    foreach ($linha in ($resultado.Saida -split "`r?`n")) {
        if ($linha -match '^worktree\s+(.+)$') {
            $caminhos += $Matches[1].Trim()
        }
    }
    return $caminhos
}

function Test-CaminhoEquivalente {
    param([string]$A, [string]$B)

    try {
        $normalA = (Resolve-Path -LiteralPath $A -ErrorAction Stop).Path
        $normalB = (Resolve-Path -LiteralPath $B -ErrorAction Stop).Path
    }
    catch {
        return $false
    }
    return $normalA.TrimEnd('\', '/') -ieq $normalB.TrimEnd('\', '/')
}

function Get-Bloqueios {
    <#
        Motivos para NAO remover um worktree: arquivos sujos ou commits nao publicados.
        Sem esses bloqueios, 'git worktree remove' (sem --force) e uma operacao segura.
    #>
    param([Parameter(Mandatory)][string]$Caminho)

    $bloqueios = @()

    $status = Invoke-Git @('-C', $Caminho, 'status', '--porcelain')
    if ($status.ExitCode -ne 0) {
        return @("nao foi possivel ler o status: $($status.Saida)")
    }
    if ($status.Saida) {
        $quantidade = ($status.Saida -split "`r?`n").Count
        $bloqueios += "$quantidade arquivo(s) com alteracoes nao commitadas"
    }

    # Commits locais ainda sem upstream publicado. Sem upstream configurado, comparamos
    # com origin/main para nao apagar trabalho que nunca chegou ao remoto.
    $upstream = Invoke-Git @('-C', $Caminho, 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}')
    $referencia = if ($upstream.ExitCode -eq 0 -and $upstream.Saida) { $upstream.Saida } else { 'origin/main' }

    $naoPublicados = Invoke-Git @('-C', $Caminho, 'rev-list', '--count', "$referencia..HEAD")
    if ($naoPublicados.ExitCode -eq 0 -and $naoPublicados.Saida -match '^\d+$' -and [int]$naoPublicados.Saida -gt 0) {
        $bloqueios += "$($naoPublicados.Saida) commit(s) ainda nao presente(s) em '$referencia'"
    }

    return $bloqueios
}

# ---------------------------------------------------------------------------

$repositorio = (Resolve-Path -LiteralPath $RepositorioPrincipal).Path
$verificacao = Invoke-Git @('-C', $repositorio, 'rev-parse', '--is-inside-work-tree')
if ($verificacao.ExitCode -ne 0 -or $verificacao.Saida -ne 'true') {
    throw "'$repositorio' nao e um repositorio git."
}

$raiz = Split-Path -Parent $repositorio
$registrados = Get-WorktreesRegistrados -Repositorio $repositorio

Write-Host "Repositorio principal: $repositorio"
Write-Host "Worktrees registrados antes: $($registrados.Count)"
Write-Host ''

$relatorio = @()

foreach ($nome in $Worktrees) {
    $caminho = Join-Path $raiz $nome
    $registrado = @($registrados | Where-Object { Test-CaminhoEquivalente -A $_ -B $caminho })

    if ($registrado.Count -eq 0) {
        Write-Host "[ja-removido] $nome"
        $relatorio += [pscustomobject]@{ worktree = $nome; caminho = $caminho; resultado = 'ja_removido'; bloqueios = @() }
        continue
    }

    $bloqueios = @(Get-Bloqueios -Caminho $caminho)
    if ($bloqueios.Count -gt 0) {
        Write-Warning "[bloqueado]   $nome -> $($bloqueios -join '; ')"
        Write-Warning "              inspecione com: git -C `"$caminho`" status"
        $relatorio += [pscustomobject]@{ worktree = $nome; caminho = $caminho; resultado = 'bloqueado'; bloqueios = $bloqueios }
        continue
    }

    if ($Simular) {
        Write-Host "[simulado]    $nome (removivel sem --force)"
        $relatorio += [pscustomobject]@{ worktree = $nome; caminho = $caminho; resultado = 'simulado'; bloqueios = @() }
        continue
    }

    $remocao = Invoke-Git @('-C', $repositorio, 'worktree', 'remove', $caminho)
    if ($remocao.ExitCode -eq 0) {
        Write-Host "[removido]    $nome"
        $relatorio += [pscustomobject]@{ worktree = $nome; caminho = $caminho; resultado = 'removido'; bloqueios = @() }
    }
    else {
        Write-Warning "[falhou]      $nome -> $($remocao.Saida)"
        Write-Warning '              nao reexecute com --force; valide o conteudo primeiro.'
        $relatorio += [pscustomobject]@{ worktree = $nome; caminho = $caminho; resultado = 'falhou'; bloqueios = @($remocao.Saida) }
    }
}

if (-not $Simular) {
    $prune = Invoke-Git @('-C', $repositorio, 'worktree', 'prune')
    if ($prune.ExitCode -ne 0) {
        Write-Warning "git worktree prune falhou: $($prune.Saida)"
    }
}

$restantes = Get-WorktreesRegistrados -Repositorio $repositorio
$pendentes = @()
foreach ($nome in $Worktrees) {
    $caminho = Join-Path $raiz $nome
    if (@($restantes | Where-Object { Test-CaminhoEquivalente -A $_ -B $caminho }).Count -gt 0) {
        $pendentes += $nome
    }
}

Write-Host ''
Write-Host "Worktrees registrados depois: $($restantes.Count)"
Write-Host "Alvos ainda presentes: $($pendentes.Count)"

$documento = [ordered]@{
    schema_version     = '1.0.0'
    contract           = 'reqsys-worktree-cleanup'
    gerado_em          = (Get-Date).ToUniversalTime().ToString('o')
    repositorio        = $repositorio
    simulacao          = [bool]$Simular
    force_utilizado    = $false
    branches_removidos = $false
    alvos              = $Worktrees
    resultados         = $relatorio
    pendentes          = $pendentes
    concluido          = ($pendentes.Count -eq 0)
}

$diretorioEvidencia = Split-Path -Parent $Evidencia
if ($diretorioEvidencia -and -not (Test-Path -LiteralPath $diretorioEvidencia)) {
    New-Item -ItemType Directory -Force -Path $diretorioEvidencia | Out-Null
}
$documento | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $Evidencia -Encoding utf8
Write-Host "Evidencia: $Evidencia"

if ($pendentes.Count -gt 0 -and -not $Simular) {
    exit 1
}
exit 0
