# Evidência DEV — public locator zero-cost — 2026-09-20

## Escopo

PR #1864 — URL DEV estável por GitHub Pages com estado dinâmico assinado.

## Runtime físico

Host: Noteri / PC24x7 DEV.

- gateway local `:8083` saudável;
- dois Cloudflare Quick Tunnels com `/api/health` HTTP 200;
- queda controlada de transporte alternativo não interrompeu os dois Cloudflare;
- Task Scheduler confirmado com repetição PT5M;
- tarefa corrigida para:
  - iniciar em bateria;
  - não parar ao entrar em bateria;
  - `StartWhenAvailable=true`;
  - `ExecutionTimeLimit=PT10M`.

## Locator assinado

Publisher local:

- gera Ed25519 no host;
- protege a chave privada com Windows DPAPI;
- publica somente chave pública, payload e assinatura;
- aceita apenas endpoints HTTPS `*.trycloudflare.com` que respondam health;
- payload expira em 15 minutos;
- publicação ntfy retornou HTTP 200 com dois endpoints saudáveis;
- leitura externa do ntfy recuperou a mensagem.

## Validação independente

HEAD anterior ao commit desta evidência: `e2cef81703b9f2714dab2baf34b477db08862a4c`.

- pytest direcionado: **9/9 passed**;
- E2E Edge/Playwright:
  - CORS ntfy: aprovado;
  - WebCrypto Ed25519: aprovado;
  - dois links DEV válidos produzidos;
  - nenhum endpoint fora de `*.trycloudflare.com` aceito.

Correlações:

- `corr-dev-locator-tests-v2-20260920`
- `corr-dev-locator-browser-e2e-20260920`
- `corr-dev-locator-publish-bootstrap-20260920`

## Limite

Não constitui prova pós-reboot/headless. Esse gate permanece separado.
