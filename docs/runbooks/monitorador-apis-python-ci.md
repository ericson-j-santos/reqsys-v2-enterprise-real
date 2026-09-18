# Runbook — CI do Monitorador de APIs Python

## Objetivo

Orientar correções futuras no workflow `Testes Monitorador APIs Python`.

## Workflow

Arquivo: `.github/workflows/testes-monitorador-apis-python.yml`

Comando crítico:

```bash
pytest --cov=app --cov-report=term-missing --cov-fail-under=85
```

## Regra operacional

Falha de cobertura deve ser tratada preferencialmente com expansão de testes, não com redução do limiar.

## Correção aplicada neste incremento

- Testes adicionais para `/api/resultados`.
- Teste mockado para `/api/monitorar`.
- Teste mockado para `/dashboard`.

## Critério de pronto

- Workflow verde.
- Sem chamadas externas reais.
- Sem redução de gate.
