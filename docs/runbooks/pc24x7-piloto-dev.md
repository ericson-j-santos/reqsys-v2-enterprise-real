# Piloto PC24x7 — publicação pública do ambiente DEV

Este runbook aplica o ADR-047 e substitui a dependência operacional do Fly.io para DEV.

## Estado evidenciado em 2026-09-20

- gateway ReqSys DEV saudável em `http://127.0.0.1:8083`;
- API saudável via `/api/health`;
- dois Cloudflare Quick Tunnels corrigidos para `http://host.docker.internal:8083`;
- ambos com `restart: unless-stopped`;
- `/api/health` e `/task-console` retornaram HTTP 200 através dos túneis;
- DuckDNS existente está com drift de IP e não há token DuckDNS armazenado no host;
- UPnP não foi detectado no roteador;
- HML e PROD não são promovidos por este runbook.

## 1. Arquitetura

```text
Internet
   |
   +-- Cloudflare Quick Tunnel (DEV imediato, gratuito, URL dinâmica)
   |        |
   |        +--> host.docker.internal:8083
   |
   +-- tieridev.duckdns.org (alvo de URL estável)
            |
            +--> HTTPS do PC24x7 quando DNS/ingresso estiverem comprovados

PC24x7
   |
   +--> Nginx DEV :8083
           +--> frontend
           +--> /api --> backend
```

Não publicar `:8210`, `:8211`, `:8215` ou qualquer backend diretamente para a Internet.

## 2. Reconciliação do Quick Tunnel

Somente leitura:

```powershell
python scripts/pc24x7_public_dev_tunnel.py
```

Aplicar correção idempotente:

```powershell
python scripts/pc24x7_public_dev_tunnel.py --apply
```

O reconciliador garante dois containers:

- `reqsys-dev-gateway-tunnel`
- `reqsys-dev-failover-tunnel`

Ambos apontam para `http://host.docker.internal:8083`, evitando dependência do IPv4 LAN do
host. O estado corrente é salvo fora do repositório em
`%LOCALAPPDATA%/ReqSys/PublicRuntime/dev-tunnels.json`.

## 3. Por que Quick Tunnel é contingência e não URL canônica

Quick Tunnel é gratuito e não exige domínio, IP público ou porta aberta, mas o hostname
`*.trycloudflare.com` muda quando o processo é recriado. Portanto:

- adequado para DEV, validação e contingência;
- inadequado como endereço canônico de HML/PROD;
- a URL dinâmica nunca deve ser hardcoded no Git.

## 4. URL estável gratuita com DuckDNS

Alvo DEV:

```text
https://tieridev.duckdns.org
```

Pré-requisitos para ativar:

1. token DuckDNS disponível no host por mecanismo protegido;
2. atualizador DDNS idempotente;
3. entrada 80/443 no roteador ou outro ingresso externo comprovado;
4. reverse proxy HTTPS válido para `:8083`;
5. E2E externo.

O token não deve ser colocado em `.env` versionado, argumento de container, log ou
artifact.

Se o provedor de Internet usar CGNAT ou o roteador não permitir ingresso, não forçar
DuckDNS direto: usar Cloudflare Tunnel.

## 5. URL estável por Cloudflare

Cloudflare Tunnel usa conexão somente de saída e não exige abrir portas. Para hostname
estável próprio, usar Named Tunnel com domínio sob DNS Cloudflare.

Sem domínio próprio, manter Quick Tunnel apenas para DEV.

## 6. HML e PROD

Não copiar automaticamente DEV para HML/PROD.

Antes da promoção exigir:

- stack isolada por ambiente;
- persistência/backup restaurável;
- restart pós-boot;
- endpoint HTTPS estável;
- health/readiness;
- gates de segurança/governança;
- E2E com leitura independente;
- rollback testado.

## 7. Critério de conclusão DEV

DEV público só passa de contingência para canônico quando:

- URL estável;
- DNS atualizado automaticamente;
- HTTPS válido;
- frontend e `/api/health` verdes;
- reinício recupera stack e publicação;
- nenhuma porta de backend está exposta diretamente;
- evidência vinculada ao SHA corrente.
