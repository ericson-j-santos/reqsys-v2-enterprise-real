# Runtime Health Validator + Governed Remediation Executor

## Objetivo

Detectar regressões operacionais reais e gerar plano de remediação governado, com execução allowlisted apenas quando explicitamente autorizado.

## Modos

| Modo | Comportamento |
|---|---|
| `report_only` | Detecta, classifica e gera evidência sem executar remediação |
| `dry_run` | Simula plano de remediação sem executar |
| `execute` | Executa somente remediações allowlisted |

## Escopo

O validador:

- consulta runs recentes de GitHub Actions;
- classifica saúde operacional;
- calcula severidade;
- diferencia falha real de falha transitória;
- gera plano de remediação;
- executa rerun somente quando permitido e em modo `execute`;
- gera artifact auditável.

## Remediações allowlisted

- `Actions Auto Operator`
- `Operational Governance Orchestrator`
- `Main Post-Merge Validation`
- `PR CI Watch`
- `PR Conflict Guard`
- `Branch Protection Audit`
- `Fast CI - Operational Guardrails`

## Conclusões transitórias elegíveis

- `cancelled`
- `timed_out`
- `action_required`

## Falhas bloqueadas

| Conclusão | Tratamento |
|---|---|
| `failure` | Não executa remediação automática; exige diagnóstico/correção |

## Guard rails

| Guard rail | Valor |
|---|---|
| merge | false |
| deploy | false |
| production_change | false |
| branch_protection_change | false |
| secrets_change | false |
| anti_loop | true |

## Artifact

Artifact esperado:

`runtime-health-validator-evidence`

Conteúdo:

- `runtime-health-validator.json`
- `summary.md`

## Critério de aceite

| Critério | Estado alvo |
|---|---|
| CI verde | Sim |
| Artifact publicado | Sim |
| Correlation ID | Presente |
| Plano de remediação | Presente |
| Falhas reais bloqueadas | Sim |
| Modo padrão seguro | `report_only` |
| Sem deploy/produção | Sim |

## Links

- Actions: https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions
