# Runtime Contract Governance — Pareto Policy

Versão: `0.1.0`  
Escopo: ReqSys Runtime, OpenAPI, DTOs, artifacts operacionais e integrações Power Platform.

## Problema

O crescimento incremental do ReqSys aumenta o risco de drift entre:

- endpoints reais;
- OpenAPI versionado;
- DTOs usados por frontend, automações e Power Platform;
- artifacts JSON consumidos pelos dashboards;
- evidências geradas por CI/CD.

A política Pareto prioriza o menor conjunto de controles que evita a maior parte das regressões.

## Controles obrigatórios

| Controle | Regra |
|---|---|
| Schema version | Todo JSON operacional deve conter `schema_version` |
| Generated at | Toda evidência gerada deve conter timestamp explícito |
| Source path | Todo dashboard deve apontar para fonte versionada |
| Contract owner | Contrato crítico deve possuir owner técnico ou frente responsável |
| Breaking change | Mudança incompatível exige versionamento semântico |
| DTO drift | Divergência entre OpenAPI e DTO deve bloquear promoção |
| Runtime event | Evento runtime deve conter `correlation_id` |

## Política de versionamento

| Alteração | Versão |
|---|---|
| Campo novo opcional | minor |
| Campo obrigatório novo | major |
| Remoção de campo | major |
| Correção documental sem impacto de contrato | patch |
| Novo artifact operacional consumido por dashboard | minor |

## Gate recomendado

O gate deve falhar quando:

1. JSON operacional não tiver `schema_version`;
2. contrato OpenAPI não tiver versão;
3. artifact crítico não estiver referenciado em índice canônico;
4. `correlation_id` estiver ausente em contrato de evento runtime;
5. alteração de contrato não estiver refletida em documentação viva.

## Matriz de rastreabilidade mínima

| Contrato | Consumidor | Evidência esperada |
|---|---|---|
| OpenAPI Runtime | Frontend/API clients/Power Automate | `openapi-governance-index.json` |
| Health Dashboard | Ops Dashboard | `docs/ops-dashboard/data/health.json` |
| PR Recovery | CI/Ops | `artifacts/pr-auto-recovery/pr-auto-recovery.json` |
| Observability | Operação/Debug | `observability-correlation-report.json` |
| Power Platform Bridge | Power Automate/Copilot | OpenAPI connector + payloads mockados |

## Recomendação de implementação

A evolução deve ser incremental:

1. publicar política e índice;
2. adicionar validação read-only;
3. ligar ao CI;
4. renderizar no Ops Dashboard;
5. aplicar bloqueio estrito somente após duas execuções verdes consecutivas.
