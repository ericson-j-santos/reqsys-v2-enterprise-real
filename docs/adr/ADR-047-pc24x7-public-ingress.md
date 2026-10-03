# ADR-047 — Publicação DEV zero-cost no PC24x7

Status: **aceito para DEV**
Data: 2026-09-20
Atualizado: 2026-10-02

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

O PC24x7 publica a cada ciclo de 7 minutos o estado atual dos tunnels em um
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
- cujo destino foi previamente validado pelo contrato completo: quatro endpoints
  `/api/*`, frontend estático em `/task-console` e ausência de HMR em `/@vite/client`.

O payload expira em 15 minutos. A cadência de 7 minutos permite que uma execução
seja perdida e que a próxima tentativa prevista ocorra em 14 minutos, antes da
expiração. O teto recorrente é de 206 ciclos por 24 horas, abaixo do limite
anônimo de 250 mensagens por visitante/IP do ntfy. Restam 44 mensagens de folga
para operações excepcionais; múltiplas falhas ou atraso superior a um minuto
continuam fora do SLA de um Quick Tunnel DEV. Mensagens inválidas ou spam no
tópico público são ignorados.

## Resiliência local

A tarefa `ReqSys-Dev-Runtime-Supervisor` executa a cada 7 minutos e possui:

- `DisallowStartIfOnBatteries=false`;
- `StopIfGoingOnBatteries=false`;
- `StartWhenAvailable=true`;
- `ExecutionTimeLimit=PT10M`;
- `MultipleInstancesPolicy=IgnoreNew`.

O supervisor recupera containers, reconcilia os dois Cloudflare tunnels e
publica o locator assinado.

A reconciliação manual `public-static` não altera nem limpa o checkout que
originou o runtime encontrado. Ela cria ou atualiza por fast-forward um worktree
dedicado `wt-pc24x7-public-dev-governed`, sempre em um SHA pertencente à `main`,
e recria somente `api`, `frontend` e `nginx` a partir dessa árvore limpa. Os
overrides locais DEV de administração e Pages continuam reutilizados por lista
permitida; overrides versionados e o SHA vêm do worktree governado.

Quando o runtime inclui o override do bot Teams, o workflow autentica no Azure
por OIDC do environment `development` e reutiliza o segredo DEV já existente no
Key Vault. O valor é entregue apenas ao processo filho do Docker Compose,
apagado do ambiente em memória após o uso e nunca registrado em evidência. A
operação não rotaciona credenciais e não possui caminho para HML ou PROD.

Em esgotamento excepcional da cota do IP local, um workflow manual e vinculado ao
SHA exato da `main` pode retransmitir pelo mesmo ntfy um envelope público assinado
no PC24x7. Esse relay não recebe a chave privada, não altera a identidade do
locator, executa smoke antes de um único POST e exige readback do envelope exato.
Ele é recuperação operacional, não um segundo provedor nem fonte de verdade.

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
