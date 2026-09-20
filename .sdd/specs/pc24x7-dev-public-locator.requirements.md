# Requisitos — Locator público DEV zero-cost

## Objetivo

Fornecer uma URL estável para o ambiente DEV sem domínio pago, token DuckDNS,
consentimento Tailscale ou dependência de um subdomínio NPort que possa ficar
preso após crash.

## Arquitetura

```text
GitHub Pages /dev/
      |
      +--> lê estado assinado do ntfy
                  |
PC24x7 --Ed25519--> ntfy.sh
  |
  +--> Cloudflare Quick Tunnel A --> :8083
  +--> Cloudflare Quick Tunnel B --> :8083
```

## Requisitos

1. A URL estável deve ser
   `https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/dev/`.
2. A chave privada Ed25519 deve permanecer somente no PC24x7 e protegida por
   Windows DPAPI.
3. O repositório pode conter somente a chave pública e o tópico público.
4. O publisher deve aceitar como destino somente URLs HTTPS
   `*.trycloudflare.com` que respondam `/api/health` com HTTP 200.
5. Cada payload deve expirar em no máximo 15 minutos.
6. O locator deve ignorar mensagens inválidas, não assinadas, expiradas ou de
   ambiente diferente de DEV.
7. A tarefa local deve publicar novo estado a cada ciclo de 5 minutos.
8. Cloudflare Quick Tunnel permanece o transporte; GitHub Pages é apenas a
   entrada estável/descoberta.
9. Tailscale, DuckDNS e NPort não podem bloquear o DEV.
10. HML e PROD permanecem fora deste incremento.
11. Após merge automático governado, o Pages deve ser acionado pela conclusão bem-sucedida do `Governed PR Automation` quando esse workflow tiver origem `workflow_run`.
12. O run que dispara o deploy não pode ser tratado como produtor do dashboard Teams; o deploy deve resolver separadamente o último `Teams Notification Dashboard` bem-sucedido.
13. A `Validação de Acessos Públicos — ReqSys` deve executar após `Governed PR Automation` concluído com sucesso no caminho `workflow_run`, mantendo a URL `/dev/` como alvo obrigatório.

## Critérios de aceite

- testes do contrato passam;
- publisher local retorna HTTP 200 no ntfy;
- mensagem é legível externamente;
- GitHub Pages publica `/dev/`;
- `/dev/` valida assinatura e redireciona apenas para tunnel vigente;
- task scheduler preserva bateria/StartWhenAvailable/timeout de 10 minutos;
- deploy pós-merge ocorre mesmo quando o merge foi executado com `GITHUB_TOKEN`;
- simples abertura/edição de PR não dispara esse caminho de redeploy;
- validação pública pós-merge é disparada automaticamente e falha se o alvo obrigatório estiver indisponível;
- nenhuma dependência paga é introduzida.
