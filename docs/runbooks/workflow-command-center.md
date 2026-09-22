# Workflow Command Center

## Objetivo

Monitorar workflows criticos do ReqSys e permitir execucao controlada de workflows allowlisted via `workflow_dispatch`.

## Escopo

O Command Center:

- lista runs recentes da branch `main`;
- identifica workflows criticos com falha ou pendencia;
- gera artifact de evidencia;
- permite disparar apenas workflows na allowlist;
- apresenta a serie historica de melhoria do processo CI;
- calcula sustentabilidade somente com observacoes explicitamente comparaveis ao baseline;
- nao executa deploy;
- nao altera producao;
- nao altera secrets;
- nao faz merge automatico.

## Sustentabilidade da melhoria de processo

A classificacao `process_improvement_history.sustainability` usa somente registros com:

`window_comparability.comparable_to_baseline=true`

Registros com `false` ou sem comparabilidade explicita continuam preservados no contexto historico, mas nao entram:

- na contagem de sinais `improved`, `stable` ou `regressed` usada para sustentabilidade;
- nas medias recentes de success rate, failure rate, P95 e CV;
- no minimo de tres observacoes necessario para sair de `insufficient_data`.

O resumo publica tambem:

- `records`: total historico;
- `comparable_records`: total elegivel para sustentabilidade;
- `excluded_non_comparable_records`: registros preservados, mas excluidos da decisao;
- `sustainability_basis=comparable_to_baseline_only`;
- `series`: janela recente somente de registros comparaveis;
- `recent_context`: contexto recente completo, inclusive registros nao comparaveis e seus motivos.

A regra permanece `report-only` e `creates_gate=false`. Comparabilidade estrutural nao equivale a significancia estatistica nem prova causal.

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
- `ci-process-improvement-history.json`
- `ci-process-improvement-history.md`
- `workflow-command-center.html`

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
- Historico nao comparavel nunca e promovido a evidencia de sustentabilidade.

## Como executar manualmente

1. Abrir Actions.
2. Selecionar `Workflow Command Center`.
3. Clicar em `Run workflow`.
4. Opcionalmente informar um workflow allowlisted.
5. Confirmar artifact `workflow-command-center-evidence`.
6. Conferir `process_improvement_history.comparable_records` antes de interpretar sustentabilidade.

## Decisao operacional

| Resultado | Decisao |
|---|---|
| Sem falhas criticas | Continuar incrementos |
| Falhas criticas | Pausar e corrigir Pareto |
| Pendencias | Aguardar ou investigar logs |
| Workflow ausente na janela recente | Validar se precisa disparo manual |
| Menos de 3 observacoes comparaveis | Manter `insufficient_data` |
| `sustained_improvement` | Interpretar somente como evidencia observacional comparavel, sem prova causal |

## Links

- Actions: https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions
