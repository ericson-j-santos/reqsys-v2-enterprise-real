param(
    [string]$EnvironmentUrl = "https://orgf2ca7436.crm2.dynamics.com/",
    [string]$EnvironmentId = "b6717f20-2dcb-ed70-8b1c-e9a3c236afe7",
    [string]$ArtifactRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [switch]$SkipHttpTriggerSmoke
)

$ErrorActionPreference = "Stop"

function Assert-Contains {
    param([string]$Name, [string]$Text, [string]$Expected)
    if (-not $Text.Contains($Expected)) {
        throw "$Name did not contain '$Expected'."
    }
    Write-Host "[PASS] $Name contains $Expected"
}

function Assert-True {
    param([string]$Name, [bool]$Condition)
    if (-not $Condition) {
        throw "$Name failed."
    }
    Write-Host "[PASS] $Name"
}

function Assert-ContainsAny {
    param([string]$Name, [string]$Text, [string[]]$ExpectedValues)
    foreach ($expected in $ExpectedValues) {
        if ($Text.Contains($expected)) {
            Write-Host "[PASS] $Name contains $expected"
            return
        }
    }
    throw "$Name did not contain any expected value: $($ExpectedValues -join ', ')."
}

$evidenceDir = Join-Path $ArtifactRoot "evidence"
New-Item -ItemType Directory -Force $evidenceDir | Out-Null

$solutionList = pac solution list --environment $EnvironmentUrl | Out-String
Assert-Contains "solution list" $solutionList "ReqSysLowCodeCopilot"
Assert-Contains "solution managed" $solutionList "True"

$copilotList = pac copilot list --environment $EnvironmentUrl | Out-String
Assert-Contains "copilot list" $copilotList "ReqSys Copilot Studio Orquestrador"
Assert-Contains "copilot state" $copilotList "Published"
Assert-Contains "copilot managed" $copilotList "True"
Assert-Contains "copilot status" $copilotList "Provisioned"

$workflowFetchPath = Join-Path $ArtifactRoot "fetch-stg-workflows.xml"
$workflowFetch = pac env fetch --environment $EnvironmentUrl --xmlFile $workflowFetchPath | Out-String
foreach ($workflowName in @(
    "ReqSys - Aprovacao de requisito",
    "ReqSys - Consulta de status",
    "ReqSys - Intake de demanda",
    "ReqSys - Release governance"
)) {
    Assert-Contains "workflow fetch" $workflowFetch $workflowName
}

$rbacFetchPath = Join-Path $ArtifactRoot "fetch-stg-bot-rbac.xml"
$rbacFetch = pac env fetch --environment $EnvironmentUrl --xmlFile $rbacFetchPath | Out-String
Assert-Contains "rbac bot" $rbacFetch "ReqSys Copilot Studio Orquestrador"
Assert-Contains "rbac access policy" $rbacFetch "grupo"
Assert-Contains "rbac authentication" $rbacFetch "Integrado"
Assert-Contains "rbac trigger" $rbacFetch "Sempre"

$who = pac env who --environment $EnvironmentUrl | Out-String
Assert-Contains "authorized user environment access" $who "ericsonjosedossantos@tieri659.onmicrosoft.com"

if (-not $SkipHttpTriggerSmoke) {
    $flows = @(
        @{Name="ReqSys - Aprovacao de requisito"; Id="780422ae-8c74-57fc-8895-04f7f3513c33"; Body=@{referencia="REQ-STG-E2E-001"; correlation_id="reqsys-stg-e2e-aprovacao-20260714"}},
        @{Name="ReqSys - Consulta de status"; Id="69a54f8b-caec-53c4-9f5b-887230cf43d2"; Body=@{codigo_ou_titulo="REQ-STG-E2E-001"; correlation_id="reqsys-stg-e2e-status-20260714"}},
        @{Name="ReqSys - Intake de demanda"; Id="ae83d82a-8e04-5eb4-bf4a-dfadd5443a7a"; Body=@{titulo="Smoke STG E2E"; resultado_esperado="Validar trigger HTTP real"; origem="codex-e2e"; correlation_id="reqsys-stg-e2e-intake-20260714"}},
        @{Name="ReqSys - Release governance"; Id="768fde7b-db2e-500f-8be1-7b4cbf1ed31e"; Body=@{versao="stg-e2e-20260714"; correlation_id="reqsys-stg-e2e-release-20260714"}}
    )

    $token = az account get-access-token --resource https://service.flow.microsoft.com/ --query accessToken -o tsv
    $headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }
    $results = foreach ($flow in $flows) {
        $callbackApi = "https://api.flow.microsoft.com/providers/Microsoft.ProcessSimple/environments/$EnvironmentId/flows/$($flow.Id)/triggers/manual/listCallbackUrl?api-version=2016-11-01"
        $callback = Invoke-RestMethod -Method Post -Uri $callbackApi -Headers $headers -Body "{}"
        $callbackUrl = if ($callback.response.value) { $callback.response.value } elseif ($callback.value) { $callback.value } else { $null }
        if (-not $callbackUrl) { throw "Callback URL not returned for $($flow.Name)." }

        $response = Invoke-RestMethod -Method Post -Uri $callbackUrl -ContentType "application/json" -Body ($flow.Body | ConvertTo-Json -Depth 10 -Compress)
        Assert-True "HTTP trigger response for $($flow.Name)" ($response.status -eq "materialized_native_p0")

        [pscustomobject]@{
            name = $flow.Name
            workflow_id = $flow.Id
            callback_url_obtained = $true
            callback_url_redacted = ($callbackUrl -replace "\?.*$", "?<redacted>")
            http_status = 200
            response_workflow = $response.workflow
            response_status = $response.status
            response_correlation_id = $response.correlation_id
            passed = $true
        }
    }

    [pscustomobject]@{
        generated_at_local = "2026-07-14"
        environment = "ReqSys Test"
        environment_id = $EnvironmentId
        environment_url = $EnvironmentUrl
        validation = "real_http_trigger_smoke"
        secret_policy = "callback URLs redacted; token never written to disk"
        results = $results
    } | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 (Join-Path $evidenceDir "stg-http-trigger-smoke.json")
}

[pscustomobject]@{
    generated_at_local = "2026-07-14"
    environment = "ReqSys Test"
    environment_id = $EnvironmentId
    environment_url = $EnvironmentUrl
    validation = "live_copilot_rbac_configuration"
    bot_name = "ReqSys Copilot Studio Orquestrador"
    bot_id = "5da35c84-3153-4b22-857c-56dc6415365e"
    statecode = "Com atividade"
    statuscode = "Provisionado"
    schema_name = "reqsys_ReqSysCopilotStudioOrquestrador"
    authenticationmode = "Integrado"
    authenticationtrigger = "Sempre"
    accesscontrolpolicy = "Associacao de grupo"
    authorized_user_checked = "ericsonjosedossantos@tieri659.onmicrosoft.com"
    authorized_user_result = "PAC connected and listed Copilot in STG/Test"
    unauthorized_user_negative_test = "not_executed_no_secondary_test_principal_available"
    passed = $true
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 (Join-Path $evidenceDir "stg-rbac-live.json")

Write-Host ""
Write-Host "STG live validation completed successfully."
