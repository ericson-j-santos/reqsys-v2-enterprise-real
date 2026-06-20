# Dashboard Operacional — Connection Broker

## Rota recomendada

`/monitoramento-operacional/conectores`

## Objetivo

Permitir que operação, arquitetura e produto acompanhem a saúde dos conectores usados pelo ReqSys e agentes integrados.

---

## Cards executivos

| Card | Regra | Severidade |
|---|---|---|
| Conectores críticos indisponíveis | `criticality = critical` e `status != ready` | Crítica |
| Autorizações expiradas | `status = expired` | Alta |
| Permissão insuficiente | `status = insufficient_permission` | Alta |
| Permissões pendentes | `status = missing_permission` | Média |
| Falhas nas últimas 24h | Eventos de autorização com erro | Média |
| Ações bloqueadas por gate | Produção bloqueada por segurança | Crítica |

---

## Tabela analítica

| Campo | Descrição |
|---|---|
| Ambiente | dev, homolog ou prod |
| Conector | Provedor integrado |
| Capability | Ação lógica exigida pelo agente |
| Status | ready, expired, missing_permission, insufficient_permission, unavailable, misconfigured |
| Última verificação | Data/hora do health-check |
| Última falha | Data/hora do último erro |
| Correlação | `correlation_id` |
| Ação sugerida | Conectar, renovar, ajustar permissão, corrigir configuração |

---

## Drill-down

Ao clicar em um card ou linha, abrir painel filtrado com:

- eventos de autorização;
- ações bloqueadas;
- perfis de permissão solicitados;
- histórico de status;
- ambiente afetado;
- usuário solicitante;
- PR/issue/release associado;
- evidências de auditoria.

---

## Alertas mínimos

| Alerta | Condição |
|---|---|
| `CONNECTOR_CRITICAL_DOWN` | conector crítico fora por mais de 5 minutos |
| `AUTHORIZATION_EXPIRING_SOON` | autorização próxima de expirar |
| `PROD_GATE_BLOCKED` | produção bloqueada por gate de conector |
| `PERMISSION_DRIFT_DETECTED` | permissão real diferente do registry |
| `SECRET_LEAK_SUSPECTED` | segredo detectado em log |

---

## Métricas recomendadas

- `connector_health_status_total`
- `connector_permission_requests_total`
- `connector_permission_denied_total`
- `connector_resume_success_total`
- `connector_resume_failure_total`
- `connector_gate_block_total`
- `connector_permission_drift_total`

---

## Definition of Done

- Dashboard acessível por ambiente.
- Cards com drill-down.
- Health-check com `correlation_id`.
- Eventos auditáveis.
- Gates de produção configurados.
- Testes unitários e E2E cobrindo autorização, falha e retomada.
