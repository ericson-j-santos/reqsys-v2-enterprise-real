# Release Note — Codex Operational Audit Layer P1.2

## Entregas

- Modelo persistente `CodexAuditoria`.
- Registro automatico de auditoria em analises do Codex Governado.
- Indicadores agregados em `GET /v1/codex/operational-summary`.
- Score de confianca operacional.
- Latencia media.
- Distribuicao por provider.
- Testes automatizados de persistencia e resumo operacional.

## Validacao

```bash
cd backend
python -m pytest tests/test_codex_governado.py -v
python -m pytest tests/ -v --tb=short --cov=app --cov-report=term-missing --cov-fail-under=60
```

## Proximo incremento

Criar UI nativa dentro do ReqSys para o dashboard Codex, com drill-down por `correlation_id`, provider, usuario, status e periodo.
