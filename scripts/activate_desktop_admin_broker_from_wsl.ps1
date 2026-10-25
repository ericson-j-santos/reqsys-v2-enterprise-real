[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("ACTIVATE-REQSYS-DESKTOP-ADMIN-BROKER")]
    [string]$Confirm,

    [switch]$Elevated
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

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
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
            Python = ""
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
    $action = @($task.Actions | Where-Object { $_.CimClass.CimClassName -eq "MSFT_TaskExecAction" }) |
        Select-Object -First 1
    $python = if ($null -ne $action) { [string]$action.Execute } else { "" }

    return [pscustomobject]@{
        Exists = $true
        AtStartup = $atStartup
        S4U = $s4u
        Highest = $highest
        Enabled = $enabled
        Ready = ($atStartup -and $s4u -and $highest -and $enabled)
        Python = $python
    }
}

function Assert-PythonContract {
    param([string]$Python)
    if ([string]::IsNullOrWhiteSpace($Python) -or -not (Test-Path -LiteralPath $Python -PathType Leaf)) {
        throw "PYTHON_MISSING"
    }
    & $Python -I -c "import win32com.client" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "PYWIN32_MISSING"
    }
}

function Write-ReadyEvidence {
    param(
        [pscustomobject]$Contract,
        [string]$Python,
        [string]$MetadataPath = "",
        [string]$SourceSha = ""
    )
    [ordered]@{
        Status = "ready"
        Task = $TaskFullName
        AtStartup = [bool]$Contract.AtStartup
        S4U = [bool]$Contract.S4U
        Highest = [bool]$Contract.Highest
        Enabled = [bool]$Contract.Enabled
        Python = $Python
        Pywin32 = $true
        MetadataPath = $MetadataPath
        SourceSha = $SourceSha
        ProductionTouched = $false
        SecretsLogged = $false
        RebootPerformed = $false
    } | ConvertTo-Json -Compress
}

$isAdministrator = Test-IsAdministrator
if (-not $isAdministrator -and -not $Elevated) {
    if ([string]::IsNullOrWhiteSpace($PSCommandPath)) {
        throw "ACTIVATOR_PATH_UNAVAILABLE"
    }
    $sourceHash = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $stageRoot = Join-Path $env:LOCALAPPDATA "ReqSys\WslPowerShellBridge\releases"
    $stageDirectory = Join-Path $stageRoot $sourceHash
    $stagedScript = Join-Path $stageDirectory "activate_desktop_admin_broker_from_wsl.ps1"
    New-Item -ItemType Directory -Path $stageDirectory -Force | Out-Null
    Copy-Item -LiteralPath $PSCommandPath -Destination $stagedScript -Force
    $stagedHash = (Get-FileHash -LiteralPath $stagedScript -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($stagedHash -ne $sourceHash) {
        throw "STAGED_ACTIVATOR_HASH_MISMATCH"
    }

    $powershell = Join-Path $PSHOME "powershell.exe"
    $arguments = @(
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        ('"{0}"' -f $stagedScript),
        "-Confirm",
        "ACTIVATE-REQSYS-DESKTOP-ADMIN-BROKER",
        "-Elevated"
    )
    $startParameters = @{
        FilePath = $powershell
        ArgumentList = $arguments
        Verb = "RunAs"
        Wait = $true
        PassThru = $true
    }
    $process = Start-Process @startParameters
    if ($process.ExitCode -ne 0) {
        throw "UAC_ACTIVATION_FAILED:$($process.ExitCode)"
    }

    $contract = Get-BrokerTaskContract
    if (-not $contract.Ready) {
        throw "TASK_CONTRACT_INVALID_AFTER_UAC:$TaskFullName"
    }
    Assert-PythonContract -Python $contract.Python
    Write-ReadyEvidence -Contract $contract -Python $contract.Python
    return
}

if ($Elevated -and -not $isAdministrator) {
    throw "ELEVATED_TOKEN_REQUIRED"
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
        Assert-PythonContract -Python $python

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
    $process = Start-Process -FilePath $env:ComSpec -ArgumentList $argumentLine -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "BROKER_LAUNCHER_FAILED:$($process.ExitCode)"
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
Assert-PythonContract -Python $contract.Python
Write-ReadyEvidence -Contract $contract -Python $contract.Python -MetadataPath $selected.MetadataPath -SourceSha $selected.SourceSha
