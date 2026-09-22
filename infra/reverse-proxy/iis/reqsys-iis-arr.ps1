<#
ReqSys — Windows Server IIS/ARR reverse proxy

Configura o IIS por API administrativa nativa (`Microsoft.Web.Administration`).
Pré-requisitos no servidor:
- IIS instalado.
- URL Rewrite + Application Request Routing instalados e habilitados.
- Execução como Administrador.

Uso:
  .\infra\reverse-proxy\iis\reqsys-iis-arr.ps1 -SiteName "ReqSys" -HostName "reqsys.local" -GatewayPort 8081
#>

[CmdletBinding()]
param(
  [string]$SiteName = "ReqSys",
  [string]$HostName = "reqsys.local",
  [int]$GatewayPort = 8081,
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173,
  [int]$KbPort = 8080,
  [string]$PhysicalPath = "C:\inetpub\reqsys-gateway"
)

$ErrorActionPreference = "Stop"

function Assert-Administrator {
  $current = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($current)
  if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Execute este script em PowerShell como Administrador."
  }
}

function Assert-IisApi {
  try {
    Add-Type -AssemblyName "Microsoft.Web.Administration" -ErrorAction Stop
  } catch {
    throw "API Microsoft.Web.Administration indisponível. Instale/habilite o IIS Management Console."
  }
}

function Ensure-Directory([string]$Path) {
  if (-not (Test-Path $Path)) {
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
  }
}

function Write-Placeholder([string]$Path) {
  $index = Join-Path $Path "index.html"
  if (-not (Test-Path $index)) {
@"
<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>ReqSys Gateway</title></head>
<body><h1>ReqSys Gateway IIS/ARR</h1><p>Gateway ativo. O conteúdo principal é entregue por proxy reverso.</p></body>
</html>
"@ | Set-Content -Path $index -Encoding UTF8
  }
}

function Ensure-Site {
  param([Microsoft.Web.Administration.ServerManager]$Manager)

  Ensure-Directory $PhysicalPath
  Write-Placeholder $PhysicalPath

  $site = $Manager.Sites[$SiteName]
  if ($null -eq $site) {
    $site = $Manager.Sites.Add($SiteName, "http", "*:$GatewayPort:$HostName", $PhysicalPath)
  }

  $bindingInfo = "*:$GatewayPort:$HostName"
  $exists = $false
  foreach ($binding in $site.Bindings) {
    if ($binding.Protocol -eq "http" -and $binding.BindingInformation -eq $bindingInfo) {
      $exists = $true
      break
    }
  }
  if (-not $exists) {
    $site.Bindings.Add($bindingInfo, "http") | Out-Null
  }

  return $site
}

function Set-WebConfig {
  $webConfig = Join-Path $PhysicalPath "web.config"
  $content = @"
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>
    <rewrite>
      <rules>
        <rule name="ReqSys favicon" stopProcessing="true">
          <match url="^favicon\.ico$" />
          <action type="CustomResponse" statusCode="204" statusReason="No Content" statusDescription="No Content" />
        </rule>
        <rule name="ReqSys API" stopProcessing="true">
          <match url="^api/(.*)" />
          <action type="Rewrite" url="http://127.0.0.1:$BackendPort/{R:1}" appendQueryString="true" />
          <serverVariables>
            <set name="HTTP_X_FORWARDED_PROTO" value="http" />
            <set name="HTTP_X_FORWARDED_HOST" value="{HTTP_HOST}" />
          </serverVariables>
        </rule>
        <rule name="ReqSys KB" stopProcessing="true">
          <match url="^kb/(.*)" />
          <action type="Rewrite" url="http://127.0.0.1:$KbPort/{R:1}" appendQueryString="true" />
          <serverVariables>
            <set name="HTTP_X_FORWARDED_PREFIX" value="/kb" />
            <set name="HTTP_X_FORWARDED_PROTO" value="http" />
            <set name="HTTP_X_FORWARDED_HOST" value="{HTTP_HOST}" />
          </serverVariables>
        </rule>
        <rule name="ReqSys Frontend" stopProcessing="true">
          <match url="(.*)" />
          <action type="Rewrite" url="http://127.0.0.1:$FrontendPort/{R:1}" appendQueryString="true" />
          <serverVariables>
            <set name="HTTP_X_FORWARDED_PROTO" value="http" />
            <set name="HTTP_X_FORWARDED_HOST" value="{HTTP_HOST}" />
          </serverVariables>
        </rule>
      </rules>
    </rewrite>
    <httpProtocol>
      <customHeaders>
        <remove name="X-Powered-By" />
        <add name="X-Frame-Options" value="DENY" />
        <add name="X-Content-Type-Options" value="nosniff" />
        <add name="Referrer-Policy" value="strict-origin-when-cross-origin" />
        <add name="Permissions-Policy" value="geolocation=(), microphone=(), camera=()" />
      </customHeaders>
    </httpProtocol>
    <security>
      <requestFiltering>
        <requestLimits maxAllowedContentLength="4194304" />
      </requestFiltering>
    </security>
  </system.webServer>
</configuration>
"@
  $content | Set-Content -Path $webConfig -Encoding UTF8
}

function Enable-ArrProxyBestEffort {
  $appcmd = Join-Path $env:windir "System32\inetsrv\appcmd.exe"
  if (-not (Test-Path $appcmd)) {
    Write-Warning "appcmd.exe não encontrado. IIS pode não estar instalado corretamente."
    return
  }

  & $appcmd set config -section:system.webServer/proxy /enabled:"True" /preserveHostHeader:"True" /commit:apphost | Out-Null
}

Assert-Administrator
Assert-IisApi

$manager = New-Object Microsoft.Web.Administration.ServerManager
$site = Ensure-Site -Manager $manager
Set-WebConfig
Enable-ArrProxyBestEffort
$manager.CommitChanges()

Write-Host "[ReqSys/IIS] Proxy reverso configurado." -ForegroundColor Green
Write-Host "  Site        : $SiteName"
Write-Host "  URL pública : http://$HostName`:$GatewayPort"
Write-Host "  Frontend    : http://127.0.0.1:$FrontendPort"
Write-Host "  Backend API : http://127.0.0.1:$BackendPort"
Write-Host "  KB          : http://127.0.0.1:$KbPort"
