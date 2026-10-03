$ErrorActionPreference = 'Stop'

$environmentUrl = 'https://orga258f260.crm2.dynamics.com'
$solutionName = 'ReqSysLowCode'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $root '..\..\..')
$manifestPath = Join-Path $repoRoot 'artifacts\lowcode-solution-factory\reqsys-lowcode\manifest.json'
$solutionZip = Join-Path $root 'ReqSysLowCode_unmanaged.zip'
$evidencePath = Join-Path $root 'materialization-evidence.json'

function New-Label([string]$text) {
  return @{
    '@odata.type' = 'Microsoft.Dynamics.CRM.Label'
    LocalizedLabels = @(
      @{
        '@odata.type' = 'Microsoft.Dynamics.CRM.LocalizedLabel'
        Label = $text
        LanguageCode = 1033
      }
    )
  }
}

function New-HtmlContent([string]$title, [string]$body) {
  $encoded = [System.Net.WebUtility]::HtmlEncode($body)
  $html = "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>$title</title><style>body{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#111827}pre{white-space:pre-wrap;background:#f8fafc;border:1px solid #cbd5e1;padding:16px;border-radius:6px}h1{font-size:22px}</style></head><body><h1>$title</h1><pre>$encoded</pre></body></html>"
  return [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($html))
}

function Invoke-Dataverse {
  param(
    [ValidateSet('GET', 'POST', 'PATCH', 'PUT')]
    [string]$Method,
    [string]$Path,
    [object]$Body = $null,
    [switch]$NoSolutionHeader
  )

  $headers = @{
    Authorization = "Bearer $script:token"
    Accept = 'application/json'
    'Content-Type' = 'application/json; charset=utf-8'
    'OData-MaxVersion' = '4.0'
    'OData-Version' = '4.0'
  }
  if (-not $NoSolutionHeader) {
    $headers['MSCRM.SolutionUniqueName'] = $solutionName
  }

  $uri = "$environmentUrl/api/data/v9.2/$Path"
  if ($null -eq $Body) {
    return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers
  }

  $json = $Body | ConvertTo-Json -Depth 30
  return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -Body $json
}

function Test-EntityExists([string]$logicalName) {
  try {
    Invoke-Dataverse -Method GET -Path "EntityDefinitions(LogicalName='$logicalName')?`$select=LogicalName" -NoSolutionHeader | Out-Null
    return $true
  } catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 404) { return $false }
    throw
  }
}

function Test-AttributeExists([string]$entityLogicalName, [string]$logicalName) {
  try {
    Invoke-Dataverse -Method GET -Path "EntityDefinitions(LogicalName='$entityLogicalName')/Attributes(LogicalName='$logicalName')?`$select=LogicalName" -NoSolutionHeader | Out-Null
    return $true
  } catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 404) { return $false }
    throw
  }
}

function New-RequiredLevel([bool]$required) {
  return @{
    Value = if ($required) { 'ApplicationRequired' } else { 'None' }
    CanBeChanged = $true
    ManagedPropertyLogicalName = 'canmodifyrequirementlevelsettings'
  }
}

function New-StringAttribute([string]$schemaName, [string]$displayName, [int]$maxLength, [bool]$required) {
  return @{
    '@odata.type' = 'Microsoft.Dynamics.CRM.StringAttributeMetadata'
    SchemaName = $schemaName
    DisplayName = New-Label $displayName
    Description = New-Label $displayName
    RequiredLevel = New-RequiredLevel $required
    MaxLength = $maxLength
    FormatName = @{ Value = 'Text' }
  }
}

function New-MemoAttribute([string]$schemaName, [string]$displayName) {
  return @{
    '@odata.type' = 'Microsoft.Dynamics.CRM.MemoAttributeMetadata'
    SchemaName = $schemaName
    DisplayName = New-Label $displayName
    Description = New-Label $displayName
    RequiredLevel = New-RequiredLevel $false
    MaxLength = 4000
    FormatName = @{ Value = 'TextArea' }
  }
}

