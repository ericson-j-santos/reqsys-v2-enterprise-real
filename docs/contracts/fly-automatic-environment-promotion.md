# Fly Automatic Environment Promotion

> Estado atual: **legado manual-only**. O nome do workflow foi preservado por compatibilidade histórica. Fly não é permitido em DEV.

## Objetivo

Permitir, somente por `workflow_dispatch`, a validação de DEV no PC24x7 e a promoção legada de HML/PROD em Fly quando explicitamente solicitada e autorizada.

## Gatilhos

- somente `workflow_dispatch`;
- não existe `schedule`;
- não existe `workflow_run` automático;
- SHA diferente da `main` corrente é recusado antes de qualquer promoção.

## Fluxo

1. Resolver o SHA atual da `main` e rejeitar SHA obsoleto.
2. Validar DEV exclusivamente pelo locator assinado PC24x7, incluindo health e same-SHA.
3. Somente após DEV verde, capturar/promover HML no Fly legado.
4. Consultar o BACEN Production Hard Gate.
5. Capturar/promover PROD somente quando HML estiver verde e o gate BACEN autorizar.
6. Publicar relatório imutável da cadeia.

## Guard rails

- Fly não é permitido em DEV e não existe fallback por `REQSYS_DEV_RUNTIME_PROVIDER`;
- execução automática de Fly por horário ou pós-merge é proibida;
- fail-closed para locator ausente, runtime PC24x7 indisponível, SHA divergente, artifact ausente, JSON inválido, command failure, secret ausente ou check degradado;
- nenhuma persistência de valores de secrets;
- nenhum bypass do ambiente GitHub ou do BACEN Production Hard Gate;
- somente o SHA atual da `main` pode ser promovido;
- artifacts de ambiente retidos por 90 dias e resumo da cadeia por 365 dias.

## Rollback

O workflow não executa rollback destrutivo automático. Uma falha interrompe a cadeia no estágio atual e preserva os artifacts para diagnóstico. O rollback operacional deve reutilizar um SHA anterior autorizado por um fluxo específico de rollback, sujeito aos mesmos gates.
