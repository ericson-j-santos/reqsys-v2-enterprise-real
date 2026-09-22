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
- gera artifact auditável;
- publica **health matrix** (`ci_github`, `fly_*`, `evidence_gate`, `security_gates`);
- calcula **runtime score** canônico ponderado;
- ativa **quarantine** (`AOP-SEC-QUARANTINE-001`) quando gates de segurança falham;
- expõe **retry policy** governada (`AOP-CI-RETRY-001`) com anti-loop;
- aplica **fallback progressivo**: GitHub API → artifact em cache → baseline.

## Health matrix (`schema_version=1.2.0`)

| Linha | Fonte padrão | Probe opcional |
|---|---|---|
| `ci_github` | Runs recentes da branch | — |
| `fly_dev` / `fly_homolog` / `fly_prod` | Endpoints declarados | `--probe-env` |
| `evidence_gate` | Workflow ou artifact local | — |
| `security_gates` | Workflows com keywords de segurança/governança | — |

Cada linha inclui `status`, `score`, `source` (`live` | `artifact` | `declared` | `fallback`) e `detail`.

## Runtime score

Score único `0–100` derivado da health matrix com pesos governados. Propagado para `maturity.score` e consumido pelo Coordenador Status Consolidator como `runtime_score`.

## Quarantine

Quando gates de segurança estão vermelhos ou há gaps `P0`, o artifact define:

```json
{
  "active": true,
  "policy": "AOP-SEC-QUARANTINE-001",
  "blocked_actions": ["deploy", "promote"]
}
```

Sem chamadas destrutivas a Fly/deploy — apenas evidência e guard rails.

## Retry policy governada

Compartilha limites com `scripts/auto_rerun_governed.py`:

- `MAX_RERUN_ATTEMPTS = 2`
- cooldown de 30 minutos documentado
- bloqueio por workflow blocklisted ou tentativas esgotadas
- execução real somente em `--mode execute` com `retry_policy.allowed = true`

## Fallback progressivo

| Estágio | Condição | Confiança |
|---|---|---|
| 1 | GitHub API disponível | `high` |
| 2 | Artifact `runtime-health-validator.json` em cache | `medium` |
| 3 | Baseline mínimo sem runs | `low` |

O campo `data_sources[]` registra cada estágio tentado.

## Flags CLI

| Flag | Efeito |
|---|---|
| `--probe-env` | Faz probe HTTP nos endpoints Fly.io (default: apenas declarados) |
| `--artifact-root` | Raiz para lookup de artifacts locais (evidence gate) |

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
| deploy | true quando quarantine ativa |
| production_change | true quando quarantine ativa |
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
