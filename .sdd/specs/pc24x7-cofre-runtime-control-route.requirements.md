# PC24x7 — rota pública de controle do Cofre DEV

## Objetivo
Permitir que o Cofre Runtime Evidence Gate alcance os endpoints autenticados `/v1/cofre/runtime/control-status` e `/v1/cofre/runtime/restart` no backend, em vez de cair no frontend.

## Requisitos
1. Expor somente `/v1/cofre/runtime/`.
2. Preservar o prefixo `/v1`.
3. Manter `limit_req zone=cofre`.
4. Não expor genericamente `/v1/cofre/` nem `/v1/`.
5. Não alterar autenticação JWT ou segredos.

## Critérios de aceite
- Teste preventivo do Nginx passa.
- `GET /v1/cofre/runtime/control-status` alcança a API e retorna envelope JSON autenticado.
- A rota não cai no frontend.
- Após merge/reconciliação, o Cofre Runtime Evidence Gate avança além do preflight.
