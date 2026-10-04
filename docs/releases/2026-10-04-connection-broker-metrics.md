# Connection Broker — métricas operacionais

O PR #69 adiciona métricas agregadas do Connection Broker à stack .NET atual.

## Entregue

- `GET /api/connectors/metrics`;
- `GET /v1/connectors/metrics`;
- famílias Prometheus para total, status, criticidade, confirmação humana e eventos de auditoria;
- sanitização de labels;
- testes xUnit e contrato preventivo;
- documentação do contrato runtime.

## Não alterado

- permissões ou credenciais dos conectores;
- comportamento dos checks de capability;
- baseline Azure AD e gates produtivos;
- deploy ou promoção de ambiente.
