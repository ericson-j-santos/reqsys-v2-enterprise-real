# Schema Runtime Enforcement

Atualizado em: 2026-06-24

## Objetivo

Garantir que os contratos governados em `docs/schema-registry.json` sejam aplicados também em runtime, não apenas no CI.

## Estado implementado

| Capacidade | Estado |
|---|---|
| Runtime enforcer framework-agnostic | Implementado em `runtime/schema_runtime_enforcer.py` |
| Métricas runtime | Implementadas em `runtime/schema_metrics.py` |
| Auditoria runtime | Implementada em `runtime/schema_audit.py` |
| Fixtures válidas/inválidas | Implementadas em `examples/runtime/**` |
| Testes runtime | Implementados em `tests/schema_runtime/test_schema_runtime_enforcer.py` |
| Workflow CI runtime | Implementado em `.github/workflows/schema-runtime-validation.yml` |

## Regras aplicadas em runtime

| Regra | Bloqueio |
|---|---|
| Contrato desconhecido | Sim |
| Contrato sem `runtime_validation_required` | Sim |
| Payload sem JSON object root | Sim |
| Payload sem `schema_version` válida | Sim |
| `schema_version` incompatível | Sim |
| Required field ausente | Sim |
| Enum inválido | Sim |
| Campo extra com `additionalProperties: false` | Sim |
| Tipo incompatível | Sim |

## Métricas geradas

| Métrica | Significado |
|---|---|
| `schema_validation_total` | Total de validações runtime |
| `schema_validation_passed_total` | Validações aprovadas |
| `schema_validation_failed_total` | Validações rejeitadas |
| `schema_version_mismatch_total` | Divergências de versão |
| `schema_runtime_blocked_payload_total` | Payloads bloqueados |
| `contract_runtime_coverage` | Cobertura operacional runtime |

## Exemplo de uso via CLI

```bash
python runtime/schema_runtime_enforcer.py \
  product-intelligence-event \
  examples/runtime/product-intelligence-event.runtime.valid.json \
  --correlation-id manual-runtime-check
```

## Exemplo de uso como adapter

```python
from runtime.schema_runtime_enforcer import SchemaRuntimeEnforcer

enforcer = SchemaRuntimeEnforcer()
result = enforcer.validate(
    "product-intelligence-event",
    payload,
    correlation_id="request-123",
)
```

## Modo não bloqueante

Para rollout gradual, é possível usar `block=False`:

```python
result = enforcer.validate(
    "product-intelligence-event",
    payload,
    correlation_id="request-123",
    block=False,
)
```

Esse modo gera auditoria e métricas, mas não lança exceção.

## Política operacional recomendada

| Ambiente | Modo recomendado |
|---|---|
| Desenvolvimento | `block=False` inicialmente, depois `block=True` |
| Homologação | `block=True` para contratos críticos |
| Produção | `block=True` obrigatório em entradas/saídas críticas |

## Limites atuais

- O enforcer é framework-agnostic; ainda não está acoplado a FastAPI/Flask/Django/Express.
- A persistência de auditoria é em memória nesta primeira versão.
- A exportação Prometheus/OpenTelemetry ainda depende de adapter futuro.
- A validação usa o subconjunto governado já consolidado no Schema Governance Gate.

## Próximo incremento recomendado

Integrar o enforcer ao ponto real de entrada/saída da API do ReqSys, publicando métricas para o dashboard operacional vivo e elevando `contract_runtime_coverage` com evidência de execução real.
