# Operational Governance Orchestrator

## Objetivo

Consolidar a leitura operacional dos principais workflows e PRs em um único artifact executivo, reduzindo falsos positivos, race conditions e dispersão de evidências.

## Escopo

O orchestrator:

- consulta runs recentes da branch monitorada;
- identifica workflows críticos verdes, amarelos, vermelhos, pendentes e ausentes;
- consulta PRs abertos;
- calcula score operacional;
- gera JSON de auditoria;
- gera Markdown executivo;
- publica artifact consolidado.

## Modo

`report_only`

## Fora de escopo

O orchestrator não:

- faz merge;
- executa deploy;
- altera produção;
- altera branch protection;
- executa rerun;
- altera labels;
- altera secrets.

## Workflows críticos monitorados

- CI — ReqSys v2 Enterprise
- CI Enterprise Fast
- Fast CI - Operational Guardrails
- Governance Quality Gates
- Governança Padrão Ouro
- PR CI Watch
- PR Evidence Gate
- PR Conflict Guard
- Branch Protection Audit
- Main Post-Merge Validation
- Actions Auto Operator
- Workflow Command Center

## Artifact

Artifact esperado:

`operational-governance-orchestrator-evidence`

Conteúdo:

- `operational-governance-orchestrator.json`
- `summary.md`

## Decisão operacional

| Estado | Significado | Ação |
|---|---|---|
| `green` | Sem falha crítica, sem pendências e sem ausências críticas | Continuar incrementos |
| `yellow` | Pendências ou workflows críticos ausentes na janela recente | Validar logs/artifacts antes de merge |
| `red` | Falha crítica real em workflow crítico | Bloquear novos merges até correção |

## Guard rails

| Guard rail | Valor |
|---|---|
| `merge` | false |
| `deploy` | false |
| `production_change` | false |
| `rerun` | false |
| `branch_protection_change` | false |

## Links

- Actions: https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions
