# Domain Coverage Governance

## Objetivo

Substituir a dependência exclusiva de cobertura global por governança de cobertura por domínio arquitetural.

## Domínios monitorados

- `core`
- `services`
- `api`
- `repositories`
- `runtime`

## Política de adoção

O modo inicial é `record_then_regression`:

1. o primeiro ciclo mede e publica a cobertura real por domínio;
2. os valores medidos são revisados e registrados em `config/domain-coverage-policy.json`;
3. ciclos seguintes falham somente quando um domínio cai abaixo do baseline versionado;
4. metas-alvo permanecem visíveis mesmo quando ainda não bloqueiam o CI.

Essa abordagem evita elevar percentuais de forma arbitrária e reduz falsos bloqueios.

## Evidências

O workflow publica por 30 dias:

- `coverage.json` bruto do Coverage.py;
- `report.json` normalizado por domínio;
- `domain-coverage-latest.json` no contrato de dados do Ops Dashboard.

## Execução local

```bash
python -m pip install -r backend/requirements.txt
cd backend
python -m pytest tests --cov=app --cov-report=json:../artifacts/domain-coverage/coverage.json
cd ..
python scripts/evaluate_domain_coverage.py --json
```

## Ativação do bloqueio por regressão

Após a primeira medição, preencher o objeto `baseline` da política:

```json
{
  "baseline": {
    "core": 72.5,
    "services": 64.0,
    "api": 58.3,
    "repositories": 61.2,
    "runtime": 55.0
  }
}
```

O gate passa com melhoria ou estabilidade e falha quando qualquer domínio regredir além da tolerância configurada.
