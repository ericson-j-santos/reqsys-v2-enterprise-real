param(
  [string]$EnvironmentUrl = "https://orga258f260.crm2.dynamics.com/",
  [string]$SolutionName = "ReqSysLowCodeCopilot",
  [string]$OutDir = "artifacts/lowcode-solution-factory/copilot-observability-dashboard"
)

$ErrorActionPreference = "Stop"

function New-LocalizedLabel([string]$label, [int]$languageCode = 1046) {
  @{
    LocalizedLabels = @(@{ Label = $label; LanguageCode = $languageCode })
    UserLocalizedLabel = @{ Label = $label; LanguageCode = $languageCode }
  }
}

function Get-DataverseToken([string]$resource) {
  az account get-access-token --resource $resource --query accessToken -o tsv
}

function Invoke-Dv {
  param(
    [ValidateSet("GET", "POST", "PUT", "PATCH", "DELETE")]
    [string]$Method,
    [string]$Path,
    [object]$Body = $null,
    [switch]$Allow404
  )

  $uri = "$EnvironmentUrl/api/data/v9.2/$Path"
  $headers = @{
    Authorization = "Bearer $script:Token"
    "OData-MaxVersion" = "4.0"
    "OData-Version" = "4.0"
    Accept = "application/json"
    "Content-Type" = "application/json; charset=utf-8"
    "MSCRM.SolutionUniqueName" = $SolutionName
  }

  try {
    if ($null -eq $Body) {
      return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -TimeoutSec 120
    }
    $json = $Body | ConvertTo-Json -Depth 30
    return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -Body $json -TimeoutSec 120
  } catch {
    $status = $_.Exception.Response.StatusCode.value__
    if ($Allow404 -and $status -eq 404) {
      return $null
    }
    throw
  }
}

function Ensure-Entity {
  $existing = Invoke-Dv -Method GET -Path "EntityDefinitions(LogicalName='reqsys_copilotexecucao')?`$select=MetadataId,LogicalName" -Allow404
  if ($existing) {
    return @{ changed = $false; metadataId = $existing.MetadataId }
  }

  $body = @{
    "@odata.type" = "Microsoft.Dynamics.CRM.EntityMetadata"
    SchemaName = "reqsys_CopilotExecucao"
    DisplayName = New-LocalizedLabel "ReqSys Copilot Execucao"
    DisplayCollectionName = New-LocalizedLabel "ReqSys Copilot Execucoes"
    Description = New-LocalizedLabel "Telemetria de execucoes do Copilot Studio e flows ReqSys."
    OwnershipType = "UserOwned"
    HasActivities = $false
    HasNotes = $false
    IsActivity = $false
    Attributes = @(
      @{
      "@odata.type" = "Microsoft.Dynamics.CRM.StringAttributeMetadata"
      SchemaName = "reqsys_Name"
      DisplayName = New-LocalizedLabel "Nome"
      RequiredLevel = @{ Value = "None"; CanBeChanged = $true; ManagedPropertyLogicalName = "canmodifyrequirementlevelsettings" }
      MaxLength = 200
      IsPrimaryName = $true
      FormatName = @{ Value = "Text" }
      }
    )
  }
  Invoke-Dv -Method POST -Path "EntityDefinitions" -Body $body | Out-Null
  $created = Invoke-Dv -Method GET -Path "EntityDefinitions(LogicalName='reqsys_copilotexecucao')?`$select=MetadataId,LogicalName"
  return @{ changed = $true; metadataId = $created.MetadataId }
}

function Attribute-Exists([string]$logicalName) {
  $attr = Invoke-Dv -Method GET -Path "EntityDefinitions(LogicalName='reqsys_copilotexecucao')/Attributes(LogicalName='$logicalName')?`$select=MetadataId" -Allow404
  return $null -ne $attr
}

function Ensure-StringAttribute([string]$schemaName, [string]$logicalName, [string]$displayName, [int]$maxLength = 200) {
  if (Attribute-Exists $logicalName) { return $false }
  $body = @{
    "@odata.type" = "Microsoft.Dynamics.CRM.StringAttributeMetadata"
    SchemaName = $schemaName
    DisplayName = New-LocalizedLabel $displayName
    RequiredLevel = @{ Value = "None"; CanBeChanged = $true; ManagedPropertyLogicalName = "canmodifyrequirementlevelsettings" }
    MaxLength = $maxLength
    FormatName = @{ Value = "Text" }
  }
  Invoke-Dv -Method POST -Path "EntityDefinitions(LogicalName='reqsys_copilotexecucao')/Attributes" -Body $body | Out-Null
  return $true
}

