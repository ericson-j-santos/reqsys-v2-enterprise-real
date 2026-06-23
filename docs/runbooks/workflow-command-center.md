# Workflow Command Center

## Objetivo

Monitorar workflows criticos do ReqSys e permitir execucao controlada de workflows allowlisted via `workflow_dispatch`.

## Escopo

O Command Center:

- lista runs recentes da branch `main`;
- identifica workflows criticos com falha ou pendencia;
- gera artifact de evidencia;
- permite disparar apenas workflows na allowlist;
- nao executa deploy;
- nao altera producao;
- nao altera secrets;
- nao faz merge automatico.

## Workflows monitorados

- CI — ReqSys v2 Enterprise
- CI Enterprise Fast
- Fast CI - Operational Guardrails
- Governance Quality Gates
- Branch Protection Audit
- PR Conflict Guard
- Main Smoke CI
- Main Operational Health

## Workflows allowlisted para execucao

- `main-smoke-ci.yml`
- `main-operational-health.yml`
- `pr-ci-watch.yml`
- `ci-fast-operational.yml`

## Gatilhos

- Agenda em dias uteis: `37 9 * * 1-5`.
- Manual via `workflow_dispatch`.

## Artifact

Artifact esperado:

`workflow-command-center-evidence`

Conteudo:

- `workflow-command-center.json`
- `summary.md`

## Permissoes

O workflow usa:

- `contents: read`
- `actions: write`

Motivo de `actions: write`: necessario para disparar workflows allowlisted via API.

## Politica de seguranca

- Apenas workflows allowlisted podem ser executados.
- O script falha se o workflow solicitado nao estiver na allowlist.
- Nao existe execucao arbitraria de comandos.
- Nao usa secrets externos.
- Nao manipula ambientes produtivos.

## Como executar manualmente

1. Abrir Actions.
2. Selecionar `Workflow Command Center`.
3. Clicar em `Run workflow`.
4. Opcionalmente informar um workflow allowlisted.
5. Confirmar artifact `workflow-command-center-evidence`.

## Decisao operacional

| Resultado | Decisao |
|---|---|
| Sem falhas criticas | Continuar incrementos |
| Falhas criticas | Pausar e corrigir Pareto |
| Pendencias | Aguardar ou investigar logs |
| Workflow ausente na janela recente | Validar se precisa disparo manual |

## Links

- Actions: https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions
