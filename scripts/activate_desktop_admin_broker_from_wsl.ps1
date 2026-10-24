[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("ACTIVATE-REQSYS-DESKTOP-ADMIN-BROKER")]
    [string]$Confirm
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ExpectedHost = "DESKTOP-PDQK954"
$TaskPath = "\Automation\"
$TaskName = "ReqSysDesktopAdminBroker"
$TaskFullName = "\Automation\ReqSysDesktopAdminBroker"

if ($env:COMPUTERNAME -ine $ExpectedHost) {
    throw "WRONG_HOST:$($env:COMPUTERNAME)"
}
if ($Confirm -ne "ACTIVATE-REQSYS-DESKTOP-ADMIN-BROKER") {
    throw "CONFIRMATION_INVALID"
}

function Test-ChildPath {
    param([string]$Child, [string]$Parent)
    try {
        $childFull = [System.IO.Path]::GetFullPath($Child).TrimEnd("\")
        $parentFull = [System.IO.Path]::GetFullPath($Parent).TrimEnd("\")
        return $childFull.StartsWith($parentFull + "\", [System.StringComparison]::OrdinalIgnoreCase)
    }
    catch {
        return $false
    }
}

function Get-BrokerTaskContract {
    try {
        $task = Get-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -ErrorAction Stop
    }
    catch {
        return [pscustomobject]@{
            Exists = $false
            AtStartup = $false
            S4U = $false
            Highest = $false
            Enabled = $false
            Ready = $false
        }
    }

    $atStartup = @(
        $task.Triggers | Where-Object {
            $_.CimClass.CimClassName -eq "MSFT_TaskBootTrigger"
        }
    ).Count -gt 0
    $s4u = ([string]$task.Principal.LogonType -eq "S4U")
    $highest = ([string]$task.Principal.RunLevel -eq "Highest")
    $enabled = ([bool]$task.Settings.Enabled) -and ([string]$task.State -ne "Disabled")

    return [pscustomobject]@{
        Exists = $true
        AtStartup = $atStartup
        S4U = $s4u
        Highest = $highest
        Enabled = $enabled
        Ready = ($atStartup -and $s4u -and $highest -and $enabled)
    }
}

$candidatePaths = [System.Collections.Generic.List[string]]::new()
if ($env:LOCALAPPDATA) {
    $candidatePaths.Add((Join-Path $env:LOCALAPPDATA "ReqSys\DesktopAdminBroker\metadata.json"))
}
$systemDrive = if ($env:SystemDrive) { $env:SystemDrive } else { "C:" }
$usersRoot = Join-Path $systemDrive "Users"
if (Test-Path -LiteralPath $usersRoot -PathType Container) {
    Get-ChildItem -LiteralPath $usersRoot -Directory -Force -ErrorAction SilentlyContinue |
        ForEach-Object {
            $candidatePaths.Add(
                (Join-Path $_.FullName "AppData\Local\ReqSys\DesktopAdminBroker\metadata.json")
            )
        }
}

$selected = $null
$rejections = [System.Collections.Generic.List[string]]::new()
foreach ($candidate in ($candidatePaths | Select-Object -Unique)) {
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        continue
    }
    try {
        $metadata = Get-Content -LiteralPath $candidate -Raw -Encoding UTF8 | ConvertFrom-Json
        $runtimeRoot = [System.IO.Path]::GetFullPath([string]$metadata.runtime_root)
        $metadataPath = [System.IO.Path]::GetFullPath($candidate)
        $expectedMetadata = Join-Path $runtimeRoot "metadata.json"
        $launcher = [System.IO.Path]::GetFullPath([string]$metadata.activation_launcher)
        $expectedLauncher = Join-Path $runtimeRoot "Activate-Desktop-Admin-Broker.cmd"
        $python = [System.IO.Path]::GetFullPath([string]$metadata.python_executable)
        $releaseRoot = [System.IO.Path]::GetFullPath([string]$metadata.release_root)
        $sourceSha = [string]$metadata.source_sha

        if ([string]$metadata.host -ine $ExpectedHost) { throw "host" }
        if ([string]$metadata.service -ne "reqsys-desktop-admin-broker") { throw "service" }
        if ($sourceSha -notmatch "^[a-f0-9]{40}$") { throw "source_sha" }
        if ($metadataPath -ine [System.IO.Path]::GetFullPath($expectedMetadata)) { throw "metadata_path" }
        if ($launcher -ine [System.IO.Path]::GetFullPath($expectedLauncher)) { throw "launcher_path" }
        if (-not (Test-ChildPath -Child $releaseRoot -Parent $runtimeRoot)) { throw "release_root" }
        if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw "launcher_missing" }
        if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "python_missing" }

        & $python -I -c "import win32com.client" 2>$null
        if ($LASTEXITCODE -ne 0) { throw "pywin32_missing" }

        $selected = [pscustomobject]@{
            MetadataPath = $metadataPath
            RuntimeRoot = $runtimeRoot
            Launcher = $launcher
            Python = $python
            SourceSha = $sourceSha
        }
        break
    }
    catch {
        $rejections.Add("$candidate::$($_.Exception.Message)")
    }
}

if ($null -eq $selected) {
    $summary = ($rejections | Select-Object -First 10) -join ";"
    throw "BROKER_METADATA_NOT_FOUND_OR_INVALID:$summary"
}

$contract = Get-BrokerTaskContract
if (-not $contract.Ready) {
    $argumentLine = '/d /s /c ""{0}""' -f $selected.Launcher
    $startParameters = @{
        FilePath = $env:ComSpec
        ArgumentList = $argumentLine
        Verb = "RunAs"
        Wait = $true
        PassThru = $true
    }
    $process = Start-Process @startParameters

    if ($process.ExitCode -ne 0) {
        throw "UAC_ACTIVATION_FAILED:$($process.ExitCode)"
    }

    $deadline = [DateTimeOffset]::UtcNow.AddSeconds(90)
    do {
        Start-Sleep -Seconds 1
        $contract = Get-BrokerTaskContract
    } until ($contract.Ready -or [DateTimeOffset]::UtcNow -ge $deadline)
}

if (-not $contract.Ready) {
    throw "TASK_CONTRACT_INVALID:$TaskFullName"
}

[ordered]@{
    Status = "ready"
    Task = $TaskFullName
    AtStartup = [bool]$contract.AtStartup
    S4U = [bool]$contract.S4U
    Highest = [bool]$contract.Highest
    Enabled = [bool]$contract.Enabled
    Python = $selected.Python
    Pywin32 = $true
    MetadataPath = $selected.MetadataPath
    SourceSha = $selected.SourceSha
    ProductionTouched = $false
    SecretsLogged = $false
    RebootPerformed = $false
} | ConvertTo-Json -Compress
