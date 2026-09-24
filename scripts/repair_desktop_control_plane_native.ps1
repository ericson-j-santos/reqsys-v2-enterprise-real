#requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ExpectedHost = 'DESKTOP-PDQK954'
$AutomationFolder = '\Automation'
$BrokerTask = 'ReqSysDesktopAdminBroker'
$WatchdogTask = 'ReqSysDesktopControlPlaneWatchdog'
$S4U = 2
$RunLevelHighest = 1
$RunLevelLimited = 0
$TaskCreateOrUpdate = 6
$TaskTriggerBoot = 8
$TaskActionExec = 0
$TaskInstancesIgnoreNew = 2

function Write-RepairEvidence {
    param([hashtable]$Payload)
    $root = Join-Path $env:LOCALAPPDATA 'ReqSys\DesktopControlPlaneNativeRepair'
    New-Item -ItemType Directory -Force -Path $root | Out-Null
    $Payload['production_touched'] = $false
    $Payload['secrets_read'] = $false
    $Payload['reboot_performed'] = $false
    $Payload['generated_at_utc'] = [DateTime]::UtcNow.ToString('o')
    $Payload | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $root 'last.json')
    $Payload | ConvertTo-Json -Compress -Depth 8
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Resolve-GovernedRuntime {
    param(
        [Parameter(Mandatory = $true)][string]$RuntimeRoot,
        [Parameter(Mandatory = $true)][string]$Service
    )
    $expected = [IO.Path]::GetFullPath($RuntimeRoot)
    $metadataPath = Join-Path $expected 'metadata.json'
    if (-not (Test-Path -LiteralPath $metadataPath -PathType Leaf)) {
        throw "$Service metadata ausente: $metadataPath"
    }
    $metadata = Get-Content -LiteralPath $metadataPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$metadata.host -ine $ExpectedHost) {
        throw "$Service metadata pertence a host diferente"
    }
    $sourceSha = [string]$metadata.source_sha
    if ($sourceSha -notmatch '^[0-9a-fA-F]{40}$') {
        throw "$Service source_sha invalido"
    }
    $metadataRuntime = [IO.Path]::GetFullPath([string]$metadata.runtime_root)
    if ($metadataRuntime.TrimEnd('\') -ine $expected.TrimEnd('\')) {
        throw "$Service runtime_root divergente"
    }
    $expectedRelease = [IO.Path]::GetFullPath((Join-Path $expected ('releases\' + $sourceSha.ToLowerInvariant())))
    $releaseRoot = [IO.Path]::GetFullPath([string]$metadata.release_root)
    if ($releaseRoot.TrimEnd('\') -ine $expectedRelease.TrimEnd('\')) {
        throw "$Service release_root divergente"
    }
    $python = [IO.Path]::GetFullPath([string]$metadata.python_executable)
    $launcher = Join-Path $expected 'run.py'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw "$Service Python instalado ausente"
    }
    if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
        throw "$Service run.py ausente"
    }
    return @{
        service = $Service
        metadata_path = $metadataPath
        runtime_root = $expected
        release_root = $releaseRoot
        source_sha = $sourceSha.ToLowerInvariant()
        python = $python
        launcher = $launcher
    }
}

function Get-SchedulerFolder {
    param([object]$Service)
    try {
        return $Service.GetFolder($AutomationFolder)
    }
    catch {
        $root = $Service.GetFolder('\')
        return $root.CreateFolder($AutomationFolder.TrimStart('\'))
    }
}

function Register-GovernedTask {
    param(
        [Parameter(Mandatory = $true)][object]$Scheduler,
        [Parameter(Mandatory = $true)][hashtable]$Runtime,
        [Parameter(Mandatory = $true)][string]$TaskLeaf,
        [Parameter(Mandatory = $true)][string]$Description,
        [Parameter(Mandatory = $true)][int]$RunLevel,
        [Parameter(Mandatory = $true)][string]$Delay
    )
    $folder = Get-SchedulerFolder -Service $Scheduler
    $definition = $Scheduler.NewTask(0)
    $definition.RegistrationInfo.Description = $Description
    $definition.Settings.Enabled = $true
    $definition.Settings.StartWhenAvailable = $true
    $definition.Settings.MultipleInstances = $TaskInstancesIgnoreNew
    $definition.Settings.ExecutionTimeLimit = 'PT0S'
    try {
        $definition.Settings.RestartCount = 999
        $definition.Settings.RestartInterval = 'PT1M'
    } catch {}

    $trigger = $definition.Triggers.Create($TaskTriggerBoot)
    $trigger.Enabled = $true
    $trigger.Delay = $Delay

    $action = $definition.Actions.Create($TaskActionExec)
    $action.Path = $Runtime.python
    $action.Arguments = '"' + $Runtime.launcher + '"'
    $action.WorkingDirectory = $Runtime.runtime_root

    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $definition.Principal.UserId = $identity
    $definition.Principal.LogonType = $S4U
    $definition.Principal.RunLevel = $RunLevel

    $null = $folder.RegisterTaskDefinition($TaskLeaf, $definition, $TaskCreateOrUpdate, $identity, $null, $S4U, $null)

    $task = $folder.GetTask($TaskLeaf)
    $registered = $task.Definition
    $startupFound = $false
    for ($i = 1; $i -le $registered.Triggers.Count; $i++) {
        if ($registered.Triggers.Item($i).Type -eq $TaskTriggerBoot) {
            $startupFound = $true
            break
        }
    }
    if (-not $startupFound) { throw "$TaskLeaf sem trigger AtStartup" }
    if ($registered.Principal.LogonType -ne $S4U) { throw "$TaskLeaf sem S4U" }
    if ($registered.Principal.RunLevel -ne $RunLevel) { throw "$TaskLeaf com RunLevel divergente" }

    $null = $task.Run($null)
    return @{
        task = ($AutomationFolder + '\' + $TaskLeaf)
        trigger_at_startup = $true
        logon_type = 'S4U'
        run_level = $(if ($RunLevel -eq $RunLevelHighest) { 'highest' } else { 'limited' })
        started = $true
    }
}

try {
    if ($env:COMPUTERNAME -ine $ExpectedHost) {
        throw "launcher permitido somente em $ExpectedHost"
    }

    if (-not (Test-IsAdministrator)) {
        $arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'))
        $process = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -Verb RunAs -PassThru
        Write-RepairEvidence @{
            ok = $true
            result = 'UAC_LAUNCHED'
            elevated_process_id = $process.Id
        }
        exit 0
    }

    $brokerRoot = Join-Path $env:LOCALAPPDATA 'ReqSys\DesktopAdminBroker'
    $watchdogRoot = Join-Path $env:LOCALAPPDATA 'ReqSys\DesktopControlPlaneWatchdog'
    $broker = Resolve-GovernedRuntime -RuntimeRoot $brokerRoot -Service 'DesktopAdminBroker'
    $watchdog = Resolve-GovernedRuntime -RuntimeRoot $watchdogRoot -Service 'DesktopControlPlaneWatchdog'

    $scheduler = New-Object -ComObject 'Schedule.Service'
    $scheduler.Connect()

    $watchdogArgs = @{
        Scheduler = $scheduler
        Runtime = $watchdog
        TaskLeaf = $WatchdogTask
        Description = 'ReqSys Desktop control-plane watchdog: RDC + GitHub Actions runner'
        RunLevel = $RunLevelLimited
        Delay = 'PT20S'
    }
    $watchdogTaskResult = Register-GovernedTask @watchdogArgs

    $brokerArgs = @{
        Scheduler = $scheduler
        Runtime = $broker
        TaskLeaf = $BrokerTask
        Description = 'ReqSys Desktop privileged admin broker'
        RunLevel = $RunLevelHighest
        Delay = 'PT30S'
    }
    $brokerTaskResult = Register-GovernedTask @brokerArgs

    Write-RepairEvidence @{
        ok = $true
        result = 'DESKTOP_CONTROL_PLANE_NATIVE_REPAIRED'
        host = $env:COMPUTERNAME
        broker_source_sha = $broker.source_sha
        watchdog_source_sha = $watchdog.source_sha
        broker_task = $brokerTaskResult
        watchdog_task = $watchdogTaskResult
    }
    exit 0
}
catch {
    Write-RepairEvidence @{
        ok = $false
        result = 'DESKTOP_CONTROL_PLANE_NATIVE_REPAIR_BLOCKED'
        host = $env:COMPUTERNAME
        error = $_.Exception.Message
        error_type = $_.Exception.GetType().Name
    }
    exit 2
}