function Ensure-MemoAttribute([string]$schemaName, [string]$logicalName, [string]$displayName) {
  if (Attribute-Exists $logicalName) { return $false }
  $body = @{
    "@odata.type" = "Microsoft.Dynamics.CRM.MemoAttributeMetadata"
    SchemaName = $schemaName
    DisplayName = New-LocalizedLabel $displayName
    RequiredLevel = @{ Value = "None"; CanBeChanged = $true; ManagedPropertyLogicalName = "canmodifyrequirementlevelsettings" }
    MaxLength = 4000
    Format = "TextArea"
  }
  Invoke-Dv -Method POST -Path "EntityDefinitions(LogicalName='reqsys_copilotexecucao')/Attributes" -Body $body | Out-Null
  return $true
}

function Ensure-IntegerAttribute([string]$schemaName, [string]$logicalName, [string]$displayName) {
  if (Attribute-Exists $logicalName) { return $false }
  $body = @{
    "@odata.type" = "Microsoft.Dynamics.CRM.IntegerAttributeMetadata"
    SchemaName = $schemaName
    DisplayName = New-LocalizedLabel $displayName
    RequiredLevel = @{ Value = "None"; CanBeChanged = $true; ManagedPropertyLogicalName = "canmodifyrequirementlevelsettings" }
    MinValue = 0
    MaxValue = 2147483647
    Format = "None"
  }
  Invoke-Dv -Method POST -Path "EntityDefinitions(LogicalName='reqsys_copilotexecucao')/Attributes" -Body $body | Out-Null
  return $true
}

function Ensure-DateTimeAttribute([string]$schemaName, [string]$logicalName, [string]$displayName) {
  if (Attribute-Exists $logicalName) { return $false }
  $body = @{
    "@odata.type" = "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata"
    SchemaName = $schemaName
    DisplayName = New-LocalizedLabel $displayName
    RequiredLevel = @{ Value = "None"; CanBeChanged = $true; ManagedPropertyLogicalName = "canmodifyrequirementlevelsettings" }
    Format = "DateAndTime"
    DateTimeBehavior = @{ Value = "UserLocal" }
  }
  Invoke-Dv -Method POST -Path "EntityDefinitions(LogicalName='reqsys_copilotexecucao')/Attributes" -Body $body | Out-Null
  return $true
}

function Ensure-SavedQuery([string]$name, [string]$fetchXml, [string]$layoutXml) {
  $encoded = [System.Uri]::EscapeDataString("name eq '$name' and returnedtypecode eq 'reqsys_copilotexecucao'")
  $existing = Invoke-Dv -Method GET -Path "savedqueries?`$select=savedqueryid,name&`$filter=$encoded"
  if ($existing.value.Count -gt 0) {
    return @{ changed = $false; id = $existing.value[0].savedqueryid }
  }
  $body = @{
    name = $name
    returnedtypecode = "reqsys_copilotexecucao"
    querytype = 0
    fetchxml = $fetchXml
    layoutxml = $layoutXml
    isdefault = $false
  }
  Invoke-Dv -Method POST -Path "savedqueries" -Body $body | Out-Null
  $created = Invoke-Dv -Method GET -Path "savedqueries?`$select=savedqueryid,name&`$filter=$encoded"
  return @{ changed = $true; id = $created.value[0].savedqueryid }
}

function Ensure-Chart([string]$name, [string]$dataXml, [string]$presentationXml) {
  $encoded = [System.Uri]::EscapeDataString("name eq '$name' and primaryentitytypecode eq 'reqsys_copilotexecucao'")
  $existing = Invoke-Dv -Method GET -Path "savedqueryvisualizations?`$select=savedqueryvisualizationid,name&`$filter=$encoded"
  if ($existing.value.Count -gt 0) {
    return @{ changed = $false; id = $existing.value[0].savedqueryvisualizationid }
  }
  $body = @{
    name = $name
    primaryentitytypecode = "reqsys_copilotexecucao"
    datadescription = $dataXml
    presentationdescription = $presentationXml
    isdefault = $false
  }
  Invoke-Dv -Method POST -Path "savedqueryvisualizations" -Body $body | Out-Null
  $created = Invoke-Dv -Method GET -Path "savedqueryvisualizations?`$select=savedqueryvisualizationid,name&`$filter=$encoded"
  return @{ changed = $true; id = $created.value[0].savedqueryvisualizationid }
}

