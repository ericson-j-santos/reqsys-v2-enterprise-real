# Unified Operational Event Bus

## Objetivo

Unificar os eventos operacionais do ecossistema de CI/CD em um payload padronizado, roteável e auditável.

## Capacidades implementadas

- Payload operacional único.
- Padronização de evento operacional.
- Roteamento lógico para dashboard, histórico e alertas.
- Classificação por severidade.
- Política de ação governada.
- Preservação explícita de gates.
- Artifacts em JSON, Markdown e HTML.

## Esquema inicial

| Campo | Descrição |
|---|---|
| schema_version | Versão do payload |
| bus | Nome do barramento operacional |
| event_class | Classe operacional do evento |
| severity | Severidade do evento |
| routing_key | Chave lógica de roteamento |
| action_policy | Política operacional recomendada |
| governance_gate | Estado dos gates de governança |
| source | Origem GitHub Actions |
| git | Branch e commit |
| routing | Rotas lógicas habilitadas |

## Rotas operacionais

- Dashboard.
- Histórico.
- Alertas.
- Governança.

## Limites

- Não executa remediação automática.
- Não flexibiliza gates.
- Não altera runtime produtivo.
- Não cria backend persistente.

## Implementação

- Script canônico: `scripts/unified_operational_event_bus.py`
- Workflow: `.github/workflows/unified-operational-event-bus.yml`
- Artifact: `artifacts/unified-operational-event-bus/unified-operational-event.json`
- Consumidor downstream: `scripts/unified_operational_signal_consolidator.py`

## Encerramento do eixo operacional

Este incremento integra dashboards, histórico, alertas e event mesh via `Unified Operational Signal Consolidator`, consumido pelo Coordenador Principal e pelo Evidence Gate consolidado. Runbook: `docs/runbooks/consolidacao-operacional-p0.md`.