function New-IntegerAttribute([string]$schemaName, [string]$displayName) {
  return @{
    '@odata.type' = 'Microsoft.Dynamics.CRM.IntegerAttributeMetadata'
    SchemaName = $schemaName
    DisplayName = New-Label $displayName
    Description = New-Label $displayName
    RequiredLevel = New-RequiredLevel $false
    MinValue = 0
    MaxValue = 1000000
    Format = 'None'
  }
}

function New-DateTimeAttribute([string]$schemaName, [string]$displayName) {
  return @{
    '@odata.type' = 'Microsoft.Dynamics.CRM.DateTimeAttributeMetadata'
    SchemaName = $schemaName
    DisplayName = New-Label $displayName
    Description = New-Label $displayName
    RequiredLevel = New-RequiredLevel $false
    Format = 'DateAndTime'
    DateTimeBehavior = @{ Value = 'UserLocal' }
  }
}

function New-PicklistAttribute([string]$schemaName, [string]$displayName, [string[]]$options) {
  $value = 100000000
  $items = foreach ($option in $options) {
    @{
      Value = $value++
      Label = New-Label $option
    }
  }
  return @{
    '@odata.type' = 'Microsoft.Dynamics.CRM.PicklistAttributeMetadata'
    SchemaName = $schemaName
    DisplayName = New-Label $displayName
    Description = New-Label $displayName
    RequiredLevel = New-RequiredLevel $false
    OptionSet = @{
      '@odata.type' = 'Microsoft.Dynamics.CRM.OptionSetMetadata'
      IsGlobal = $false
      OptionSetType = 'Picklist'
      Options = @($items)
    }
  }
}

function Convert-SchemaName([string]$logicalName) {
  $parts = $logicalName -split '_'
  if ($parts.Count -lt 2) { return $logicalName }
  $prefix = $parts[0]
  $tail = ($parts[1..($parts.Count - 1)] | ForEach-Object {
    if ($_.Length -eq 0) { $_ } else { $_.Substring(0, 1).ToUpperInvariant() + $_.Substring(1) }
  }) -join ''
  return "${prefix}_$tail"
}

function New-AttributePayload($column, $choices) {
  $schemaName = Convert-SchemaName $column.name
  $displayName = if ($column.display_name) { [string]$column.display_name } else { $schemaName }
  $required = if ($column.required) { [bool]$column.required } else { $false }
  switch ([string]$column.type) {
    'text' {
      $maxLength = 250
      if ($column.PSObject.Properties.Name -contains 'max_length' -and $column.max_length) {
        $maxLength = [int]$column.max_length
      }
      return New-StringAttribute $schemaName $displayName $maxLength $required
    }
    'multiline_text' { return New-MemoAttribute $schemaName $displayName }
    'whole_number' { return New-IntegerAttribute $schemaName $displayName }
    'datetime' { return New-DateTimeAttribute $schemaName $displayName }
    'url' { return New-StringAttribute $schemaName $displayName 500 $false }
    'choice' {
      $choiceValues = @('novo', 'em_triagem', 'em_aprovacao', 'aprovado', 'em_execucao', 'validado', 'arquivado')
      if ($column.name -like '*prioridade') { $choiceValues = @('baixa', 'media', 'alta', 'critica') }
      if ($column.name -like '*origem') { $choiceValues = @('power_app', 'teams', 'copilot', 'importacao', 'manual') }
      if ($column.name -like '*tipo*') { $choiceValues = @('funcional', 'nao_funcional', 'regra_negocio', 'integracao', 'seguranca') }
      return New-PicklistAttribute $schemaName $displayName $choiceValues
    }
    default { return New-StringAttribute $schemaName $displayName 250 $false }
  }
}

