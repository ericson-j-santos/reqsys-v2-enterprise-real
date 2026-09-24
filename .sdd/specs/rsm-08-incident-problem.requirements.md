# RSM-08 — INCIDENT -> PROBLEM + causa raiz auditável — Requisitos

Issue: #2055
Parent: #1782

## Requisito 1 — relação canônica
A correlação causal deve reutilizar `ServiceCase`. A origem deve ser `INCIDENT` e o destino deve ser `PROBLEM`; não criar grafo ou CMDB paralelo.

## Requisito 2 — invariantes fail-closed
Autorreferência, origem diferente de INCIDENT, destino diferente de PROBLEM e caso inexistente devem ser rejeitados antes de qualquer mutação persistente.

## Requisito 3 — identidade e idempotência
O vínculo é idempotente por `event_id` e pela identidade lógica `(incident_case_id, problem_case_id)`. Replay deve convergir sem duplicar relação nem evento. Reutilização do mesmo `event_id` para efeito divergente deve falhar.

## Requisito 4 — causa raiz auditável
Somente `PROBLEM` aceita causa raiz. Cada registro é append-only, contém texto objetivo, `correlation_id`, URI de evidência e SHA-256 da evidência. Replay do mesmo `event_id` e mesmo efeito não duplica registro nem evento.

## Requisito 5 — contrato de leitura
`GET /v1/service-cases/{incident_id}` deve expor o `PROBLEM` relacionado em `related_cases`, calculado no backend. `GET` do PROBLEM deve expor `root_causes`, sem duplicar regra causal no frontend.

## Requisito 6 — histórico
Criação do vínculo deve registrar `INCIDENT_LINKED_TO_PROBLEM` em `rsm_service_case_events`. Registro de causa raiz deve registrar `PROBLEM_ROOT_CAUSE_RECORDED` com a mesma evidência objetiva.

## Requisito 7 — E2E sem falso positivo
O E2E deve executar HTTP real contra FastAPI e PostgreSQL real no SHA exato, validar caso positivo, leitura SQL independente, replay por `event_id`, replay pela identidade lógica, controle negativo sem mutação e teste do teste com entrada deliberadamente inválida.

## Requisito 8 — escopo e segurança
Este incremento não executa merge, deploy, promoção, alteração de segredo, branch protection ou ação em HML/PROD. CMDB Lite / Service Graph permanece fora do escopo.

## Critérios de aceite
1. INCIDENT -> PROBLEM válido é persistido uma única vez.
2. Origem não INCIDENT e destino não PROBLEM são rejeitados sem mutação.
3. Autorreferência e caso inexistente são rejeitados.
4. Replay por `event_id` e identidade lógica não duplica vínculo/evento.
5. PROBLEM registra causa raiz com URI, SHA-256 e `correlation_id`.
6. INCIDENT expõe PROBLEM relacionado em leitura canônica.
7. PostgreSQL confirma relação, causa raiz, eventos e evidência.
8. Controle negativo preserva contagens/estado.
9. Teste do teste detecta SHA-256 inválido.
10. Evidência pertence ao HEAD atual e nenhuma evidência anterior é reutilizada.
