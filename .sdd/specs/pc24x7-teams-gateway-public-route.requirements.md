# PC24x7 — rota pública do Teams Messaging Gateway

## Objetivo

Corrigir o HTTP 405 observado no E2E GitHub → PC24x7 → Teams. O FastAPI expõe POST em `/v1/teams-gateway/*`, mas o Nginx público DEV encaminhava apenas `/api/*`; a requisição `/v1/teams-gateway/*` caía no frontend.

## Requisitos

1. Encaminhar somente `/v1/teams-gateway/` para `api:8000`.
2. Preservar integralmente o prefixo `/v1`.
3. Não criar proxy genérico para `/v1/`.
4. Manter as demais superfícies públicas inalteradas.
5. Não alterar segredos nem aceitar HTTP 405 como sucesso.

## Critérios de aceite

- O teste `tests/test_pc24x7_teams_gateway_nginx_route.py` passa.
- O bloco Nginx usa `location ^~ /v1/teams-gateway/`.
- O `proxy_pass` não contém URI final que remova o prefixo.
- Não existe exposição genérica de `/v1/`.
- Após merge/reconciliação do runtime, uma chamada real do Teams Commit Notification alcança o backend e deve confirmar entrega para concluir a correção.
