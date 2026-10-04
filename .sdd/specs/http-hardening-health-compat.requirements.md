# Hardening HTTP e compatibilidade de health checks da API

## Objetivo

Recuperar o comportamento funcional perdido do PR #25 sem regredir a arquitetura atual do ReqSys, mantendo os contratos de runtime existentes e adicionando somente os aliases operacionais e o hardening HTTP necessários.

## Requisitos

1. `GET /health/live` deve responder HTTP 200 com estado de liveness e não pode depender da disponibilidade do banco.
2. `GET /health/ready` deve verificar o banco no momento da requisição, responder HTTP 200 quando disponível e falhar fechado com HTTP 503 quando indisponível.
3. O middleware deve aceitar `X-Correlation-ID` ou `X-Request-ID`, preservar o identificador e devolvê-lo nos headers `X-Correlation-Id` e `X-Request-ID`.
4. Toda resposta processada pelo middleware deve incluir `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin` e `Permissions-Policy` restritiva.
5. `Strict-Transport-Security` deve ser emitido somente para requisições HTTPS.
6. Eventos HTTP 401/403 devem registrar `correlation_id` sem expor credenciais, tokens ou detalhes sensíveis.
7. Os endpoints canônicos `/api/runtime/readiness` e `/api/runtime/liveness` existentes não devem ser alterados pelo incremento.
8. A repetição da mesma requisição com o mesmo correlation ID não pode gerar identificador diferente na resposta.

## Critérios de aceite

- `backend/tests/test_http_hardening.py` aprova liveness, readiness positiva, readiness negativa, propagação de correlação, repetição e comportamento HTTPS/HSTS.
- `backend/tests/test_main_critical_paths.py` permanece verde, comprovando ausência de regressão nos contratos atuais de runtime.
- Ruff e compilação Python dos arquivos alterados permanecem verdes.
- O Security Changed Diff permanece verde.
- O Pre-PR Readiness aprova o HEAD exato com `behind_by=0`.
- Nenhuma mudança de deploy, segredo, ambiente ou permissão é introduzida.
