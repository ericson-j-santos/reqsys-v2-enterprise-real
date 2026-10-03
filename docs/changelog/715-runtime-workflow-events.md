# Changelog — Issue #715 — Runtime Workflow Events

## Tipo

Complemento incremental do Runtime Core.

## Contexto

Após a criação do `RuntimeEventBus` e do `RuntimeEventEnvelope`, o próximo passo seguro foi criar um adaptador específico para eventos do workflow de requisitos, sem alterar imediatamente contratos públicos da API.

## Alterações

- Adicionado `backend/app/services/requisitos_runtime_events.py`.
- Adicionado teste `backend/tests/test_requisitos_runtime_events.py`.
- Criada função `publicar_requisito_transicionado` para padronizar o evento `REQUISITO_TRANSICIONADO`.
- Criada função `resumir_runtime_requisitos` para inspeção operacional mínima do barramento.

## Decisão arquitetural

A publicação foi isolada em um serviço dedicado para evitar acoplamento direto entre o endpoint de requisitos e a implementação do Runtime Core. Isso permite evoluir o barramento para outbox SQL, broker externo ou fila corporativa sem alterar os contratos de API.

## Critérios atendidos

- [x] Mantém contratos existentes preservados.
- [x] Padroniza evento de transição de requisito.
- [x] Preserva `correlation_id`.
- [x] Não bloqueia fluxo quando não há handler registrado.
- [x] Adiciona cobertura automatizada.

## Próximo incremento recomendado

Acoplar `publicar_requisito_transicionado` dentro do endpoint `POST /api/requisitos/{identificador}/transicao`, logo após o registro de auditoria, retornando evidência técnica opcional no payload de resposta sem quebrar consumidores existentes.
