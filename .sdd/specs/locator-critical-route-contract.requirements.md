# Locator PC24x7 — contrato de rotas críticas

## Objetivo
Impedir que um Quick Tunnel seja publicado enquanto ainda encaminha Teams/Cofre para um Nginx antigo.

## Requisitos
1. Manter health/readiness/build-info existentes.
2. Antes da publicação, testar sem credenciais `/v1/cofre/runtime/control-status`.
3. Antes da publicação, testar sem credenciais `/v1/teams-gateway/flow-bot/owners`.
4. Para essas superfícies autenticadas, somente HTTP 401/403 comprova chegada ao backend.
5. HTTP 404, 405, 2xx inesperado ou falha de rede tornam a URL inelegível.
6. Os probes não enviam JWT, webhook, token ou outro segredo.

## Critérios de aceite
- Teste preventivo comprova os dois probes.
- Uma instância com Nginx antigo não é incluída em `healthy_urls()`.
- O payload assinado registra o contrato de probes críticos.
- Após merge/reconciliação, execuções Teams no locator vigente não alternam para HTTP 405 durante a publicação.
