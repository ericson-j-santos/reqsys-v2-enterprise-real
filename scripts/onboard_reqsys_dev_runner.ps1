[CmdletBinding(SupportsShouldProcess)]
param(
  [Parameter(Mandatory = $true)][ValidatePattern('^[a-z0-9][a-z0-9-]{7,63}$')][string]$RunnerInstanceId,
  [Parameter(Mandatory = $true)][string]$RuntimeRoot,
  [ValidateSet('base', 'runtime', 'ollama')][string]$Profile = 'runtime',
  [string]$ManifestPath = "$env:ProgramData\ReqSys\runner-pool.json",
  [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$policy = Get-Content -Raw (Join-Path $repoRoot 'config\reqsys-dev-runner-pool.json') | ConvertFrom-Json
$selected = $policy.profiles.$Profile
if (-not $selected) { throw 'PROFILE_INVALID' }
$runnerLabels = @($selected.runner_labels)
if (-not $runnerLabels -or $runnerLabels.Count -lt 5) { throw 'PROFILE_LABELS_INVALID' }
if (-not (Test-Path -LiteralPath $RuntimeRoot -PathType Container)) { throw 'RUNTIME_ROOT_INVALID' }
$manifest = [ordered]@{
  schema_version = 1
  pool = $policy.pool
  profile = $Profile
  environment = 'dev'
  runner_instance_id = $RunnerInstanceId
  allowed_environments = @('dev')
  runtime_root = (Resolve-Path -LiteralPath $RuntimeRoot).Path
  capabilities = @($selected.capabilities)
  runner_labels = @($runnerLabels)
  safeguards = [ordered]@{
    hml_enabled = $false
    stg_enabled = $false
    production_enabled = $false
    automatic_retry_enabled = $false
  }
}
if (-not $ValidateOnly) {
  $parent = Split-Path -Parent $ManifestPath
  if ($PSCmdlet.ShouldProcess($ManifestPath, 'Write ReqSys DEV runner manifest')) {
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $rendered = ($manifest | ConvertTo-Json -Depth 6) + [Environment]::NewLine
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($ManifestPath, $rendered, $utf8NoBom)
  }
}
$env:REQSYS_DEV_RUNNER_MANIFEST = $ManifestPath
python (Join-Path $repoRoot 'scripts\validate_reqsys_dev_runner.py') --manifest $ManifestPath --profile $Profile --repository $repoRoot
if ($LASTEXITCODE -ne 0) { throw 'RUNNER_PREFLIGHT_BLOCKED' }
Write-Host ('Assign these profile labels only after validation: ' + ($runnerLabels -join ', '))
