#requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ExpectedHost = 'DESKTOP-PDQK954'
$AutomationFolder = '\Automation'
$WatchdogTask = 'ReqSysDesktopControlPlaneWatchdog'
$S4U = 2
$RunLevelLimited = 0
$TaskUpdate = 4
$TaskTriggerBoot = 8
$TaskActionExec = 0

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
    $localRoot = [IO.Path]::GetFullPath($env:LOCALAPPDATA).TrimEnd('\') + '\'
    if (-not $python.StartsWith($localRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'WATCHDOG_PYTHON_OUTSIDE_LOCALAPPDATA'
    }
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
    # Esta rota repara apenas a tarefa existente; ausência muda o escopo.
    return $Service.GetFolder($AutomationFolder)
}

function Test-SamePath {
    param([string]$Observed, [string]$Expected)
    if ([string]::IsNullOrWhiteSpace($Observed) -or [string]::IsNullOrWhiteSpace($Expected)) { return $false }
    try {
        $left = [IO.Path]::GetFullPath($Observed.Trim().Trim('"'))
        $right = [IO.Path]::GetFullPath($Expected)
        return [string]::Equals($left, $right, [StringComparison]::OrdinalIgnoreCase)
    } catch { return $false }
}

function Get-TaskContract {
    param([object]$Definition, [hashtable]$Runtime)
    $boot = $false
    for ($i = 1; $i -le $Definition.Triggers.Count; $i++) {
        $candidate = $Definition.Triggers.Item($i)
        if ($candidate.Type -eq $TaskTriggerBoot -and $candidate.Enabled) { $boot = $true }
    }
    $oneAction = $Definition.Actions.Count -eq 1
    $action = if ($oneAction) { $Definition.Actions.Item(1) } else { $null }
    return @{
        enabled = [bool]$Definition.Settings.Enabled
        trigger_at_startup = $boot
        logon_s4u = $Definition.Principal.LogonType -eq $S4U
        runlevel_limited = $Definition.Principal.RunLevel -eq $RunLevelLimited
        one_exec_action = $oneAction -and $action.Type -eq $TaskActionExec
        command_matches = $oneAction -and (Test-SamePath -Observed $action.Path -Expected $Runtime.python)
        arguments_match = $oneAction -and (Test-SamePath -Observed $action.Arguments -Expected $Runtime.launcher)
        working_dir_matches = $oneAction -and (Test-SamePath -Observed $action.WorkingDirectory -Expected $Runtime.runtime_root)
    }
}

function Test-ApprovedDrift {
    param([hashtable]$Checks)
    return (
        $Checks.enabled -and $Checks.trigger_at_startup -and $Checks.logon_s4u -and
        $Checks.one_exec_action -and $Checks.arguments_match -and $Checks.working_dir_matches -and
        -not $Checks.runlevel_limited -and -not $Checks.command_matches
    )
}

function Register-WatchdogTask {
    param(
        [Parameter(Mandatory = $true)][object]$Scheduler,
        [Parameter(Mandatory = $true)][hashtable]$Runtime
    )
    $folder = Get-SchedulerFolder -Service $Scheduler
    $previousTask = $folder.GetTask($WatchdogTask)
    $previousDefinition = $previousTask.Definition
    $previousXml = [string]$previousDefinition.XmlText
    if ([string]::IsNullOrWhiteSpace($previousXml)) { throw 'WATCHDOG_ROLLBACK_SNAPSHOT_UNAVAILABLE' }
    $previousChecks = Get-TaskContract -Definition $previousDefinition -Runtime $Runtime
    if (-not (Test-ApprovedDrift -Checks $previousChecks)) { throw 'WATCHDOG_DRIFT_PROFILE_CHANGED' }
    $identity = [string]$previousDefinition.Principal.UserId
    if ([string]::IsNullOrWhiteSpace($identity)) { throw 'WATCHDOG_PRINCIPAL_MISSING' }

    # Clona o XML anterior para limitar a mutação aos dois campos observados.
    $definition = $Scheduler.NewTask(0)
    $definition.XmlText = $previousXml
    $action = $definition.Actions.Item(1)
    $action.Path = $Runtime.python
    $definition.Principal.RunLevel = $RunLevelLimited
    $script:RegistrationAttempted = $true
    try {
        $null = $folder.RegisterTaskDefinition(
            $WatchdogTask, $definition, $TaskUpdate, $identity, $null, $S4U, $null
        )
        $task = $folder.GetTask($WatchdogTask)
        $checks = Get-TaskContract -Definition $task.Definition -Runtime $Runtime
        if (@($checks.Values | Where-Object { $_ -ne $true }).Count -ne 0) {
            throw 'WATCHDOG_POSTCHECK_FAILED'
        }
        $null = $task.Run($null)
    } catch {
        $script:RollbackAttempted = $true
        try {
            $null = $folder.RegisterTaskDefinition(
                $WatchdogTask, $previousDefinition, $TaskUpdate, $identity, $null, $S4U, $null
            )
            $restored = $folder.GetTask($WatchdogTask)
            $script:RollbackVerified = [string]::Equals(
                [string]$restored.Definition.XmlText, $previousXml, [StringComparison]::Ordinal
            )
        } catch { $script:RollbackVerified = $false }
        throw 'WATCHDOG_REPAIR_FAILED_ROLLBACK_ATTEMPTED'
    }
    return @{
        task = ($AutomationFolder + '\' + $WatchdogTask)
        enabled = $true
        trigger_at_startup = $true
        logon_type = 'S4U'
        run_level = 'limited'
        command_matches = $true
        arguments_match = $true
        working_dir_matches = $true
        rollback_required = $false
        started = $true
    }
}

try {
    $script:RegistrationAttempted = $false
    $script:RollbackAttempted = $false
    $script:RollbackVerified = $false
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
        registration_attempted = $script:RegistrationAttempted
        rollback_attempted = $script:RollbackAttempted
    }
    exit 0
}
catch {
    Write-RepairEvidence @{
        ok = $false
        result = 'DESKTOP_WATCHDOG_NATIVE_REPAIR_BLOCKED'
        host = $env:COMPUTERNAME
        error = if ($_.Exception.Message -in @(
            'WATCHDOG_DRIFT_PROFILE_CHANGED', 'WATCHDOG_PRINCIPAL_MISSING',
            'WATCHDOG_REPAIR_FAILED_ROLLBACK_ATTEMPTED'
        )) { $_.Exception.Message } else { 'WATCHDOG_REPAIR_PRECONDITION_OR_COM_FAILED' }
        error_type = $_.Exception.GetType().Name
        registration_attempted = $script:RegistrationAttempted
        rollback_attempted = $script:RollbackAttempted
        rollback_verified = $script:RollbackVerified
    }
    exit 2
}


