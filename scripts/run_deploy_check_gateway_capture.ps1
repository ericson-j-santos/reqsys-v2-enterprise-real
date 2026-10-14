[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Python,
    [Parameter(Mandatory = $true)][string]$CaptureScript,
    [Parameter(Mandatory = $true)][string]$Gateway,
    [Parameter(Mandatory = $true)][string]$StdoutPath,
    [Parameter(Mandatory = $true)][string]$StderrPath,
    [Parameter(Mandatory = $true)][string[]]$GatewayArgs
)

$ErrorActionPreference = "Stop"
& $Python $CaptureScript --stdout-path $StdoutPath --stderr-path $StderrPath -- $Python $Gateway @GatewayArgs
exit $LASTEXITCODE
