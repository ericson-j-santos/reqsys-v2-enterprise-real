# Microsoft Graph Planner→Teams Watch

## Objetivo

Monitorar por GitHub Actions, sem custo adicional, mudanças oficiais do Microsoft Graph que possam destravar ou alterar o E2E Planner→Teams do ReqSys. O foco é `ChannelMessage.Read.*`, `ChannelMessage.Send*`, consentimento administrativo, resource-specific consent (RSC), mensagens de canal, change notifications e autenticação.

## Requisitos

1. Incorporar o monitor ao próprio `Scheduled Operational Watch`, preservando o cron existente de 4 horas; não criar novo workflow nem novo cron.
2. Consultar apenas Microsoft Learn e Microsoft Graph changelog oficiais.
3. Persistir baseline e deduplicação na issue #2165.
4. A primeira coleta deve semear baseline sem comentário de alerta.
5. Mudança relevante deve registrar fonte oficial, evidência SHA-256, efeito no bloqueio, risco e menor adaptação segura/idempotente.
6. Novo item relevante do changelog deve alertar uma única vez; replay não pode duplicar comentário.
7. Erro isolado de fonte deve gerar evidência degradada, nunca alerta material.
8. O monitor não concede permissões, não altera consentimento, tenant, segredo, ambiente ou deploy.
9. Actions externas devem usar SHA imutável.
10. Cada execução deve publicar artifact sanitizado.
11. O alerta deve exigir validação E2E em DEV com `correlation_id` único, caso negativo, caso positivo, readback independente e replay sem duplicidade.

## Critérios de aceite

- Testes contratuais provam ausência de novo workflow/cron, preservação do monitor operacional existente, fontes oficiais, issue durável, fail-closed para alertas e SHAs imutáveis.
- O workflow real sem mudança material semeia/atualiza estado sem comentário de alerta.
- Uma mudança material futura produz um único comentário na issue #2165.
- `READY_FOR_PR=passed` deve pertencer ao HEAD exato e a branch deve estar `behind_by=0` antes da abertura da PR.
