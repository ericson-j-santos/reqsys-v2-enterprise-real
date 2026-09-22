<#
Validação operacional simples do gateway ReqSys.
Não substitui testes automatizados de aplicação; valida roteamento mínimo do proxy reverso.

Uso:
  .\infra\reverse-proxy\scripts\validate-reverse-proxy.ps1 -BaseUrl "http://localhost:8081"
#>

[CmdletBinding()]
param(
  [string]$BaseUrl = "http://localhost:8081",
  [int]$TimeoutSec = 10
)

$ErrorActionPreference = "Stop"

$checks = @(
  @{ Nome = "Frontend"; Url = "$BaseUrl/"; StatusAceito = @(200, 304) },
  @{ Nome = "API docs"; Url = "$BaseUrl/api/docs"; StatusAceito = @(200, 307, 308, 404) },
  @{ Nome = "Favicon sem ruído"; Url = "$BaseUrl/favicon.ico"; StatusAceito = @(204) }
)

$resultados = @()
$falhas = 0

foreach ($check in $checks) {
  try {
    $response = Invoke-WebRequest -Uri $check.Url -Method Get -TimeoutSec $TimeoutSec -MaximumRedirection 0 -ErrorAction Stop
    $status = [int]$response.StatusCode
  } catch {
    if ($_.Exception.Response) {
      $status = [int]$_.Exception.Response.StatusCode
    } else {
      $status = 0
    }
  }

  $ok = $check.StatusAceito -contains $status
  if (-not $ok) { $falhas++ }

  $resultados += [pscustomobject]@{
    Nome = $check.Nome
    Url = $check.Url
    Status = $status
    Resultado = if ($ok) { "OK" } else { "FALHA" }
  }
}

$resultados | Format-Table -AutoSize

if ($falhas -gt 0) {
  throw "Validação do proxy reverso falhou em $falhas verificação(ões)."
}

Write-Host "[ReqSys] Validação do proxy reverso concluída com sucesso." -ForegroundColor Green
