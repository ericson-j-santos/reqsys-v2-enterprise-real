param(
    [string]$ArtifactRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

function Assert-Equal {
    param([string]$Name, $Actual, $Expected)
    if ($Actual -ne $Expected) {
        throw "$Name mismatch. Expected '$Expected', got '$Actual'."
    }
    Write-Host "[PASS] $Name = $Actual"
}

function Assert-True {
    param([string]$Name, [bool]$Condition)
    if (-not $Condition) {
        throw "$Name failed."
    }
    Write-Host "[PASS] $Name"
}

$botPath = Join-Path $ArtifactRoot "pac-workspace/orchestrator/.mcs/botdefinition.json"
$connPath = Join-Path $ArtifactRoot "pac-workspace/orchestrator/.mcs/conn.json"
$changeTokenPath = Join-Path $ArtifactRoot "pac-workspace/orchestrator/.mcs/changetoken.txt"
$deliveryPath = Join-Path $ArtifactRoot "FINAL_DELIVERY.md"
$stgValidationPath = Join-Path $ArtifactRoot "STG_VALIDATION.md"
$managedZipPath = Join-Path $ArtifactRoot "ReqSysLowCodeCopilot_stg_managed.zip"
$unmanagedZipPath = Join-Path $ArtifactRoot "ReqSysLowCodeCopilot_stg_unmanaged.zip"
$checkerZipPath = Join-Path $ArtifactRoot "checker-stg-managed/202607140057493654_ReqSysLowCodeCopilot_df56.zip"
$fetchXmlPath = Join-Path $ArtifactRoot "fetch-stg-workflows.xml"
$devClonePath = Join-Path $ArtifactRoot "dev-clone/ReqSysCopilotStudioOrquestrador-DEV"
$stgClonePath = Join-Path $ArtifactRoot "stg-clone/ReqSysCopilotStudioOrquestrador-STG"

Assert-True "botdefinition.json exists" (Test-Path $botPath)
Assert-True "conn.json exists" (Test-Path $connPath)
Assert-True "changetoken.txt exists" (Test-Path $changeTokenPath)
Assert-True "FINAL_DELIVERY.md exists" (Test-Path $deliveryPath)
Assert-True "STG_VALIDATION.md exists" (Test-Path $stgValidationPath)
Assert-True "managed solution zip exists" (Test-Path $managedZipPath)
Assert-True "unmanaged solution zip exists" (Test-Path $unmanagedZipPath)
Assert-True "checker zip exists" (Test-Path $checkerZipPath)
Assert-True "fetch-stg-workflows.xml exists" (Test-Path $fetchXmlPath)
Assert-True "DEV clone exists" (Test-Path $devClonePath)
Assert-True "STG clone exists" (Test-Path $stgClonePath)

$bot = Get-Content -Raw $botPath | ConvertFrom-Json
$conn = Get-Content -Raw $connPath | ConvertFrom-Json
$delivery = Get-Content -Raw $deliveryPath

Assert-Equal "bot kind" $bot.'$kind' "BotDefinition"
Assert-Equal "agent name" $bot.entity.displayName "ReqSys Copilot Studio Orquestrador"
Assert-Equal "agent schema" $bot.entity.schemaName "reqsys_ReqSysCopilotStudioOrquestrador"
Assert-Equal "agent id" $bot.entity.cdsBotId "62303236-29a7-4d5e-acd3-68de1287d9df"
Assert-Equal "runtime provider" $bot.entity.runtimeProvider "PowerVirtualAgents"
Assert-Equal "agent state" $bot.entity.state "Active"
Assert-Equal "authentication mode" $bot.entity.authenticationMode "Integrated"
Assert-Equal "authentication trigger" $bot.entity.authenticationTrigger "Always"
Assert-Equal "access control policy" $bot.entity.accessControlPolicy "GroupMembership"
Assert-Equal "component count" $bot.components.Count 14
Assert-Equal "dialog component count" @($bot.components | Where-Object { $_.'$kind' -eq "DialogComponent" }).Count 13
Assert-Equal "gpt component count" @($bot.components | Where-Object { $_.'$kind' -eq "GptComponent" }).Count 1
Assert-Equal "environment variable count" $bot.environmentVariables.Count 10

Assert-Equal "generative actions enabled" $bot.entity.configuration.settings.GenerativeActionsEnabled $true
Assert-Equal "agent connectable" $bot.entity.configuration.isAgentConnectable $true
Assert-Equal "model knowledge enabled" $bot.entity.configuration.aISettings.useModelKnowledge $true
Assert-Equal "file analysis enabled" $bot.entity.configuration.aISettings.isFileAnalysisEnabled $true
Assert-Equal "semantic search enabled" $bot.entity.configuration.aISettings.isSemanticSearchEnabled $true

Assert-Equal "dataverse endpoint" $conn.DataverseEndpoint "https://orga258f260.crm2.dynamics.com/"
Assert-Equal "environment id" $conn.EnvironmentId "Default-6d09c88c-0617-490c-8329-305e577684bc"
Assert-Equal "tenant id" $conn.AccountInfo.TenantId "6d09c88c-0617-490c-8329-305e577684bc"
Assert-Equal "conn agent id" $conn.AgentId "62303236-29a7-4d5e-acd3-68de1287d9df"
Assert-Equal "copilot studio solution version" $conn.SolutionVersions.CopilotStudioSolutionVersion "2026.5.4.20551445"

$requiredTopics = @(
    "Multiple Topics Matched",
    "Reset Conversation",
    "Sign in",
    "On Error",
    "Fallback",
    "Thank you",
    "Goodbye",
    "Greeting",
    "Start Over",
    "Escalate",
    "End of Conversation",
    "Conversation Start",
    "Conversational boosting"
)

$componentNames = @($bot.components | ForEach-Object { $_.displayName })
foreach ($topic in $requiredTopics) {
    Assert-True "topic present: $topic" ($componentNames -contains $topic)
}

$requiredEnvironmentVariables = @(
    "reqsys_TeamsWebhookUrl",
    "reqsys_EquipeId",
    "reqsys_GrupoId",
    "reqsys_PlanoId",
    "reqsys_CanalId"
)

$environmentVariableSchemas = @($bot.environmentVariables | ForEach-Object { $_.schemaName })
foreach ($schemaName in $requiredEnvironmentVariables) {
    Assert-True "environment variable present: $schemaName" ($environmentVariableSchemas -contains $schemaName)
}

$botHash = (Get-FileHash $botPath -Algorithm SHA256).Hash
$connHash = (Get-FileHash $connPath -Algorithm SHA256).Hash
$managedZipHash = (Get-FileHash $managedZipPath -Algorithm SHA256).Hash
$unmanagedZipHash = (Get-FileHash $unmanagedZipPath -Algorithm SHA256).Hash
$checkerZipHash = (Get-FileHash $checkerZipPath -Algorithm SHA256).Hash

Assert-Equal "botdefinition.json SHA256" $botHash "69D6C52DA9A982A7F28FBD49C8667540EC8ABE913F60D896048460FE53986F64"
Assert-Equal "conn.json SHA256" $connHash "7CE04281D12701869CEA8305E760FBC7BFB9470DE1E8FECD4336A4CB481A355E"
Assert-Equal "managed solution zip SHA256" $managedZipHash "A2BD56A1AFD7797FB435A40F26877EB13CBEFF0B7868325E677E6C84797E0D45"
Assert-Equal "unmanaged solution zip SHA256" $unmanagedZipHash "D9426847293C26ECA2531FEF58029DE6D254BCDC793834DEBDB5A4C0F08BFD69"
Assert-Equal "checker zip SHA256" $checkerZipHash "78458040590A6B5CBA4B5CF08ED1FA548072882F956C9FCED6C34FB3B6991CAF"

$managedZipEntries = @(tar -tf $managedZipPath)
$unmanagedZipEntries = @(tar -tf $unmanagedZipPath)
$checkerZipEntries = @(tar -tf $checkerZipPath)

foreach ($entry in @("customizations.xml", "solution.xml", "Workflows/ReqSys-Aprovacaoderequisito-780422AE-8C74-57FC-8895-04F7F3513C33.json", "botcomponents/reqsys_ReqSysCopilotStudioOrquestrador.gpt.default/data")) {
    Assert-True "managed zip entry present: $entry" ($managedZipEntries -contains $entry)
    Assert-True "unmanaged zip entry present: $entry" ($unmanagedZipEntries -contains $entry)
}

Assert-True "checker sarif present" ($checkerZipEntries -contains "202607140057493654_ReqSysLowCodeCopilot_df56.sarif")

$devAgentPath = Join-Path $devClonePath "agent.mcs.yml"
$devSettingsPath = Join-Path $devClonePath "settings.mcs.yml"
$stgSettingsPath = Join-Path $stgClonePath "settings.mcs.yml"
$devTopicFiles = @(Get-ChildItem (Join-Path $devClonePath "topics") -Filter "*.mcs.yml" -File)

Assert-True "DEV agent metadata exists" (Test-Path $devAgentPath)
Assert-True "DEV settings metadata exists" (Test-Path $devSettingsPath)
Assert-True "STG settings metadata exists" (Test-Path $stgSettingsPath)
Assert-Equal "DEV topic file count" $devTopicFiles.Count 17
Assert-True "DEV clone documents multiagent orchestration" ((Get-Content -Raw $devAgentPath).Contains("orquestrador multiagente low-code"))
Assert-True "DEV clone disables direct external writes" ((Get-Content -Raw $devAgentPath).Contains("Nunca execute escrita externa diretamente"))
Assert-True "STG clone preserves GroupMembership" ((Get-Content -Raw $stgSettingsPath).Contains("accessControlPolicy: GroupMembership"))
Assert-True "STG clone preserves Integrated authentication" ((Get-Content -Raw $stgSettingsPath).Contains("authenticationMode: Integrated"))

Assert-True "FINAL_DELIVERY documents agent id" $delivery.Contains("62303236-29a7-4d5e-acd3-68de1287d9df")
Assert-True "FINAL_DELIVERY documents dataverse endpoint" $delivery.Contains("https://orga258f260.crm2.dynamics.com/")
Assert-True "FINAL_DELIVERY documents E2E validation" $delivery.Contains("scripts/validate-e2e.ps1")
Assert-True "FINAL_DELIVERY documents managed zip" $delivery.Contains("ReqSysLowCodeCopilot_stg_managed.zip")
Assert-True "FINAL_DELIVERY documents STG validation" $delivery.Contains("STG_VALIDATION.md")
Assert-True "FINAL_DELIVERY documents DEV clone" $delivery.Contains("dev-clone/ReqSysCopilotStudioOrquestrador-DEV")

Write-Host ""
Write-Host "E2E validation completed successfully."
