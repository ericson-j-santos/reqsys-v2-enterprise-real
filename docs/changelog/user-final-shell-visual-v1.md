# Changelog — User Final Shell Visual v1

## Implementado

- Nova view `frontend/src/views/UserFinalShellView.vue`.
- Rotas protegidas:
  - `/home`
  - `/workspace`
  - `/analytics`
  - `/ajuda`
- Navegação interna do shell.
- Hero operacional com ambiente visível.
- Cards navegáveis com preparação para drill-down.
- Estados visuais padrão.
- Rodapé técnico com versão, ambiente e `correlation_id` local seguro.

## Fora do escopo

- Deploy.
- Promoção para produção.
- RBAC completo.
- Persistência real de requisitos.

## Correção operacional

Este incremento substitui o PR #129, que ficou não mergeável após avanço da `main`. O substituto foi recriado em branch limpa e não carrega alterações antigas de workflow que não pertencem diretamente ao shell de usuário final.
