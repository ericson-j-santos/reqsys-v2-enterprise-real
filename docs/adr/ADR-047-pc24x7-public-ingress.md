# ADR-047 — Publicação DEV zero-cost no PC24x7

Status: **aceito para DEV**
Data: 2026-09-20

## Contexto

O Fly.io deixou de ser runtime vigente. O ReqSys DEV roda no PC24x7, com gateway
Nginx em `:8083`.

Os E2Es físicos de 2026-09-20 provaram:

- dois Cloudflare Quick Tunnels apontando para `host.docker.internal:8083`
  permaneceram HTTP 200 durante queda do transporte alternativo;
- Quick Tunnel é resiliente como transporte, mas o hostname muda após reinício;
- NPort forneceu subdomínio escolhido sem custo, porém após crash abrupto a nova
  instância recebeu `subdomain already in use`, portanto não é canônico para
  recuperação pós-falha;
- DuckDNS depende de credencial ausente e ingresso residencial;
- Tailscale Funnel depende de consentimento administrativo e não deve bloquear DEV.

A regra econômica do projeto é **custo adicional zero**.

## Decisão

A publicação DEV passa a ter duas camadas:

1. **Transporte:** dois Cloudflare Quick Tunnels gratuitos para o gateway
   `:8083`.
2. **Entrada estável:** GitHub Pages em
   `https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/dev/`.

O PC24x7 publica a cada ciclo de 5 minutos o estado atual dos tunnels em um
tópico ntfy público. O payload é assinado com Ed25519.

A chave privada:

- nasce no próprio PC24x7;
- é protegida por Windows DPAPI;
- nunca entra no Git, ntfy ou logs públicos.

O Pages contém somente a chave pública e aceita exclusivamente payload:

- com assinatura Ed25519 válida;
- `environment=dev`;
- não expirado;
- com URL HTTPS terminando em `.trycloudflare.com`;
- cujo destino foi previamente validado pelo publisher via `/api/health`.

O payload expira em 15 minutos. Mensagens inválidas ou spam no tópico público
são ignorados.

## Resiliência local

A tarefa `ReqSys-Dev-Runtime-Supervisor` executa a cada 5 minutos e possui:

- `DisallowStartIfOnBatteries=false`;
- `StopIfGoingOnBatteries=false`;
- `StartWhenAvailable=true`;
- `ExecutionTimeLimit=PT10M`;
- `MultipleInstancesPolicy=IgnoreNew`.

O supervisor recupera containers, reconcilia os dois Cloudflare tunnels e
publica o locator assinado.

## Evidência

Em 2026-09-20:

- Cloudflare A: `/api/health` HTTP 200;
- Cloudflare B: `/api/health` HTTP 200;
- queda controlada do NPort não afetou os dois Cloudflare;
- publisher assinou e publicou dois endpoints saudáveis no ntfy com HTTP 200;
- leitura externa do ntfy recuperou a mensagem assinada;
- nenhuma credencial externa nova foi criada.

## Limites

- Quick Tunnel continua sendo um transporte de desenvolvimento sem SLA;
- GitHub Pages é locator/entrada estável, não proxy reverso;
- HML e PROD não são promovidos por esta ADR;
- prova pós-reboot/headless permanece um gate separado.

## Critério de conclusão DEV

- Pages `/dev/` publicado;
- assinatura/expiração validadas no navegador;
- redirecionamento somente para tunnel DEV vigente;
- supervisor recorrente produz novo locator sem intervenção;
- Cloudflare redundante permanece verde;
- custo adicional igual a zero.
