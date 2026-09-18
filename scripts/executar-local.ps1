# Executa o stack ReqSys sem Docker — Windows (PowerShell)
# Pré-requisitos: Python 3.12+, Node.js 20+, nginx para Windows
#
# Nginx para Windows: https://nginx.org/en/download.html
#   Extraia para C:\nginx (ou defina $env:NGINX_HOME antes de rodar)
#
# Uso:
#   cd reqsys-v2-enterprise-real
#   .\scripts\executar-local.ps1
#
# Variáveis de ambiente opcionais:
#   $env:GATEWAY_PORT   porta do nginx local        (padrão: 8081)
#   $env:BACKEND_PORT   porta do uvicorn backend    (padrão: 8000)
#   $env:FRONTEND_PORT  porta do vite dev server    (padrão: 5173)
#   $env:KB_PORT        porta do uvicorn kb         (padrão: 8080)
#   $env:KB_DIR         caminho absoluto para o kb
#   $env:NGINX_HOME     pasta raiz do nginx.exe     (padrão: C:\nginx)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Caminhos e portas
# ---------------------------------------------------------------------------
$Root        = (Resolve-Path "$PSScriptRoot\..").Path
$BackendDir  = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$KbDir       = if ($env:KB_DIR) { $env:KB_DIR } else { (Resolve-Path (Join-Path $Root "..\..\kb") -ErrorAction SilentlyContinue)?.Path }
$NginxHome   = if ($env:NGINX_HOME) { $env:NGINX_HOME } else { "C:\nginx" }

$BackendPort  = if ($env:BACKEND_PORT)  { $env:BACKEND_PORT  } else { "8000" }
$FrontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "5173" }
$KbPort       = if ($env:KB_PORT)       { $env:KB_PORT       } else { "8080" }
$GatewayPort  = if ($env:GATEWAY_PORT)  { $env:GATEWAY_PORT  } else { "8081" }

# Carrega .env do projeto (se existir)
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
  Get-Content $EnvFile | Where-Object { $_ -match '^\s*[^#]\S+=\S' } | ForEach-Object {
    $parts = $_ -split '=', 2
    if ($parts.Count -eq 2 -and -not [System.Environment]::GetEnvironmentVariable($parts[0].Trim())) {
      [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim())
    }
  }
}

# Modo local = sempre SQLite (o .env pode ter SQL Server para Docker/prod)
if (-not $env:DATABASE_URL -or $env:DATABASE_URL -notlike "sqlite*") {
  $env:DATABASE_URL = "sqlite:///./reqsys.db"
  Write-Host "[Backend] INFO: DATABASE_URL sobrescrita para SQLite no modo local." -ForegroundColor DarkCyan
}
# Garante CORS com DuckDNS
if (-not $env:CORS_ORIGINS) {
  $env:CORS_ORIGINS = "http://localhost:$GatewayPort,http://127.0.0.1:$GatewayPort,https://tieridev.duckdns.org,https://tierin.duckdns.org,https://tieriprod.duckdns.org"
}
if (-not $env:JWT_SECRET) { $env:JWT_SECRET = "trocar-em-producao" }

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " ReqSys — stack local sem Docker (Windows)" -ForegroundColor Cyan
Write-Host "  Gateway  : http://localhost:$GatewayPort" -ForegroundColor Cyan
Write-Host "  Login    : POST http://localhost:$GatewayPort/api/v1/auth/login" -ForegroundColor Cyan
Write-Host "  Swagger  : http://localhost:$BackendPort/docs" -ForegroundColor Cyan
Write-Host "  DuckDNS  : tieridev / tierin / tieriprod .duckdns.org → :$GatewayPort" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

$Processes = @()

function Stop-Stack {
  Write-Host "`n[ReqSys] Encerrando processos..." -ForegroundColor Yellow
  foreach ($p in $script:Processes) {
    try { if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force } } catch {}
  }
  # Para nginx
  $NginxExe = Join-Path $NginxHome "nginx.exe"
  if (Test-Path $NginxExe) {
    try { & $NginxExe -s quit 2>$null } catch {}
  }
  $TmpConf = Join-Path $env:TEMP "reqsys-nginx.conf"
  if (Test-Path $TmpConf) { Remove-Item $TmpConf -Force }
  Write-Host "[ReqSys] Stack encerrado." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------
Write-Host "[Backend] Preparando virtualenv..." -ForegroundColor Green
Push-Location $BackendDir
if (-not (Test-Path ".venv")) { python -m venv .venv }
& ".venv\Scripts\pip.exe" install -r requirements.txt -q
$BackendProc = Start-Process ".venv\Scripts\uvicorn.exe" `
  -ArgumentList "app.main:app --host 127.0.0.1 --port $BackendPort" `
  -PassThru -NoNewWindow
$Processes += $BackendProc
Pop-Location
Write-Host "[Backend] PID $($BackendProc.Id) ouvindo em :$BackendPort" -ForegroundColor Green

