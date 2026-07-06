# Changelog — Issue #715 — Runtime Core acoplado ao workflow de requisitos

## Tipo

Complemento P0 do Runtime Core.

## Contexto

Os PRs anteriores criaram o `RuntimeEventBus`, o `RuntimeEventEnvelope` e o adaptador de publicação do evento `REQUISITO_TRANSICIONADO`. Este incremento conecta essa fundação ao endpoint real de transição de requisitos.

## Alterações

- Adicionado `backend/app/api/requisitos_runtime_transition.py`.
- Atualizado `backend/app/api/__init__.py` para carregar a rota runtime no bootstrap da API.
- Adicionado `backend/tests/test_requisitos_runtime_transition_route.py`.

## Decisão técnica

Foi criado um router shim carregado antes do registro final dos routers em `app.main`. Ele adiciona uma rota com o mesmo path do endpoint legado `POST /api/requisitos/{identificador}/transicao`, posicionada antes da rota original em `requisitos.api_router`.

Essa abordagem reduz risco porque:

- preserva a rota legada como fallback estrutural;
- evita reescrever o módulo grande de requisitos neste incremento;
- mantém o contrato público `reqsys-requisito-transicao-v1`;
- adiciona somente o campo compatível `runtime_event` na resposta;
- publica o evento governado no Runtime Core após auditoria.

## Critérios atendidos

- [x] Acopla `REQUISITO_TRANSICIONADO` ao endpoint real de transição.
- [x] Mantém contrato público existente.
- [x] Preserva `correlation_id`.
- [x] Mantém rota legada como fallback.
- [x] Adiciona teste para ordem e preservação das rotas.

## Próximo incremento recomendado

Adicionar endpoint de inspeção operacional do Runtime Core para requisitos, expondo `resumir_runtime_requisitos()` em rota GET controlada para monitoramento do event bus, eventos pendentes e DLQ.
