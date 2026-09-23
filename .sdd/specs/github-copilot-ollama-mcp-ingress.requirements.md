# GitHub Copilot Ollama MCP — ingresso HTTPS DEV

## Objetivo

Expor somente o bridge MCP local do Ollama em HTTPS estável para o GitHub Copilot,
reutilizando Tailscale Funnel no Desktop PC24x7. Ollama `:11434` e o gateway
`:8008` permanecem loopback-only.

## Requisitos

1. Executar somente em `DESKTOP-PDQK954`, DEV, no runner allowlisted
   `self-hosted, Windows, X64, pc24x7, reqsys-dev`.
2. O único alvo público permitido é `http://127.0.0.1:8010`.
3. O mount público é exatamente `/mcp`, HTTPS porta 443, usando
   `tailscale funnel --bg`.
4. O reconciliador deve exigir `BackendState=Running`, MagicDNS e hostname
   `*.ts.net`.
5. O bridge local precisa estar escutando antes de qualquer alteração no Funnel;
   caso contrário, falhar com `MCP_LOCAL_NOT_READY`.
6. Consentimento único de Funnel ausente deve ser classificado como
   `TAILSCALE_FUNNEL_CONSENT_REQUIRED`, sem abrir navegador automaticamente.
7. Nenhum segredo, bearer token, conteúdo de prompt ou resposta do modelo pode
   ser lido, gravado ou publicado pelo reconciliador.
8. A evidência deve ser sanitizada, vinculada ao SHA exato e declarar
   explicitamente que produção, `:11434` e `:8008` não foram publicados.
9. O Authorized Actions Gateway deve aceitar somente o comando exato
   `/reqsys run github-copilot-ollama-mcp-ingress-dev` na issue #1705 e deve
   aplicar a mesma validação de pickup/cancelamento dos demais jobs self-hosted.
10. HML e PROD ficam fora do escopo.

## Critérios de aceite

1. Testes provam host, target, path e comando Tailscale fixos e rejeitam alvo
   diferente.
2. Testes provam que `:11434`, `:8008` e `:8083` não entram no comando
   público deste incremento.
3. O workflow é inputless, DEV-only, consta da allowlist self-hosted e não
   referencia bearer token.
4. O gateway usa comando e workflow exatos e falha fechado se o runner não
   adquirir o job.
5. `READY_FOR_PR=passed` no HEAD exato antes da PR.
6. E2E físico exige bridge local ativo, rota Funnel observada e probe externo de
   `https://<desktop>.ts.net/mcp`; CI isolada não substitui essa evidência.
