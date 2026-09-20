# ADR-047 — Publicação do ReqSys no PC24x7 sem Fly.io

Status: **aceito para DEV**
Data: 2026-09-20

## Contexto

O Fly.io deixou de ser o runtime vigente do ReqSys. O runtime local/DEV está no PC24x7 e o
gateway funcional é o Nginx publicado em `:8083`.

A validação física de 2026-09-20 encontrou dois drifts:

1. os containers `reqsys-dev-gateway-tunnel` e `reqsys-dev-failover-tunnel` apontavam para
   endereço LAN/portas antigas;
2. os nomes `tieridev`, `tierin` e `tieriprod.duckdns.org` apontavam para um IPv4 público
   antigo, e não havia token DuckDNS armazenado no host nem UPnP disponível para provisionar
   automaticamente o roteador.

## Decisão

1. **Runtime:** PC24x7 continua como primeira opção, conforme a regra global
   `runtime-routing.md`.
2. **DEV público imediato:** dois Cloudflare Quick Tunnels gratuitos, ambos apontando para
   `http://host.docker.internal:8083`.
3. **URL estável sem domínio pago:** `tieridev.duckdns.org` permanece o alvo, mas só pode ser
   promovido quando houver credencial DuckDNS disponível fora do Git/chat e ingresso
   80/443 comprovado no roteador/reverse proxy.
4. **URL estável com Cloudflare:** quando houver domínio próprio sob DNS Cloudflare, substituir
   Quick Tunnel por Named Tunnel. O túnel continua gratuito; o domínio é externo ao plano.
5. **HML/PROD:** não são promovidos por esta decisão. Exigem gates próprios, isolamento,
   continuidade e evidência E2E antes de publicação.
6. **Backend:** nenhuma porta de API é publicada diretamente como entrada pública. O acesso
   deve passar pelo gateway Nginx do ambiente.

## Implementação

O reconciliador `scripts/pc24x7_public_dev_tunnel.py`:

- não lê segredos;
- é idempotente;
- usa `host.docker.internal`, removendo dependência de IPv4 LAN fixo;
- garante `restart: unless-stopped`;
- valida `/api/health` e `/task-console`;
- grava o estado runtime local em
  `%LOCALAPPDATA%/ReqSys/PublicRuntime/dev-tunnels.json`.

Aplicação:

```powershell
python scripts/pc24x7_public_dev_tunnel.py --apply
```

Validação read-only:

```powershell
python scripts/pc24x7_public_dev_tunnel.py
```

## Evidência de 2026-09-20

Após a correção, os dois túneis DEV ficaram em execução com destino
`http://host.docker.internal:8083`, política `unless-stopped` e retornaram HTTP 200 tanto
em `/api/health` quanto em `/task-console`.

As URLs Quick Tunnel são deliberadamente tratadas como estado runtime e não são commitadas,
pois mudam quando o processo do tunnel é recriado.

## Critério de conclusão da URL estável DEV

- credencial DuckDNS armazenada em mecanismo local protegido, nunca no Git/chat;
- atualização automática do registro comprovada;
- ingresso HTTPS público comprovado sem publicar API direta;
- certificado válido;
- `/api/health` e `/task-console` HTTP 200 por leitura externa;
- restart do host seguido de recuperação sem intervenção.