function Ensure-Role([string]$name, [string]$description, [string]$businessUnitId) {
  $encodedName = $name.Replace("'", "''")
  $existing = Invoke-Dataverse -Method GET -Path "roles?`$select=roleid,name&`$filter=name eq '$encodedName'&`$top=1" -NoSolutionHeader
  if ($existing.value.Count -gt 0) {
    return @{ name = $name; status = 'exists'; id = $existing.value[0].roleid }
  }

  $payload = @{
    name = $name
    description = $description
    'businessunitid@odata.bind' = "/businessunits($businessUnitId)"
  }
  Invoke-Dataverse -Method POST -Path 'roles' -Body $payload -NoSolutionHeader | Out-Null
  $created = Invoke-Dataverse -Method GET -Path "roles?`$select=roleid,name&`$filter=name eq '$encodedName'&`$top=1" -NoSolutionHeader
  $roleId = $created.value[0].roleid
  try {
    Invoke-Dataverse -Method POST -Path 'AddSolutionComponent' -NoSolutionHeader -Body @{
      ComponentId = $roleId
      ComponentType = 20
      SolutionUniqueName = $solutionName
      AddRequiredComponents = $false
    } | Out-Null
  } catch {
    # Role may already be part of the solution; keep evidence and continue.
  }
  return @{ name = $name; status = 'created'; id = $roleId }
}

function Ensure-WebResource([string]$name, [string]$displayName, [string]$contentBase64) {
  $escapedName = $name.Replace("'", "''")
  $existing = Invoke-Dataverse -Method GET -Path "webresourceset?`$select=webresourceid,name&`$filter=name eq '$escapedName'&`$top=1" -NoSolutionHeader
  if ($existing.value.Count -gt 0) {
    $id = $existing.value[0].webresourceid
    Invoke-Dataverse -Method PATCH -Path "webresourceset($id)" -Body @{
      displayname = $displayName
      description = 'ReqSys LowCode Solution Factory artefact'
      content = $contentBase64
    } | Out-Null
    return @{ name = $name; status = 'updated'; id = $id }
  }

  Invoke-Dataverse -Method POST -Path 'webresourceset' -Body @{
    name = $name
    displayname = $displayName
    description = 'ReqSys LowCode Solution Factory artefact'
    webresourcetype = 1
    content = $contentBase64
  } | Out-Null
  $created = Invoke-Dataverse -Method GET -Path "webresourceset?`$select=webresourceid,name&`$filter=name eq '$escapedName'&`$top=1" -NoSolutionHeader
  return @{ name = $name; status = 'created'; id = $created.value[0].webresourceid }
}

Write-Host "Importing base solution $solutionZip"
pac solution import --path $solutionZip --publish-changes --force-overwrite --environment $environmentUrl
if ($LASTEXITCODE -ne 0) {
  throw "pac solution import failed with exit code $LASTEXITCODE"
}

$script:token = az account get-access-token --resource $environmentUrl --query accessToken -o tsv
$manifest = Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json

$evidence = [ordered]@{
  generated_at = (Get-Date).ToUniversalTime().ToString('o')
  environment_url = $environmentUrl
  solution_name = $solutionName
  tables = @()
  roles = @()
  web_resources = @()
  publish = $null
}

foreach ($table in $manifest.dataverse.tables) {
  $logicalName = [string]$table.logical_name
  $schemaName = Convert-SchemaName $logicalName
  $primaryName = "${schemaName}Titulo"
  if ($schemaName -eq 'reqsys_Requisito') { $primaryName = 'reqsys_Titulo' }
  $tableEvidence = [ordered]@{ logical_name = $logicalName; schema_name = $schemaName; status = $null; columns = @() }

  if (-not (Test-EntityExists $logicalName)) {
    $entityPayload = @{
      '@odata.type' = 'Microsoft.Dynamics.CRM.EntityMetadata'
      SchemaName = $schemaName
      DisplayName = New-Label ([string]$table.display_name)
      DisplayCollectionName = New-Label ([string]$table.display_name)
      Description = New-Label ([string]$table.description)
      OwnershipType = 'UserOwned'
      IsActivity = $false
      HasActivities = $false
      HasNotes = $true
      Attributes = @(
        @{
          '@odata.type' = 'Microsoft.Dynamics.CRM.StringAttributeMetadata'
          SchemaName = $primaryName
          DisplayName = New-Label 'Titulo'
          Description = New-Label 'Titulo'
          IsPrimaryName = $true
          RequiredLevel = New-RequiredLevel $true
          MaxLength = 250
          FormatName = @{ Value = 'Text' }
        }
      )
    }
    Invoke-Dataverse -Method POST -Path 'EntityDefinitions' -Body $entityPayload | Out-Null
    $tableEvidence.status = 'created'
  } else {
    $tableEvidence.status = 'exists'
  }

  foreach ($column in $table.columns) {
    if ($column.name -like '*_titulo') {
      $tableEvidence.columns += @{ name = [string]$column.name; status = 'primary_name' }
      continue
    }
    if ([string]$column.type -eq 'lookup') {
      $tableEvidence.columns += @{ name = [string]$column.name; status = 'skipped_lookup_p0' }
      continue
    }
    if (Test-AttributeExists $logicalName ([string]$column.name)) {
      $tableEvidence.columns += @{ name = [string]$column.name; status = 'exists' }
      continue
    }
    $payload = New-AttributePayload $column $manifest.dataverse.choices
    Invoke-Dataverse -Method POST -Path "EntityDefinitions(LogicalName='$logicalName')/Attributes" -Body $payload | Out-Null
    $tableEvidence.columns += @{ name = [string]$column.name; status = 'created' }
  }

  $evidence.tables += $tableEvidence
}

$businessUnits = Invoke-Dataverse -Method GET -Path "businessunits?`$select=businessunitid,name&`$top=1" -NoSolutionHeader
$businessUnitId = $businessUnits.value[0].businessunitid
foreach ($role in $manifest.security_roles) {
  $evidence.roles += Ensure-Role ([string]$role.name) ([string]$role.description) $businessUnitId
}

$canvas = Get-Content (Join-Path $repoRoot 'artifacts\lowcode-solution-factory\reqsys-lowcode\CANVAS.md') -Raw -Encoding UTF8
$manifestRaw = Get-Content $manifestPath -Raw -Encoding UTF8
$dataverseRaw = $manifest.dataverse | ConvertTo-Json -Depth 30
$flowsRaw = $manifest.flows | ConvertTo-Json -Depth 30
$copilotSecurityAlmRaw = ([ordered]@{
  copilot = $manifest.copilot
  security_roles = $manifest.security_roles
  alm_package = $manifest.alm_package
} | ConvertTo-Json -Depth 30)

$evidence.web_resources += Ensure-WebResource 'reqsys_/lowcode/canvas.htm' 'ReqSys LowCode Canvas' (New-HtmlContent 'ReqSys LowCode Canvas' $canvas)
$evidence.web_resources += Ensure-WebResource 'reqsys_/lowcode/manifest.htm' 'ReqSys LowCode Manifest' (New-HtmlContent 'ReqSys LowCode Manifest' $manifestRaw)
$evidence.web_resources += Ensure-WebResource 'reqsys_/lowcode/dataverse-schema.htm' 'ReqSys LowCode Dataverse Schema' (New-HtmlContent 'ReqSys LowCode Dataverse Schema' $dataverseRaw)
$evidence.web_resources += Ensure-WebResource 'reqsys_/lowcode/powerautomate-flows.htm' 'ReqSys LowCode Power Automate Flows' (New-HtmlContent 'ReqSys LowCode Power Automate Flows' $flowsRaw)
$evidence.web_resources += Ensure-WebResource 'reqsys_/lowcode/copilot-security-alm.htm' 'ReqSys LowCode Copilot Security ALM' (New-HtmlContent 'ReqSys LowCode Copilot Security ALM' $copilotSecurityAlmRaw)

Invoke-Dataverse -Method POST -Path 'PublishAllXml' -Body @{} -NoSolutionHeader | Out-Null
$evidence.publish = 'PublishAllXml completed'

$evidence | ConvertTo-Json -Depth 30 | Set-Content -Path $evidencePath -Encoding UTF8
Write-Host "Materialization evidence written to $evidencePath"
