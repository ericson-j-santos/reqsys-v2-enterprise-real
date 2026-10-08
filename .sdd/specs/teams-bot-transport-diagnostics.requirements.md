# Diagnóstico seguro do transporte Teams Bot

## Contexto

O E2E físico DEV alcança o Teams Gateway, mas uma exceção sem status HTTP é reduzida a `provider_delivery_failed`. A correção causal exige preservar a classe operacional da falha sem transportar texto, URL, credencial ou corpo devolvido pelo provedor.

## Requisitos

1. O gateway deve converter falhas de circuito, conexão, timeout, token e resposta inválida em códigos estáveis e não sensíveis.
2. Exceções não reconhecidas devem expor somente o nome normalizado da classe, nunca `str(exc)` na fila ou evidência.
3. Respostas HTTP do provedor continuam representadas exclusivamente pelo status numérico.
4. O E2E deve propagar somente categorias allowlisted ou códigos estruturados com prefixo `provider_`.
5. O fluxo permanece fail-closed enquanto `teams_delivered` não for verdadeiro.
6. O workflow pode diagnosticar a `main` a partir de uma ref de correção somente quando solicitado explicitamente e após resolver e validar o SHA remoto vigente de `main`.
7. O runtime DEV observado deve reportar exatamente esse SHA antes de qualquer mutação E2E.
8. Nenhum segredo, endpoint privado ou corpo de resposta pode aparecer na evidência publicada.
9. Para o Azure Bot `SingleTenant`, o token do Connector deve ser solicitado no tenant configurado em `TEAMS_BOT_APP_TENANT_ID`; o tenant legado `botframework.com` não pode ser usado como autoridade OAuth.

10. Quando o envio direto resolver de forma inequívoca a única `conversationReference`, preservar o destinatário na conversa antes da chamada ao Bot Framework; o fallback da fila deve reutilizá-lo mesmo após falha externa.
11. Com referência ambígua ou ausente, não inventar destinatário, não efetuar envio e manter o fluxo fail-closed.
12. Antes do transporte, a `conversationReference` deve estar vinculada ao Bot App ID e tenant atualmente configurados; campos ausentes ou divergentes bloqueiam o envio com código sanitizado.
13. A evidência E2E pode propagar códigos `conversation_reference_*`, mas nunca os identificadores observados ou esperados.
14. Exceções inesperadas entre fila e gateway devem persistir somente `provider_exception_<classe>`, sem `str(exc)`.

## Critérios de aceite

- testes focados do gateway e do E2E aprovados;
- contrato SDD aprovado no SHA do PR;
- diagnóstico físico identifica uma categoria estruturada após integração e reconciliação;
- entrega real ao Teams é a única condição que aprova o E2E final;
- nenhum valor sensível aparece em logs ou artifacts.
- teste regressivo confirma autoridade OAuth tenant-specific e preserva o scope `https://api.botframework.com/.default`.
- teste regressivo confirma bloqueio pré-transporte para referência ausente ou pertencente a outra identidade Bot.
