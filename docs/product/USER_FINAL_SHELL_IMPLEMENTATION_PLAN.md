# Plano de Implementação — Shell do Usuário Final

## Objetivo

Disponibilizar uma experiência inicial navegável para usuário final do ReqSys sem alterar deploy, produção ou gates de segurança.

## Entregas

- View `frontend/src/views/UserFinalShellView.vue`.
- Rotas protegidas `/home`, `/workspace`, `/analytics` e `/ajuda`.
- Contrato versionado em `docs/product/user-final-shell-contract.json`.
- ADR de arquitetura do shell.
- Changelog do incremento.

## Fora do escopo

- RBAC completo.
- Persistência real de requisitos.
- Analytics avançado.
- Alteração ampla do menu lateral global.
- Promoção para produção.

## Critérios de aceite

- Build frontend verde.
- CI geral verde.
- Rotas mínimas não quebram.
- Estados visuais padrão representados.
- Ambiente visível.
- Sem vazamento de dados sensíveis.

## Próximo incremento

Expor as rotas no menu lateral global em PR pequeno e independente.