function Publish-All {
  Invoke-Dv -Method POST -Path "PublishAllXml" -Body @{} | Out-Null
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$script:Token = Get-DataverseToken $EnvironmentUrl

$summary = [ordered]@{
  environment_url = $EnvironmentUrl
  solution_name = $SolutionName
  table = "reqsys_copilotexecucao"
  created_or_updated_at = (Get-Date).ToString("o")
  entity = $null
  attributes_changed = @()
  savedqueries = @()
  charts = @()
  model_app = $null
}

$summary.entity = Ensure-Entity

$attrs = @(
  @{ kind="string"; schema="reqsys_CorrelationId"; logical="reqsys_correlationid"; label="Correlation ID"; max=200 },
  @{ kind="string"; schema="reqsys_Topico"; logical="reqsys_topico"; label="Topico"; max=120 },
  @{ kind="string"; schema="reqsys_Flow"; logical="reqsys_flow"; label="Flow"; max=160 },
  @{ kind="string"; schema="reqsys_Ambiente"; logical="reqsys_ambiente"; label="Ambiente"; max=80 },
  @{ kind="string"; schema="reqsys_Status"; logical="reqsys_status"; label="Status"; max=80 },
  @{ kind="string"; schema="reqsys_Usuario"; logical="reqsys_usuario"; label="Usuario"; max=200 },
  @{ kind="memo"; schema="reqsys_EntradaResumo"; logical="reqsys_entradaresumo"; label="Entrada - resumo" },
  @{ kind="memo"; schema="reqsys_SaidaResumo"; logical="reqsys_saidaresumo"; label="Saida - resumo" },
  @{ kind="memo"; schema="reqsys_Erro"; logical="reqsys_erro"; label="Erro" },
  @{ kind="integer"; schema="reqsys_DuracaoMs"; logical="reqsys_duracaoms"; label="Duracao (ms)" },
  @{ kind="datetime"; schema="reqsys_ExecutadoEm"; logical="reqsys_executadoem"; label="Executado em" }
)

foreach ($attr in $attrs) {
  $changed = $false
  if ($attr.kind -eq "string") { $changed = Ensure-StringAttribute $attr.schema $attr.logical $attr.label $attr.max }
  if ($attr.kind -eq "memo") { $changed = Ensure-MemoAttribute $attr.schema $attr.logical $attr.label }
  if ($attr.kind -eq "integer") { $changed = Ensure-IntegerAttribute $attr.schema $attr.logical $attr.label }
  if ($attr.kind -eq "datetime") { $changed = Ensure-DateTimeAttribute $attr.schema $attr.logical $attr.label }
  if ($changed) { $summary.attributes_changed += $attr.logical }
}

Publish-All

$layout = @"
<grid name="resultset" object="1" jump="reqsys_name" select="1" icon="1" preview="1">
  <row name="result" id="reqsys_copilotexecucaoid">
    <cell name="reqsys_executadoem" width="140" />
    <cell name="reqsys_topico" width="160" />
    <cell name="reqsys_flow" width="220" />
    <cell name="reqsys_status" width="100" />
    <cell name="reqsys_correlationid" width="220" />
    <cell name="reqsys_duracaoms" width="100" />
    <cell name="reqsys_erro" width="260" />
  </row>
</grid>
"@

$recentFetch = @"
<fetch version="1.0" mapping="logical" count="100">
  <entity name="reqsys_copilotexecucao">
    <attribute name="reqsys_name" />
    <attribute name="reqsys_executadoem" />
    <attribute name="reqsys_topico" />
    <attribute name="reqsys_flow" />
    <attribute name="reqsys_status" />
    <attribute name="reqsys_correlationid" />
    <attribute name="reqsys_duracaoms" />
    <attribute name="reqsys_erro" />
    <order attribute="reqsys_executadoem" descending="true" />
  </entity>
</fetch>
"@
$summary.savedqueries += Ensure-SavedQuery "ReqSys Copilot - Execucoes recentes" $recentFetch $layout

$errorsFetch = @"
<fetch version="1.0" mapping="logical" count="100">
  <entity name="reqsys_copilotexecucao">
    <attribute name="reqsys_name" />
    <attribute name="reqsys_executadoem" />
    <attribute name="reqsys_topico" />
    <attribute name="reqsys_flow" />
    <attribute name="reqsys_status" />
    <attribute name="reqsys_correlationid" />
    <attribute name="reqsys_erro" />
    <filter>
      <condition attribute="reqsys_status" operator="ne" value="ok" />
    </filter>
    <order attribute="reqsys_executadoem" descending="true" />
  </entity>
</fetch>
"@
$summary.savedqueries += Ensure-SavedQuery "ReqSys Copilot - Falhas e alertas" $errorsFetch $layout

$chartByTopicData = @"
<datadefinition>
  <fetchcollection>
    <fetch mapping="logical" aggregate="true">
      <entity name="reqsys_copilotexecucao">
        <attribute name="reqsys_topico" groupby="true" alias="groupby_column" />
        <attribute name="reqsys_copilotexecucaoid" aggregate="count" alias="aggregate_column" />
      </entity>
    </fetch>
  </fetchcollection>
  <categorycollection>
    <category alias="groupby_column">
      <measurecollection>
        <measure alias="aggregate_column" />
      </measurecollection>
    </category>
  </categorycollection>
</datadefinition>
"@
$chartByTopicPresentation = @"
<Chart Palette="None" PaletteCustomColors="91,151,213; 237,125,49; 160,116,166; 255,192,0; 68,114,196; 112,173,71; 37,94,145; 158,72,14; 117,55,125; 153,115,0; 38,68,120; 67,104,43; 124,175,221; 241,151,90; 186,144,192; 255,205,51; 105,142,208; 140,193,104; 50,125,194; 210,96,18; 150,83,159; 204,154,0; 51,90,161; 90,138,57;"><Series><Series ChartType="Column" IsValueShownAsLabel="True" Font="{0}, 9.5px" LabelForeColor="59, 59, 59" CustomProperties="PointWidth=0.75, MaxPixelPointWidth=40" /></Series><ChartAreas><ChartArea BorderColor="White" BorderDashStyle="Solid"><AxisY LabelAutoFitMinFontSize="8" TitleForeColor="59, 59, 59" TitleFont="{0}, 10.5px" LineColor="165, 172, 181" IntervalAutoMode="VariableCount"><MajorGrid LineColor="239, 242, 246" /><MajorTickMark LineColor="165, 172, 181" /><LabelStyle Font="{0}, 10.5px" ForeColor="59, 59, 59" /></AxisY><AxisX LabelAutoFitMinFontSize="8" TitleForeColor="59, 59, 59" TitleFont="{0}, 10.5px" LineColor="165, 172, 181" IntervalAutoMode="VariableCount"><MajorTickMark LineColor="165, 172, 181" /><MajorGrid LineColor="Transparent" /><LabelStyle Font="{0}, 10.5px" ForeColor="59, 59, 59" /></AxisX></ChartArea></ChartAreas><Titles><Title Alignment="TopLeft" DockingOffset="-3" Font="{0}, 13px" ForeColor="59, 59, 59" /></Titles></Chart>
"@
$summary.charts += Ensure-Chart "ReqSys Copilot - Execucoes por topico" $chartByTopicData $chartByTopicPresentation

$chartByStatusData = @"
<datadefinition>
  <fetchcollection>
    <fetch mapping="logical" aggregate="true">
      <entity name="reqsys_copilotexecucao">
        <attribute name="reqsys_status" groupby="true" alias="groupby_column" />
        <attribute name="reqsys_copilotexecucaoid" aggregate="count" alias="aggregate_column" />
      </entity>
    </fetch>
  </fetchcollection>
  <categorycollection>
    <category alias="groupby_column">
      <measurecollection>
        <measure alias="aggregate_column" />
      </measurecollection>
    </category>
  </categorycollection>
</datadefinition>
"@
$chartByStatusPresentation = @"
<Chart Palette="None" PaletteCustomColors="112,173,71; 237,125,49; 192,80,77; 68,114,196; 91,151,213; 160,116,166; 255,192,0;"><Series><Series ChartType="Doughnut" IsValueShownAsLabel="True" Font="{0}, 9.5px" LabelForeColor="59, 59, 59" /></Series><ChartAreas><ChartArea BorderColor="White" BorderDashStyle="Solid" /></ChartAreas><Legends><Legend Alignment="Center" LegendStyle="Table" Docking="Bottom" IsEquallySpacedItems="True" Font="{0}, 10.5px" ForeColor="59, 59, 59" /></Legends><Titles><Title Alignment="TopLeft" DockingOffset="-3" Font="{0}, 13px" ForeColor="59, 59, 59" /></Titles></Chart>
"@
$summary.charts += Ensure-Chart "ReqSys Copilot - Execucoes por status" $chartByStatusData $chartByStatusPresentation

Publish-All

$summaryPath = Join-Path $OutDir "provision-summary.json"
$summary | ConvertTo-Json -Depth 20 | Set-Content -Path $summaryPath -Encoding UTF8

Write-Host "Provisionamento concluido."
Write-Host "Tabela: reqsys_copilotexecucao"
Write-Host "Resumo: $summaryPath"
