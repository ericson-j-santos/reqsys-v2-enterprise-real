# Estatísticas v2 — Backend Real

Data: 2026-06-22
Branch: `feature/estatisticas-tab-v2`

## Objetivo

Evoluir a aba Estatísticas da v1 frontend/internal-first para uma v2 com backend real, endpoint versionado e indicadores calculados a partir do banco operacional do ReqSys.

## Entregas

- Novo endpoint `GET /v1/estatisticas`.
- Novo serviço backend `backend/app/services/estatisticas.py`.
- Novo router `backend/app/api/estatisticas.py`.
- Registro do router em `backend/app/main.py`.
- Frontend `frontend/src/services/estatisticas.js` passa a consumir `/v1/estatisticas`.
- Fallback local permanece, mas marcado como `frontend-runtime-fallback`.
- Testes backend para endpoint, schema, correlation_id, fonte/fórmula e fonte externa.
- Testes frontend para carga via API e fallback controlado.

## Indicadores reais iniciais

| Indicador | Origem | Observação |
|---|---|---|
| Total de requisitos | `requisitos` | `count(requisitos.id)` |
| Requisitos com BDD | `requisitos.titulo + descricao` | Marcadores BDD/Gherkin |
| Requisitos com lacunas | `requisitos.titulo + descricao` | Marcadores de indefinição |
| Requisitos concluídos | `requisitos.status` | Status finalizados |
| Guard rails de produção | `Settings.validate_production_gates` | Evidência de gate versionado |
| Fontes externas válidas | registry pendente | Mantido como `nao_medido` |

## Decisão de governança

Fontes externas continuam como `nao_medido` até existir registry/conector autorizado. A v2 prioriza dados internos reais antes de expandir dados externos.

## Próximo incremento recomendado

Implementar histórico temporal e registry de fontes externas autorizadas com TTL real, cache e quality gate contra mock externo em produção.
