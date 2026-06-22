# RUNBOOK — AOP P0.2 Runtime Health Validator e Executor Governado

## Objetivo

Validar e operar a segunda fatia da Autonomous Operations Platform: health por componente e avaliação governada de remediações.

## Endpoints

### Runtime Health

```http
GET /operacao-autonoma/runtime-health
X-Correlation-Id: <opcional>
```

### Avaliar Remediação

```http
POST /operacao-autonoma/remediacoes/avaliar
X-Correlation-Id: <opcional>
Content-Type: application/json
```

Exemplo:

```json
{
  "codigo_acao": "AOP-ACT-004",
  "componente": "auto_remediacao_runtime",
  "tipo": "retry_governado",
  "motivo": "falha transitória simulada",
  "dry_run": true
}
```

## Componentes avaliados

| Componente | Objetivo |
|---|---|
| `api_fastapi` | Saúde básica da API e correlation_id |
| `observabilidade` | Logging, tracing e alertas |
| `auto_remediacao_runtime` | Executor governado e dry-run |
| `persistencia_auditoria` | Auditoria durável de decisões |

## Matriz de decisão

| Tipo de remediação | Decisão atual |
|---|---|
| `retry_governado` | Elegível, mas somente dry-run no P0.2 |
| `bloquear_deploy` | Elegível, mas somente dry-run no P0.2 |
| `registrar_incidente` | Elegível, mas somente dry-run no P0.2 |
| `observacao` | Elegível, mas somente dry-run no P0.2 |
| `restart_controlado` | Bloqueado por política |
| `rollback_seguro` | Bloqueado por política |

## Validação local

```bash
cd backend
python -m pytest tests/test_operacao_autonoma.py -v
```

## Critérios de aceite

| Critério | Esperado |
|---|---|
| Runtime health retorna 200 | Sim |
| Componentes principais aparecem no snapshot | Sim |
| `correlation_id` é propagado | Sim |
| Retry governado fica permitido em dry-run | Sim |
| Restart real fica bloqueado | Sim |
| Execução real fica bloqueada no P0.2 | Sim |
| Componente desconhecido fica bloqueado | Sim |
| PR continua draft até CI verde | Sim |

## Política de avanço de maturidade

Este incremento melhora a base operacional, mas ainda não permite declarar operação autônoma como avançada.

Para elevar maturidade, ainda faltam:

| Gap | Próximo incremento |
|---|---|
| Auditoria persistente | AOP P0.3 |
| Métricas reais | AOP P0.4 |
| Dashboard em tela | AOP P1 |
| Adapters reais de infraestrutura | AOP P1 |
| Rollback validado | AOP P1/P2 |
