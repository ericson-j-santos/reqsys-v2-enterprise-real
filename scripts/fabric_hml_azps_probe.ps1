param(
  [Parameter(Mandatory=$true)][string]$TenantId,
  [Parameter(Mandatory=$true)][string]$AppName,
  [Parameter(Mandatory=$true)][string]$WorkspaceName
)

$ErrorActionPreference = "Stop"
$result = [ordered]@{
  azure_ps_available = $false
  authenticated = $false
  tenant_match = $false
  graph_status = $null
  app_exact_count = 0
  app_id = ""
  fabric_status = $null
  workspace_exact_count = 0
  workspace_id = ""
}

function Convert-AccessTokenToPlainText($tokenObject) {
  $value = $tokenObject.Token
  if ($value -is [System.Security.SecureString]) {
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($value)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
  }
  return [string]$value
}

try {
  $module = Get-Module -ListAvailable -Name Az.Accounts | Select-Object -First 1
  if (-not $module) { $result | ConvertTo-Json -Compress; exit 0 }
  $result.azure_ps_available = $true
  Import-Module Az.Accounts -ErrorAction Stop | Out-Null

  $context = Get-AzContext -ErrorAction SilentlyContinue
  if (-not $context) { $result | ConvertTo-Json -Compress; exit 0 }
  $result.authenticated = $true
  $contextTenant = [string]$context.Tenant.Id
  $result.tenant_match = $contextTenant.Equals($TenantId, [System.StringComparison]::OrdinalIgnoreCase)
  if (-not $result.tenant_match) { $result | ConvertTo-Json -Compress; exit 0 }

  try {
    $graphTokenObject = Get-AzAccessToken -ResourceUrl "https://graph.microsoft.com" -ErrorAction Stop
    $graphToken = Convert-AccessTokenToPlainText $graphTokenObject
    $filterText = [uri]::EscapeDataString("displayName eq '$AppName'")
    $graphUrl = "https://graph.microsoft.com/v1.0/applications?%24filter=$filterText&%24select=appId,id,displayName"
    $apps = Invoke-RestMethod -Method Get -Uri $graphUrl -Headers @{ Authorization = "Bearer $graphToken" } -ErrorAction Stop
    $exactApps = @($apps.value | Where-Object { $_.displayName -eq $AppName })
    $result.graph_status = 200
    $result.app_exact_count = $exactApps.Count
    if ($exactApps.Count -eq 1) { $result.app_id = [string]$exactApps[0].appId }
  }
  catch {
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) { $result.graph_status = [int]$_.Exception.Response.StatusCode }
    else { $result.graph_status = 0 }
  }

  try {
    $fabricTokenObject = Get-AzAccessToken -ResourceUrl "https://api.fabric.microsoft.com" -ErrorAction Stop
    $fabricToken = Convert-AccessTokenToPlainText $fabricTokenObject
    $workspaces = Invoke-RestMethod -Method Get -Uri "https://api.fabric.microsoft.com/v1/workspaces" -Headers @{ Authorization = "Bearer $fabricToken" } -ErrorAction Stop
    $exactWorkspaces = @($workspaces.value | Where-Object { $_.displayName -eq $WorkspaceName })
    $result.fabric_status = 200
    $result.workspace_exact_count = $exactWorkspaces.Count
    if ($exactWorkspaces.Count -eq 1) { $result.workspace_id = [string]$exactWorkspaces[0].id }
  }
  catch {
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) { $result.fabric_status = [int]$_.Exception.Response.StatusCode }
    else { $result.fabric_status = 0 }
  }
}
finally {
  $result | ConvertTo-Json -Compress
}
