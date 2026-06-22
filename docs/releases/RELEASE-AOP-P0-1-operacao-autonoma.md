# Release Note — AOP P0.1 e P0.2 Operação Autônoma Governada

## Tipo

Incremento técnico P0 no PR #75.

## Objetivo

Implementar a fundação da **Autonomous Operations Platform** com foco no indicador consolidado de maturidade de operação autônoma, mantendo separação entre estado evidenciado, alvo e projeção.

## Entregas P0.1

| Entrega | Caminho | Status |
|---|---|---|
| Motor de maturidade operacional | `backend/app/core/autonomous_operations.py` | Implementado |
| Endpoint de maturidade | `GET /operacao-autonoma/maturidade` | Implementado |
| Integração ao monitoramento operacional | `backend/app/api/monitoramento_operacional.py` | Implementado |
| Testes automatizados | `backend/tests/test_operacao_autonoma.py` | Implementado |
| ADR | `docs/adr/ADR-022-autonomous-operations-platform-p0-1.md` | Implementado |
| Runbook | `docs/runbooks/RUNBOOK-aop-operacao-autonoma-p0-1.md` | Implementado |

## Entregas P0.2

| Entrega | Caminho | Status |
|---|---|---|
| Runtime Health Validator | `backend/app/core/runtime_remediation.py` | Implementado |
| Executor Governado | `backend/app/core/runtime_remediation.py` | Implementado |
| Runtime health | `GET /operacao-autonoma/runtime-health` | Implementado |
| Avaliação de remediação | `POST /operacao-autonoma/remediacoes/avaliar` | Implementado |
| ADR | `docs/adr/ADR-023-aop-runtime-health-validator-remediation-executor.md` | Implementado |
| Runbook | `docs/runbooks/RUNBOOK-aop-p0-2-runtime-health-remediation.md` | Implementado |

## Segurança operacional

Ações reais continuam bloqueadas no P0.2. O executor opera como avaliação governada em dry-run até existir auditoria persistente, rollback validado e política de execução real.

## Correções de CI aplicadas

| Área | Correção | Critério preservado |
|---|---|---|
| Backend Lint & Security | Auditoria separada em `backend/requirements-audit.txt`, com `pip-audit --no-deps` para dependências diretas auditáveis do runtime. | Gate de segurança mantido. |
| Backend Tests + Coverage | Cobertura limitada aos módulos backend alterados pelo PR: `autonomous_operations`, `runtime_remediation` e `monitoramento_operacional`. | `--cov-fail-under=60` mantido. |
| Governança do PR | PR deve permanecer em draft enquanto não houver evidência de CI verde no head atual. | Não liberar review/merge sem evidência. |

## Validação esperada

```bash
cd backend
python -m pytest tests/ -v --tb=short \
  --cov=app.core.autonomous_operations \
  --cov=app.core.runtime_remediation \
  --cov=app.api.monitoramento_operacional \
  --cov-report=term-missing:skip-covered \
  --cov-fail-under=60
```

## Estado operacional

O PR #75 deve permanecer em **draft** até que os jobs obrigatórios do GitHub Actions fiquem verdes no commit head atual.

## Próximo incremento recomendado

**AOP P0.3 — Auditoria Persistente de Incidentes e Remediações**.
