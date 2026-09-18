# Planner → Teams DEV — renovação automática da autorização Microsoft

## Requisito 1 — não perder o run por expiração
O aceite deve reutilizar `msal_device_code_complete.mjs` e renovar automaticamente o `user_code` quando o código expirar, sem exigir novo disparo do workflow.

## Requisito 2 — reduzir interação manual
A primeira instrução segura deve aparecer diretamente no Summary do GitHub Actions. Códigos renovados devem aparecer no mesmo run por `::notice` e Summary.

## Requisito 3 — segurança
Somente `verification_uri`, `user_code`, tentativa e tempo de validade podem ser publicados. O `device_code` privado, tokens e segredos permanecem somente no runner.

## Requisito 4 — limite operacional
A janela total de espera é limitada a 50 minutos e o job tem orçamento de 70 minutos para autorização + E2E.

## Critérios de aceite
1. O workflow inclui `scripts/msal_device_code_complete.mjs`.
2. Código expirado é renovado no mesmo run.
3. O usuário não precisa solicitar manualmente ao ChatGPT um novo código.
4. O E2E só prossegue após a sessão MSAL efêmera ser atualizada com sucesso.
5. MFA/consentimento Microsoft continuam sendo decisões humanas quando exigidos pelo Entra ID.
