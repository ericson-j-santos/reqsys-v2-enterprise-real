# Controle de Mudança — Aba Estatísticas v1

## Mudança

Adicionar capacidade de estatísticas próprias e externas auditáveis ao ReqSys.

## Escopo técnico

- Frontend Vue/Vuetify.
- Router.
- Menu lateral.
- Serviço de indicadores.
- Testes unitários.
- Documentação governada.

## Ambientes

| Ambiente | Status |
|---|---|
| Desenvolvimento | Implementado em branch |
| Homologação | Pendente CI/PR |
| Produção | Não aprovado |

## Plano de rollback

- Reverter PR completo caso build/testes falhem sem correção objetiva.
- Em caso de falha somente de navegação, remover rota/menu mantendo documentação e serviço para correção posterior.
- Em caso de falha de teste, corrigir contrato antes de alterar UI.

## Aprovação

Pendente CI verde e revisão.
