param(
    [string]$TaskName = 'ReqSys-QualidadeIA-Snapshot-Diario',
    [int]$Hora = 8,
    [int]$Minuto = 0,
    [string]$ProjetoDir = ''
)

$ErrorActionPreference = 'Stop'

if ($Hora -lt 0 -or $Hora -gt 23) {
    throw 'Parametro Hora deve estar entre 0 e 23.'
}
if ($Minuto -lt 0 -or $Minuto -gt 59) {
    throw 'Parametro Minuto deve estar entre 0 e 59.'
}

if ([string]::IsNullOrWhiteSpace($ProjetoDir)) {
    $ProjetoDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

$runnerScript = Join-Path $ProjetoDir 'scripts\executar-snapshot-qualidade-ia.ps1'
if (-not (Test-Path $runnerScript)) {
    throw "Script runner nao encontrado: $runnerScript"
}

$startBoundary = [datetime]::Today.AddHours($Hora).AddMinutes($Minuto)
if ($startBoundary -lt (Get-Date)) {
    $startBoundary = $startBoundary.AddDays(1)
}

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File \"$runnerScript\" -ProjetoDir \"$ProjetoDir\""
$trigger = New-ScheduledTaskTrigger -Daily -At $startBoundary
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Limited -LogonType Interactive

try {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force -ErrorAction Stop | Out-Null
}
catch {
    throw "Falha ao registrar tarefa '$TaskName'. Execute o PowerShell como Administrador ou remova restricoes de politica local. Erro: $($_.Exception.Message)"
}

Write-Host "Tarefa agendada com sucesso: $TaskName" -ForegroundColor Green
Write-Host "Execucao diaria em: $($startBoundary.ToString('HH:mm'))"
Write-Host "Projeto: $ProjetoDir"
