#requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ExpectedHost = 'DESKTOP-PDQK954'
$AutomationFolder = '\Automation'
$WatchdogTask = 'ReqSysDesktopControlPlaneWatchdog'
$S4U = 2
$RunLevelLimited = 0
$TaskCreateOrUpdate = 6
$TaskTriggerBoot = 8
$TaskActionExec = 0
$TaskInstancesIgnoreNew = 2

function Write-RepairEvidence {
    param([hashtable]$Payload)
    $root = Join-Path $env:LOCALAPPDATA 'ReqSys\DesktopWatchdogNativeRepair'
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

function Resolve-WatchdogRuntime {
    $runtimeRoot = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'ReqSys\DesktopControlPlaneWatchdog'))
    $metadataPath = Join-Path $runtimeRoot 'metadata.json'
    if (-not (Test-Path -LiteralPath $metadataPath -PathType Leaf)) {
        throw "watchdog metadata ausente: $metadataPath"
    }
    $metadata = Get-Content -LiteralPath $metadataPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$metadata.host -ine $ExpectedHost) { throw 'watchdog metadata pertence a host diferente' }
    $sourceSha = [string]$metadata.source_sha
    if ($sourceSha -notmatch '^[0-9a-fA-F]{40}$') { throw 'watchdog source_sha invalido' }
    $metadataRuntime = [IO.Path]::GetFullPath([string]$metadata.runtime_root)
    if ($metadataRuntime.TrimEnd('\') -ine $runtimeRoot.TrimEnd('\')) {
        throw 'watchdog runtime_root divergente'
    }
    $expectedRelease = [IO.Path]::GetFullPath((Join-Path $runtimeRoot ('releases\' + $sourceSha.ToLowerInvariant())))
    $releaseRoot = [IO.Path]::GetFullPath([string]$metadata.release_root)
    if ($releaseRoot.TrimEnd('\') -ine $expectedRelease.TrimEnd('\')) {
        throw 'watchdog release_root divergente'
    }
    $python = [IO.Path]::GetFullPath([string]$metadata.python_executable)
    $launcher = Join-Path $runtimeRoot 'run.py'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'watchdog Python instalado ausente' }
    if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw 'watchdog run.py ausente' }
    return @{
        runtime_root = $runtimeRoot
        release_root = $releaseRoot
        metadata_path = $metadataPath
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

function Register-WatchdogTask {
    param(
        [Parameter(Mandatory = $true)][object]$Scheduler,
        [Parameter(Mandatory = $true)][hashtable]$Runtime
    )
    $folder = Get-SchedulerFolder -Service $Scheduler
    $definition = $Scheduler.NewTask(0)
    $definition.RegistrationInfo.Description = 'ReqSys Desktop control-plane watchdog: RDC + GitHub Actions runner'
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
    $trigger.Delay = 'PT20S'

    $action = $definition.Actions.Create($TaskActionExec)
    $action.Path = $Runtime.python
    $action.Arguments = '"' + $Runtime.launcher + '"'
    $action.WorkingDirectory = $Runtime.runtime_root

    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $definition.Principal.UserId = $identity
    $definition.Principal.LogonType = $S4U
    $definition.Principal.RunLevel = $RunLevelLimited
    $null = $folder.RegisterTaskDefinition(
        $WatchdogTask,
        $definition,
        $TaskCreateOrUpdate,
        $identity,
        $null,
        $S4U,
        $null
    )

    $task = $folder.GetTask($WatchdogTask)
    $registered = $task.Definition
    $startupFound = $false
    for ($i = 1; $i -le $registered.Triggers.Count; $i++) {
        if ($registered.Triggers.Item($i).Type -eq $TaskTriggerBoot) {
            $startupFound = $true
            break
        }
    }
    if (-not $registered.Settings.Enabled) { throw "$WatchdogTask desabilitada" }
    if (-not $startupFound) { throw "$WatchdogTask sem trigger AtStartup" }
    if ($registered.Principal.LogonType -ne $S4U) { throw "$WatchdogTask sem S4U" }
    if ($registered.Principal.RunLevel -ne $RunLevelLimited) { throw "$WatchdogTask com RunLevel divergente" }

    $null = $task.Run($null)
    return @{
        task = ($AutomationFolder + '\' + $WatchdogTask)
        enabled = $true
        trigger_at_startup = $true
        logon_type = 'S4U'
        run_level = 'limited'
        started = $true
    }
}

try {
    if ($env:COMPUTERNAME -ine $ExpectedHost) { throw "launcher permitido somente em $ExpectedHost" }
    if (-not (Test-IsAdministrator)) {
        $arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'))
        $process = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -Verb RunAs -Wait -PassThru
        exit $process.ExitCode
    }

    $runtime = Resolve-WatchdogRuntime
    $scheduler = New-Object -ComObject 'Schedule.Service'
    $scheduler.Connect()
    $taskResult = Register-WatchdogTask -Scheduler $scheduler -Runtime $runtime
    Write-RepairEvidence @{
        ok = $true
        result = 'DESKTOP_WATCHDOG_NATIVE_REPAIRED'
        host = $env:COMPUTERNAME
        source_sha = $runtime.source_sha
        watchdog_task = $taskResult
    }
    exit 0
}
catch {
    Write-RepairEvidence @{
        ok = $false
        result = 'DESKTOP_WATCHDOG_NATIVE_REPAIR_BLOCKED'
        host = $env:COMPUTERNAME
        error = $_.Exception.Message
        error_type = $_.Exception.GetType().Name
    }
    exit 2
}
