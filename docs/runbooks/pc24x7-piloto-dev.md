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

### Cadência e orçamento do locator

A tarefa `ReqSys-Dev-Runtime-Supervisor` usa intervalo de 6 minutos (`PT6M`).
Como o publisher envia no máximo uma mensagem por ciclo, o teto recorrente é de
240 ciclos em 24 horas (`ceil(24 * 60 / 6)`), abaixo do limite anônimo de 250
mensagens por visitante/IP do ntfy. O locator continua com TTL de 15 minutos:
uma execução perdida leva a próxima tentativa prevista a 12 minutos, mantendo
três minutos de folga antes da expiração.

O instalador mantém um Python dedicado em
`%LOCALAPPDATA%/ReqSys/RuntimeSupervisor/python`, com dependências fixadas para
DPAPI e Ed25519. O wrapper da tarefa aponta somente para esse interpretador;
remoção ou atualização do Python usado no checkout não interrompe mais a
renovação.

O job `watch-locator` do workflow `Teams Commit Notification` executa a cada 10
minutos em runner GitHub-hosted e valida assinatura, contrato e TTL mínimo de 300 segundos. A
primeira transição para indisponível/expirando alerta o Teams pelo webhook
governado de contingência; repetições consecutivas não geram novo alerta. Quando
o locator volta a ficar fresco após uma execução falha, o workflow envia uma
única notificação de recuperação. O run permanece vermelho enquanto o locator
não estiver fresco e publica evidência sanitizada por 30 dias.

Não reduza o intervalo sem recalcular esse orçamento. Execuções manuais são
operacionais e devem permanecer excepcionais, pois também consomem a cota do
canal público.

Antes de executar o instalador, confira se os nomes de containers em
`pc24x7_dev_runtime_supervisor.py` correspondem ao deployment ativo. O instalador
copia esses scripts para `%LOCALAPPDATA%`; não o use para alterar somente a
cadência quando houver drift entre a fonte e o runtime endurecido instalado.

### Relay emergencial da mesma mensagem assinada

Quando o IP do PC24x7 atingir a cota anônima, gere um envelope público temporário
com `pc24x7_dev_locator_publisher.py --sign-only --envelope-output <arquivo>` e
despache `dispatch-public-runtime-evidence.yml` na `main` com
`operation=relay-dev-locator`, o SHA exato e a confirmação
`RELAY_DEV_LOCATOR`. O workflow valida a `main` antes do checkout, revalida a
assinatura, exige pelo menos 300 segundos de TTL, executa o smoke público antes
do POST e comprova a mensagem exata por readback. O `id` devolvido pelo POST é
validado e salvo apenas como metadado sanitizado. Para absorver a consistência
eventual do ntfy, somente o readback desse `id` faz polling: no máximo seis
consultas com intervalo fixo de dois segundos, limitado a 40 segundos. O POST
continua único e qualquer divergência de `id`, hash, assinatura ou TTL falha
fechado.

O envelope assinado e sua codificação Base64 são material público de curta
duração; a chave privada DPAPI nunca deixa o PC24x7. Apague o arquivo temporário
após o dispatch. Um 429 deve encerrar a operação: não publique o locator em Gist,
Issue, Pages ou outro canal alternativo.

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
- tarefa recorrente usa intervalo de 6 minutos, tolera um ciclo perdido com três minutos de folga e mantém o orçamento do ntfy;
- monitor externo valida TTL mínimo de 300 segundos e alerta somente nas transições de falha/recuperação;
- nenhuma porta de backend está exposta diretamente;
- evidência vinculada ao SHA corrente.