# ---------------------------------------------------------------------------
# KB (Knowledge Base)
# ---------------------------------------------------------------------------
if ($KbDir -and (Test-Path $KbDir)) {
  Write-Host "[KB] Preparando virtualenv em $KbDir..." -ForegroundColor Green
  Push-Location $KbDir
  if (-not (Test-Path ".venv")) { python -m venv .venv }
  & ".venv\Scripts\pip.exe" install -r requirements.txt -q
  $KbProc = Start-Process ".venv\Scripts\uvicorn.exe" `
    -ArgumentList "main:app --host 127.0.0.1 --port $KbPort --root-path /kb" `
    -PassThru -NoNewWindow
  $Processes += $KbProc
  Pop-Location
  Write-Host "[KB] PID $($KbProc.Id) ouvindo em :$KbPort" -ForegroundColor Green
} else {
  Write-Host "[KB] AVISO: diretório não encontrado. KB desabilitado." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Frontend (Vite dev server)
# ---------------------------------------------------------------------------
Write-Host "[Frontend] Instalando dependências..." -ForegroundColor Green
Push-Location $FrontendDir
if (-not (Test-Path "node_modules")) { npm install -q }
$env:VITE_API_URL = "/api"
$FrontendProc = Start-Process "npm" `
  -ArgumentList "run dev -- --port $FrontendPort --host 127.0.0.1" `
  -PassThru -NoNewWindow
$Processes += $FrontendProc
Pop-Location
Write-Host "[Frontend] PID $($FrontendProc.Id) ouvindo em :$FrontendPort" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Nginx (proxy reverso — login/auth passa por aqui)
# ---------------------------------------------------------------------------
$NginxExe = Join-Path $NginxHome "nginx.exe"
if (-not (Test-Path $NginxExe)) {
  Write-Host "[Nginx] AVISO: nginx.exe não encontrado em $NginxHome" -ForegroundColor Yellow
  Write-Host "        Baixe em https://nginx.org/en/download.html e extraia para C:\nginx" -ForegroundColor Yellow
  Write-Host "        Ou defina: `$env:NGINX_HOME = 'caminho\para\nginx'" -ForegroundColor Yellow
  Write-Host "        Sem nginx, o stack funciona diretamente em :$FrontendPort (sem gateway)" -ForegroundColor Yellow
} else {
  # Gera nginx.conf completo em %TEMP%
  $TmpConf = Join-Path $env:TEMP "reqsys-nginx.conf"
  $NginxLogsDir = Join-Path $NginxHome "logs"
  if (-not (Test-Path $NginxLogsDir)) { New-Item -ItemType Directory -Path $NginxLogsDir -Force | Out-Null }

  @"
worker_processes  1;
error_log  logs/reqsys-error.log  warn;
pid        logs/reqsys-nginx.pid;

events {
    worker_connections  1024;
}

http {
    default_type  application/octet-stream;
    sendfile      on;
    access_log    logs/reqsys-access.log;

    server {
        listen      $GatewayPort;
        server_name tieridev.duckdns.org tierin.duckdns.org tieriprod.duckdns.org localhost 127.0.0.1;

        proxy_set_header Host               `$host;
        proxy_set_header X-Real-IP          `$remote_addr;
        proxy_set_header X-Forwarded-For    `$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto  `$scheme;
        proxy_read_timeout    60s;
        proxy_connect_timeout 10s;
        client_max_body_size  4m;

        location /api/ {
            proxy_pass http://127.0.0.1:$BackendPort/;
        }

        location /kb/ {
            proxy_pass http://127.0.0.1:$KbPort/;
            proxy_set_header X-Forwarded-Prefix /kb;
        }

        location = /favicon.ico {
            access_log  off;
            log_not_found off;
            return 204;
        }

        location / {
            proxy_pass http://127.0.0.1:$FrontendPort/;
            proxy_http_version 1.1;
            proxy_set_header Upgrade   `$http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }
}
"@ | Set-Content -Path $TmpConf -Encoding utf8

  Push-Location $NginxHome
  & $NginxExe -t -c $TmpConf
  & $NginxExe -c $TmpConf
  Pop-Location
  Write-Host "[Nginx] Proxy ouvindo em :$GatewayPort" -ForegroundColor Green
  Write-Host "        Auth flow: browser → nginx:$GatewayPort/api/v1/auth/login → backend:$BackendPort" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[ReqSys] Stack pronto. Pressione Ctrl+C para encerrar." -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

try {
  while ($true) {
    Start-Sleep -Seconds 5
    # Verifica se algum processo essencial morreu
    foreach ($p in $Processes) {
      if ($p.HasExited -and $p.ExitCode -ne 0) {
        Write-Host "[AVISO] Processo PID $($p.Id) encerrou com código $($p.ExitCode)" -ForegroundColor Yellow
      }
    }
  }
} finally {
  Stop-Stack
}
