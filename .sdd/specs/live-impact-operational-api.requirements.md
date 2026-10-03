# Live Impact Operational API — Requisitos

## Objetivo

Disponibilizar a análise de impacto viva como fluxo operacional autenticado do ReqSys, partindo do requisito persistido e do grafo de rastreabilidade atual, sem usar o dataset histórico como fonte de decisão operacional.

## Requisitos

1. Expor uma entrada operacional autenticada para análise de impacto por requisito.
2. Construir o `functional_traceability_graph` a partir das fontes canônicas existentes e passá-lo a `analyze_live_change()`.
3. Não carregar o dataset histórico nem exigir `ground_truth` no fluxo operacional.
4. Manter a operação read-only: nenhuma chamada deve criar, alterar ou duplicar Requisito, AgileWorkItem, VinculoGit ou ChangeEvidenceRecord.
5. Excluir evidência com `evidence_status=rejected` do conjunto operacional padrão.
6. Rejeitar explicitamente seeds que não pertençam à rastreabilidade viva.
7. Preservar o `correlation_id` da requisição até a análise.
8. Manter IA opcional e desabilitada por padrão. Quando habilitada, usar o AI Provider Router existente e manter o guardrail de seleção somente entre candidatos recuperados.
9. Retornar explicitamente que a fonte é o grafo vivo e que o dataset histórico não foi usado.
10. Não criar banco, migração, Neo4j, deploy, segredo ou infraestrutura adicional.

## Contrato HTTP

`POST /v1/rastreabilidade/requisitos/{requisito_id}/impacto`

Entrada mínima:
- `change_id`
- `query`

Controles opcionais:
- `seed_artifact_ids`
- `graph_depth`
- `semantic_top_k`
- `llm_enabled`
- `provider`
- `model`

## Critérios de aceite

1. Caso positivo API → banco de teste → TraceabilityGraphService → analyze_live_change retorna estratégias graph, semantic e hybrid.
2. Todos os candidatos retornados pertencem aos nós rastreáveis do grafo vivo.
3. Replay da mesma entrada produz o mesmo `data` e não causa mutação ou duplicidade.
4. SHA runtime divergente continua visível no grafo, mas seus nós dependentes de evidência rejeitada não são candidatos operacionais.
5. Seed inexistente falha com 422.
6. Requisito inexistente falha com 404.
7. Requisição não autenticada falha com 401.
8. Pre-PR Readiness deve aprovar o HEAD exato antes da abertura da PR.
