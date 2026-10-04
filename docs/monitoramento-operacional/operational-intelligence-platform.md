# Operational Intelligence Platform — ReqSys

## Objetivo

Consolidar inteligência operacional do runtime em superfícies já integradas ao ReqSys atual.

## Endpoints canônicos

- `GET /monitoramento-operacional/runtime/health`
- `POST /monitoramento-operacional/runtime/diagnostico`
- `GET /api/runtime/health`
- `GET /api/runtime/readiness`
- `GET /api/runtime/liveness`
- `GET /api/runtime/metrics`
- `GET /api/runtime/dashboard`

## Comportamento

O diagnóstico recebe sinais operacionais e produz:

- estado `SAUDAVEL`, `ATENCAO`, `DEGRADADO` ou `BLOQUEADO`;
- score determinístico entre 0 e 100;
- riscos explicáveis;
- recomendações operacionais;
- ação assistida com indicação explícita de necessidade de aprovação.

## Correlação

As operações relevantes usam o mecanismo canônico de `correlation_id`. Evidência sem vínculo de execução não deve ser tratada como prova de saúde ou conclusão.

## UI

A visualização canônica é `MonitoramentoOperacionalView.vue`. O Runtime Center histórico do PR #74 não é restaurado como segunda tela paralela.

## Persistência e resiliência

A reconciliação não aplica DDL SQL Server cru nem serviço genérico de retry. Persistência, fila e remediação devem evoluir pelas abstrações atuais do backend e pela governança de operações autônomas.

## Critérios de aceite

- endpoints do #74 permanecem registrados no FastAPI atual;
- diagnóstico e recomendação possuem testes críticos;
- correlação/telemetria canônicas permanecem disponíveis;
- nenhuma superfície histórica duplicada é reintroduzida;
- CI/SDD/governança ficam verdes no HEAD atual.
