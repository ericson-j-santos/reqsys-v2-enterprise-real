# Repository Health Watchdog

## Objetivo

Automatizar a verificacao recorrente da saude operacional do repositorio ReqSys, com foco em CI, evidencias pos-merge, PRs duplicados e PRs de risco.

## Escopo

O monitor valida:

- existencia de run recente do `Main Smoke CI` na `main`;
- conclusao `success` do run;
- presenca do artifact `main-smoke-ci-evidence`;
- PRs abertos duplicados por titulo normalizado;
- PRs abertos com indicios de risco operacional, como workflows, deploy, runtime, security, promotion e governance.

## Fora do escopo

Este workflow nao:

- fecha PR automaticamente;
- aprova PR;
- faz merge;
- executa deploy;
- altera producao;
- altera secrets;
- altera branch protection.

## Gatilhos

- `workflow_dispatch` manual;
- agendamento horario via cron.

## Artifact

O workflow publica o artifact `repository-health-watchdog-report` contendo:

- `repository-health-report.json`;
- `repository-health-summary.md`.

## Politica de falha

Por padrao, o workflow nao falha em gaps criticos para evitar ruido operacional durante estabilizacao.

Na execucao manual, usar `fail_on_critical=true` para transformar gaps criticos em falha do job.

## Recomendacao operacional

1. Executar manualmente apos merges relevantes na `main`.
2. Manter agendamento horario ativo.
3. Usar o artifact como evidencia de auditoria.
4. Tratar falha critica antes de novos PRs de produto, UI, deploy ou runtime.
5. Fechar PRs duplicados manualmente apos revisao humana.

## Severidade

| Severidade | Significado | Acao |
|---|---|---|
| critical | Falta evidencia pos-merge ou artifact obrigatorio | Bloquear proximo incremento |
| medium | PRs duplicados ou PRs de risco abertos | Triage/rebase/fechamento manual |
| info | Estado esperado | Manter monitoramento |

## Decisao arquitetural

O monitor e somente leitura nesta versao. A automacao destrutiva ou mutavel deve ser criada apenas em incremento posterior, com allowlist, labels explicitas, revisao humana e artifact de decisao.
