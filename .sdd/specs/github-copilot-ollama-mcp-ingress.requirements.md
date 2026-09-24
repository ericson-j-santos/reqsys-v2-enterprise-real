# GitHub Copilot Ollama MCP — ingresso HTTPS DEV

## Objetivo

Expor somente o bridge MCP local do Ollama em HTTPS estável para o GitHub Copilot,
reutilizando Tailscale Funnel no Desktop PC24x7. Ollama `:11434` e o gateway
`:8008` permanecem loopback-only.

## Requisitos

1. Executar somente em `DESKTOP-PDQK954`, DEV, no runner allowlisted
   `self-hosted, Windows, X64, pc24x7, reqsys-dev`.
2. O único alvo público permitido é `http://127.0.0.1:8010`; o health local `127.0.0.1:8011/health` nunca pode ser alvo do Funnel.
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
   `/reqsys run github-copilot-ollama-mcp-ingress-dev` na issue #1705, mapear
   esse comando para o workflow canônico `codex-ollama-e2e-dev.yml` com modo
   fechado `mcp-ingress` e aplicar a mesma validação de pickup/cancelamento dos
   demais jobs self-hosted.
10. O workflow canônico deve preservar o modo `codex-e2e` existente e admitir
    somente os modos enumerados `codex-e2e` e `mcp-ingress`; não criar novo
    workflow para o ingresso MCP.
11. No runner self-hosted PC24x7, o workflow deve reutilizar o Python já
    provisionado, validar o executável antes do uso e falhar rapidamente se ele
    estiver indisponível; não deve instalar Python nem alterar o Registro do host.
12. O reconciliador não pode depender do `PATH` interativo para localizar a CLI
    do Tailscale. Deve aceitar `TAILSCALE_CLI_PATH` somente quando apontar para
    arquivo existente, tentar descoberta pelo `PATH` do serviço e pelos diretórios
    de instalação locais conhecidos e falhar fechado com `TAILSCALE_CLI_NOT_FOUND`
    quando nenhum binário for comprovado.
13. Antes de reconciliar o Funnel, o modo `mcp-ingress` deve validar a dependência MCP e reconciliar a release imutável do supervisor PC24x7 no mesmo `github.sha`, incluindo o bridge `:8010`. O workflow e o reconciliador de Funnel não podem ler/imprimir o valor do bearer nem criar/rotacionar segredos; o supervisor apenas consome o bearer pré-provisionado do ambiente local e falha fechado se ele estiver ausente.
14. HML e PROD ficam fora do escopo.

## Critérios de aceite

1. Testes provam host, target, path e comando Tailscale fixos e rejeitam alvo
   diferente.
2. Testes provam que `:11434`, `:8008`, `:8011` e `:8083` não entram no comando
   público deste incremento.
3. O comando do gateway é inputless; o workflow canônico é DEV-only, consta da
   allowlist self-hosted, aceita apenas `codex-e2e|mcp-ingress` e não referencia
   bearer token.
4. O gateway usa comando, workflow e modo exatos e falha fechado se o runner não
   adquirir o job.
5. O budget de workflows permanece com crescimento líquido zero.
6. `READY_FOR_PR=passed` no HEAD exato antes da PR.
7. E2E físico exige bridge local ativo, rota Funnel observada e probe externo de
   `https://<desktop>.ts.net/mcp`; CI isolada não substitui essa evidência.
8. Testes de workflow impedem reintroduzir `actions/setup-python` no runner
   self-hosted e comprovam o uso do executável Python provisionado.
9. Testes do reconciliador comprovam resolução explícita da CLI do Tailscale,
   rejeição de caminho configurado inexistente e erro determinístico quando o
   binário não estiver disponível no ambiente do serviço.
10. Testes do workflow comprovam a reconciliação do supervisor PC24x7 no SHA exato antes do Funnel, a inclusão do bridge na release e a ausência de referência literal ao bearer no YAML.
