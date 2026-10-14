[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$PythonPath)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$wrapper = Join-Path $root "scripts\run_deploy_check_gateway_capture.ps1"
$capture = Join-Path $root "scripts\private_process_capture.py"
$parser = Join-Path $root "scripts\deploy_check_receipt.py"
$fixture = Join-Path $root "tests\fixtures\deploy_check_gateway_fixture.py"
$sha = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
$correlation = "corr-wrapper-1"
$session = "session-wrapper-1"

$cases = @(
    @{ Mode = "blocked"; Exit = 20; Reason = "gateway_blocked" },
    @{ Mode = "malformed"; Exit = 24; Reason = "gateway_stream_encoding_invalid" },
    @{ Mode = "command-failed"; Exit = 1; Reason = "database_probe_failed" }
)

foreach ($case in $cases) {
    $stdoutPath = Join-Path $env:RUNNER_TEMP "wrapper-$($case.Mode).stdout"
    $stderrPath = Join-Path $env:RUNNER_TEMP "wrapper-$($case.Mode).stderr"
    try {
        $gatewayArgs = @("--mode", $case.Mode, "--sha", $sha, "--correlation-id", $correlation, "--session-id", $session)
        $wrapperParams = @{
            Python = $PythonPath
            CaptureScript = $capture
            Gateway = $fixture
            StdoutPath = $stdoutPath
            StderrPath = $stderrPath
            GatewayArgs = $gatewayArgs
        }
        $wrapperOutput = @(& $wrapper @wrapperParams)
        $wrapperExit = $LASTEXITCODE
        if ($wrapperOutput.Count -ne 0) { throw "wrapper emitted public output for $($case.Mode)" }
        if ($wrapperExit -ne $case.Exit) { throw "unexpected wrapper exit for $($case.Mode): $wrapperExit" }

        $receiptOutput = @(& $PythonPath $parser --gateway-exit-code $wrapperExit --gateway-stdout-file $stdoutPath --gateway-stderr-file $stderrPath --expected-sha $sha --expected-correlation-id $correlation --expected-session-id $session --host "WINDOWS-CI")
        if ($receiptOutput.Count -ne 1) { throw "parser output count invalid for $($case.Mode)" }
        $receipt = $receiptOutput[0] | ConvertFrom-Json
        if ($receipt.reason_code -ne $case.Reason) { throw "unexpected reason for $($case.Mode): $($receipt.reason_code)" }
        foreach ($privateValue in @("PRIVATE_BLOCK_DETAIL", "PRIVATE_INVALID", "PRIVATE_COMMAND_STDERR")) {
            if ($receiptOutput[0].Contains($privateValue)) { throw "private stream data leaked for $($case.Mode)" }
        }
    }
    finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}
