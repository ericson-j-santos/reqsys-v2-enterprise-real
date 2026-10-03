# ReqSys — Proxy Reverso Multiambiente

Este diretório padroniza a publicação do ReqSys em três cenários suportados:

1. **Linux + Nginx**: gateway reverso leve para frontend, backend API e KB.
2. **Linux + Apache HTTP Server**: alternativa corporativa usando `mod_proxy`, `mod_headers`, `mod_rewrite` e `mod_ssl`.
3. **Windows Server + IIS/ARR**: alternativa Windows usando API COM do IIS (`Microsoft.Web.Administration`) via PowerShell, sem interface gráfica e sem geradores externos.

## Decisão técnica

A aplicação deve expor um único ponto de entrada HTTP/HTTPS e encaminhar internamente:

| Rota pública | Destino interno padrão | Finalidade |
|---|---:|---|
| `/` | `http://127.0.0.1:5173/` | Frontend Vite/SPA |
| `/api/` | `http://127.0.0.1:8000/` | Backend FastAPI |
| `/kb/` | `http://127.0.0.1:8080/` | Knowledge Base |
| `/favicon.ico` | `204` | Evitar ruído operacional |

## Portas padrão

| Variável | Padrão | Descrição |
|---|---:|---|
| `GATEWAY_PORT` | `8081` | Porta pública local do gateway |
| `BACKEND_PORT` | `8000` | Porta do backend |
| `FRONTEND_PORT` | `5173` | Porta do frontend |
| `KB_PORT` | `8080` | Porta da KB |

## Governança obrigatória

- Não usar CORS `*` em produção.
- Não publicar backend/API diretamente sem proxy/gateway controlado.
- Preservar `Host`, `X-Real-IP`, `X-Forwarded-For` e `X-Forwarded-Proto`.
- Ativar headers mínimos de segurança.
- Validar sintaxe antes de aplicar configuração.
- Registrar rollback manual e rastreabilidade por commit/PR.

## Implementações

| Ambiente | Artefato |
|---|---|
| Linux + Apache | `apache/reqsys.conf` e `scripts/linux-apache-apply.sh` |
| Windows Server + IIS/ARR | `iis/reqsys-iis-arr.ps1` |
| Validação local | `scripts/validate-reverse-proxy.ps1` |

## Execução — Apache/Linux

```bash
sudo bash infra/reverse-proxy/scripts/linux-apache-apply.sh
```

Variáveis opcionais:

```bash
export REQSYS_SERVER_NAME="reqsys.local"
export GATEWAY_PORT="8081"
export BACKEND_PORT="8000"
export FRONTEND_PORT="5173"
export KB_PORT="8080"
```

## Execução — Windows Server/IIS

Executar PowerShell como administrador:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
.\infra\reverse-proxy\iis\reqsys-iis-arr.ps1 -SiteName "ReqSys" -HostName "reqsys.local" -GatewayPort 8081
```

## Validação

```powershell
.\infra\reverse-proxy\scripts\validate-reverse-proxy.ps1 -BaseUrl "http://localhost:8081"
```

## Observação

Os scripts não instalam ferramentas prontas de terceiros. Eles configuram os servidores suportados usando recursos nativos e APIs administrativas dos próprios serviços:

- Apache: arquivos de configuração e comandos `a2enmod`, `a2ensite`, `apache2ctl`.
- IIS: API administrativa `Microsoft.Web.Administration`.
