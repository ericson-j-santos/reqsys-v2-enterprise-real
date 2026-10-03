# Executive Readiness Gate

## Resumo

Adiciona um gate executivo report-only para consolidar o Estado Único ReqSys em uma decisão única de promoção para produção.

## Entradas consolidadas

- Runtime Validation Consolidator.
- Executive Brief do Ops Dashboard.
- Runtime público.
- Security Baseline Gate.
- Regression Alert temporal.
- Pós-deploy.
- Pós-merge.
- PR Evidence Gate.

## Saídas

- `artifacts/executive-readiness-gate/executive-readiness-gate.json`
- `artifacts/executive-readiness-gate/summary.md`

## Decisão executiva

O gate gera:

- `READY_FOR_PRODUCTION`
- `BLOCKED_FOR_PRODUCTION`

A decisão considera CI/CD, merge queue, auto-merge, runtime público, deploy, smoke checks, segurança, regressão temporal e evidências executivas.

## Guardrails

- Sem deploy.
- Sem merge.
- Sem chamadas externas.
- Sem leitura de secrets.
- Sem mudança de produção.
- Execução report-only por padrão.

## Validação

```bash
python -m unittest tests/test_executive_readiness_gate.py
python scripts/executive_readiness_gate.py --repo local/reqsys --branch main
```

## Próximo incremento seguro

Conectar `executive-readiness-gate.json` ao Runtime Executive Index e ao Ops Dashboard como indicador executivo de topo.
