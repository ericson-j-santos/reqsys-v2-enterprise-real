# Changelog — User Final Shell Visual v1

## Contexto

Incremento complementar ao PR-001A de contrato do shell do usuário final.

## Implementado

- Nova view `frontend/src/views/UserFinalShellView.vue`.
- Rotas mínimas protegidas:
  - `/home`;
  - `/workspace`;
  - `/analytics`;
  - `/ajuda`.
- Navegação interna do shell entre Início, Workspace, Analytics e Ajuda.
- Hero operacional com ambiente visível.
- Cards navegáveis com preparação para drill-down.
- Estados visuais padrão: `loading`, `empty`, `error`, `success` e `unauthorized`.
- Rodapé técnico com versão, ambiente e `correlation_id` local seguro.

## Fora do escopo

- RBAC completo.
- Persistência real de requisitos.
- Deploy.
- Promoção para produção.

## Validação esperada

- Build frontend.
- CI geral.
- Teste responsivo existente.
- Validação manual das rotas mínimas em ambiente dev/test.

## Risco residual

A navegação interna do shell está implementada. A exposição no menu lateral global segue como pendência técnica separada porque a tentativa de atualização integral do layout foi bloqueada pela ferramenta durante esta execução. O próximo incremento deve aplicar essa alteração de menu em patch menor ou via checkout local/CLI.

## Status de CI

- Checks rápidos e governança do head atual: verdes.
- CI principal do head atual: aguardando execução.
