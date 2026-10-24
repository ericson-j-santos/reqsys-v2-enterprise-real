[CmdletBinding(SupportsShouldProcess)]
param(
  [Parameter(Mandatory = $true)][ValidatePattern('^[a-z0-9][a-z0-9-]{7,63}$')][string]$RunnerInstanceId,
  [Parameter(Mandatory = $true)][string]$RuntimeRoot,
  [Parameter(Mandatory = $true)][string]$RunnerRoot,
  [ValidateSet('base', 'runtime', 'ollama')][string]$Profile = 'base',
  [string]$ManifestPath = "$env:ProgramData\ReqSys\runner-pool.json",
  [string]$RunnerServiceName = '',
  [switch]$RestartRunnerService,
  [switch]$ApplyGitHubLabels,
  [string]$AuthorizationPhrase = ''
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$onboarding = Join-Path $PSScriptRoot 'onboard_reqsys_dev_runner.ps1'

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw 'ADMINISTRATOR_REQUIRED'
}
if (-not (Test-Path -LiteralPath $RunnerRoot -PathType Container)) {
  throw 'RUNNER_ROOT_INVALID'
}
$resolvedRunnerRoot = (Resolve-Path -LiteralPath $RunnerRoot).Path
$runnerMetadata = Join-Path $resolvedRunnerRoot '.runner'
if (-not (Test-Path -LiteralPath $runnerMetadata -PathType Leaf)) {
  throw 'GITHUB_RUNNER_METADATA_MISSING'
}
if ($RunnerServiceName -and $RunnerServiceName -notmatch '^actions\.runner\.[A-Za-z0-9_.-]+$') {
  throw 'RUNNER_SERVICE_NAME_INVALID'
}
if ($RestartRunnerService -and [string]::IsNullOrWhiteSpace($RunnerServiceName)) {
  $runnerServices = @(Get-Service -Name 'actions.runner.*' -ErrorAction SilentlyContinue)
  if ($runnerServices.Count -ne 1) {
    throw 'RUNNER_SERVICE_NAME_REQUIRED_OR_AMBIGUOUS'
  }
  $RunnerServiceName = $runnerServices[0].Name
}
if ($ApplyGitHubLabels -and $AuthorizationPhrase -cne 'APPLY-REQSYS-DEV-RUNNER-LABELS') {
  throw 'GITHUB_LABEL_CONFIRMATION_REQUIRED'
}

& $onboarding `
  -RunnerInstanceId $RunnerInstanceId `
  -RuntimeRoot $RuntimeRoot `
  -Profile $Profile `
  -ManifestPath $ManifestPath
if ($LASTEXITCODE -ne 0) { throw 'RUNNER_ONBOARDING_BLOCKED' }

$resolvedManifest = (Resolve-Path -LiteralPath $ManifestPath).Path
$manifest = Get-Content -LiteralPath $resolvedManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$runnerEnv = Join-Path $resolvedRunnerRoot '.env'
$existing = @()
if (Test-Path -LiteralPath $runnerEnv -PathType Leaf) {
  $existing = @(Get-Content -LiteralPath $runnerEnv -Encoding UTF8)
}
$updated = @(
  $existing | Where-Object { $_ -notmatch '^REQSYS_DEV_RUNNER_MANIFEST=' }
)
$updated += "REQSYS_DEV_RUNNER_MANIFEST=$resolvedManifest"
$rendered = ($updated -join [Environment]::NewLine) + [Environment]::NewLine
$temporary = "$runnerEnv.reqsys.tmp"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

if ($PSCmdlet.ShouldProcess($runnerEnv, 'Configure ReqSys DEV runner manifest environment')) {
  [IO.File]::WriteAllText($temporary, $rendered, $utf8NoBom)
  Move-Item -LiteralPath $temporary -Destination $runnerEnv -Force
}

$serviceRestarted = $false
if ($RestartRunnerService) {
  $service = Get-Service -Name $RunnerServiceName -ErrorAction Stop
  if ($PSCmdlet.ShouldProcess($RunnerServiceName, 'Restart GitHub Actions runner service once')) {
    Restart-Service -Name $RunnerServiceName -Force
    $service.WaitForStatus('Running', [TimeSpan]::FromSeconds(30))
    $service.Refresh()
    if ($service.Status -ne 'Running') { throw 'RUNNER_SERVICE_NOT_RUNNING' }
    $serviceRestarted = $true
  }
}

$labelsApplied = $false
if ($ApplyGitHubLabels) {
  if (-not (Get-Command gh -CommandType Application -ErrorAction SilentlyContinue)) {
    throw 'GH_CLI_REQUIRED'
  }
  $runner = Get-Content -LiteralPath $runnerMetadata -Raw -Encoding UTF8 | ConvertFrom-Json
  $runnerId = [int]$runner.agentId
  if ($runnerId -lt 1) { throw 'GITHUB_RUNNER_ID_INVALID' }
  $currentLabels = @(
    & gh api `
      "repos/ericson-j-santos/reqsys-v2-enterprise-real/actions/runners/$runnerId" `
      --jq '.labels[].name'
  )
  if ($LASTEXITCODE -ne 0) { throw 'GITHUB_RUNNER_LABEL_READ_FAILED' }
  $managedLabels = @(
    'reqsys-dev',
    'reqsys-dev-base-v1',
    'reqsys-dev-runtime-v1',
    'reqsys-dev-ollama-v1',
    'reqsys-dev-pool-v1',
    'reqsys-cap-base-v1',
    'reqsys-cap-runtime-v1',
    'reqsys-cap-ollama-v1'
  )
  $preservedLabels = @(
    $currentLabels | Where-Object {
      $_ -notin @('self-hosted', 'Windows', 'X64') -and $_ -notin $managedLabels
    }
  )
  $profileLabels = @(
    $manifest.runner_labels | Where-Object { $_ -notin @('self-hosted', 'Windows', 'X64') }
  )
  $desiredLabels = @($preservedLabels + $profileLabels | Sort-Object -Unique)
  $payload = @{ labels = $desiredLabels } | ConvertTo-Json -Compress
  if ($PSCmdlet.ShouldProcess("GitHub runner $runnerId", 'Replace managed labels with validated profile labels')) {
    $null = $payload | & gh api --method PUT `
      "repos/ericson-j-santos/reqsys-v2-enterprise-real/actions/runners/$runnerId/labels" `
      --input -
    if ($LASTEXITCODE -ne 0) { throw 'GITHUB_RUNNER_LABEL_RECONCILE_FAILED' }
    $labelsApplied = $true
  }
}

[ordered]@{
  status = 'configured'
  profile = $Profile
  runner_instance_id = $RunnerInstanceId
  runner_labels = @($manifest.runner_labels)
  manifest_environment_configured = $true
  service_restarted = $serviceRestarted
  github_labels_applied = $labelsApplied
  environment = 'dev'
  automatic_retry_enabled = $false
  production_touched = $false
} | ConvertTo-Json -Depth 5
