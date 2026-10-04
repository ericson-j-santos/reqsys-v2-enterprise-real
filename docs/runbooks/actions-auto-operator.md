# Actions Auto Operator

## Objetivo

Automatizar a verificação de GitHub Actions e permitir rerun automático governado apenas para falhas transitórias em workflows allowlisted.

## Escopo

O operador:

- consulta runs recentes da branch monitorada;
- classifica runs por workflow, conclusão e elegibilidade;
- executa rerun somente quando `mode=execute`;
- publica artifact `actions-auto-operator-evidence`;
- mantém relatório JSON e Markdown.

## Modos

| Modo | Comportamento |
|---|---|
| `dry_run` | Verifica e gera evidência, sem executar rerun |
| `execute` | Verifica e executa rerun de falhas transitórias allowlisted |

## Workflows allowlisted

- `Main Post-Merge Validation`
- `PR CI Watch`
- `PR Conflict Guard`
- `Branch Protection Audit`
- `Fast CI - Operational Guardrails`
- `Workflow Command Center`

## Conclusões elegíveis para rerun automático

- `cancelled`
- `timed_out`
- `action_required`

## Conclusões bloqueadas

| Conclusão | Tratamento |
|---|---|
| `failure` | Não executa rerun automático; exige diagnóstico/correção |

## Fora de escopo

Este operador não:

- faz merge;
- faz deploy;
- altera produção;
- altera secrets;
- altera branch protection;
- executa workflows fora da allowlist;
- mascara falha real de código.

## Artifact

Artifact esperado:

`actions-auto-operator-evidence`

Conteúdo:

- `actions-auto-operator.json`
- `summary.md`

## Decisão operacional

| Situação | Decisão |
|---|---|
| Sem candidatos | Apenas registrar evidência |
| `cancelled`/`timed_out` allowlisted | Pode executar rerun automático |
| `failure` real | Bloquear auto-rerun e exigir correção |
| Workflow fora da allowlist | Não executar |

## Links

- Actions: https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions
