$ErrorActionPreference = 'Stop'
$base = 'artifacts/lowcode-solution-factory'
$solutionFolder = Join-Path $base 'powerplatform-standard/src/src'
$customizationsPath = Join-Path $solutionFolder 'Other/Customizations.xml'
$solutionPath = Join-Path $solutionFolder 'Other/Solution.xml'
$manifest = Get-Content (Join-Path $base 'reqsys-lowcode/manifest.json') -Raw -Encoding UTF8
$canvas = Get-Content (Join-Path $base 'reqsys-lowcode/CANVAS.md') -Raw -Encoding UTF8
$manifestObj = $manifest | ConvertFrom-Json
$dataverse = ($manifestObj.dataverse | ConvertTo-Json -Depth 30)
$flows = ($manifestObj.flows | ConvertTo-Json -Depth 30)
$copilotSecurityAlm = ([ordered]@{
  copilot = $manifestObj.copilot
  security_roles = $manifestObj.security_roles
  alm_package = $manifestObj.alm_package
} | ConvertTo-Json -Depth 30)
function New-HtmlContent([string]$title, [string]$body) {
  $encoded = [System.Net.WebUtility]::HtmlEncode($body)
  $html = "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>$title</title><style>body{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#111827}pre{white-space:pre-wrap;background:#f8fafc;border:1px solid #cbd5e1;padding:16px;border-radius:6px}h1{font-size:22px}</style></head><body><h1>$title</h1><pre>$encoded</pre></body></html>"
  return [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($html))
}
$resources = @(
  @{ id = '8c18c339-4eb7-4470-8bbf-5c435ab00401'; name = 'reqsys_/lowcode/canvas.htm'; display = 'ReqSys LowCode Canvas'; content = New-HtmlContent 'ReqSys LowCode Canvas' $canvas },
  @{ id = '8c18c339-4eb7-4470-8bbf-5c435ab00402'; name = 'reqsys_/lowcode/manifest.htm'; display = 'ReqSys LowCode Manifest'; content = New-HtmlContent 'ReqSys LowCode Manifest' $manifest },
  @{ id = '8c18c339-4eb7-4470-8bbf-5c435ab00403'; name = 'reqsys_/lowcode/dataverse-schema.htm'; display = 'ReqSys LowCode Dataverse Schema'; content = New-HtmlContent 'ReqSys LowCode Dataverse Schema' $dataverse },
  @{ id = '8c18c339-4eb7-4470-8bbf-5c435ab00404'; name = 'reqsys_/lowcode/powerautomate-flows.htm'; display = 'ReqSys LowCode Power Automate Flows'; content = New-HtmlContent 'ReqSys LowCode Power Automate Flows' $flows },
  @{ id = '8c18c339-4eb7-4470-8bbf-5c435ab00405'; name = 'reqsys_/lowcode/copilot-security-alm.htm'; display = 'ReqSys LowCode Copilot Security ALM'; content = New-HtmlContent 'ReqSys LowCode Copilot Security ALM' $copilotSecurityAlm }
)
[xml]$customizations = Get-Content $customizationsPath -Raw -Encoding UTF8
$root = $customizations.ImportExportXml
$existing = $root.WebResources
if ($existing) { [void]$root.RemoveChild($existing) }
$webResources = $customizations.CreateElement('WebResources')
foreach ($res in $resources) {
  $wr = $customizations.CreateElement('WebResource')
  foreach ($pair in @(
    @('WebResourceId', '{' + $res.id + '}'),
    @('Name', $res.name),
    @('DisplayName', $res.display),
    @('Description', 'ReqSys LowCode Solution Factory artefact embedded in solution'),
    @('WebResourceType', '1'),
    @('IntroducedVersion', '1.0.0.0'),
    @('IsEnabledForMobileClient', '0'),
    @('IsAvailableForMobileOffline', '0'),
    @('Content', $res.content)
  )) {
    $node = $customizations.CreateElement($pair[0])
    $node.InnerText = $pair[1]
    [void]$wr.AppendChild($node)
  }
  [void]$webResources.AppendChild($wr)
}
$languages = $root.Languages
[void]$root.InsertBefore($webResources, $languages)
$settings = New-Object System.Xml.XmlWriterSettings
$settings.Encoding = New-Object System.Text.UTF8Encoding($false)
$settings.Indent = $true
$writer = [System.Xml.XmlWriter]::Create((Resolve-Path $customizationsPath), $settings)
$customizations.Save($writer)
$writer.Close()

[xml]$solution = Get-Content $solutionPath -Raw -Encoding UTF8
$components = $solution.SelectSingleNode('//RootComponents')
if (-not $components) {
  $components = $solution.CreateElement('RootComponents')
  [void]$solution.ImportExportXml.SolutionManifest.AppendChild($components)
}
while ($components.HasChildNodes) {
  [void]$components.RemoveChild($components.FirstChild)
}
foreach ($res in $resources) {
  $node = $solution.CreateElement('RootComponent')
  $node.SetAttribute('type', '61')
  $node.SetAttribute('id', '{' + $res.id + '}')
  $node.SetAttribute('schemaName', $res.name)
  $node.SetAttribute('behavior', '0')
  [void]$components.AppendChild($node)
}
$writer = [System.Xml.XmlWriter]::Create((Resolve-Path $solutionPath), $settings)
$solution.Save($writer)
$writer.Close()
"Embedded $($resources.Count) web resources into ReqSysLowCode solution."
