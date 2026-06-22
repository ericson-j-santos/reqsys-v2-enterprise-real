# Plano de Testes — Estatísticas v2

## Backend

```bash
cd backend
python -m pytest tests/test_estatisticas.py -v --tb=short
```

Validações esperadas:

- `GET /v1/estatisticas` retorna 200.
- Envelope padrão `success=true`.
- `schema_version=2.0.0`.
- `correlation_id` é propagado.
- Todo indicador possui fonte, fórmula, estado, tendência e confiabilidade.
- Fonte externa permanece `nao_medido` sem registry real.

## Frontend

```bash
cd frontend
npm test -- estatisticas
npm run build
```

Validações esperadas:

- Serviço carrega `/v1/estatisticas` quando API responde.
- Fallback local é usado somente em falha.
- Fallback é identificável por `frontend-runtime-fallback`.
- Guard rails continuam bloqueando indicador sem fonte/fórmula.

## CI obrigatório

- Backend Tests + Coverage verde.
- Backend Lint & Security verde.
- Frontend Build + Security Audit verde.
- Frontend Responsive E2E verde.
- Governance Quality Gates verde.
- Governança Padrão Ouro verde.
