# Plano de Implementação — PR-001B Shell Visual e Navegação

## Objetivo

Implementar o shell visual mínimo do ReqSys para usuário final, seguindo o ADR `ADR-USER-FINAL-SHELL-001` e o contrato `docs/product/user-final-shell-contract.json`.

## Escopo do PR-001B

- Criar layout base responsivo.
- Criar menu principal com rotas mínimas.
- Exibir ambiente atual.
- Criar estados visuais padrão.
- Criar tela inicial operacional.
- Adicionar cards principais com drill-down preparado.

## Fora do escopo

- RBAC completo.
- Persistência real de requisitos.
- Analytics avançado.
- Migração estrutural grande do frontend.
- Refatoração ampla de rotas existentes.

## Rotas mínimas

| Rota | Tela | Critério |
|---|---|---|
| `/home` | Início operacional | Deve orientar o usuário sobre próximos passos. |
| `/workspace` | Workspace | Pode iniciar com cards e placeholders governados. |
| `/requisitos` | Catálogo | Pode iniciar com estado vazio/placeholder. |
| `/analytics` | Analytics | Pode iniciar como visão inicial com cards. |
| `/governanca` | Governança | Deve mostrar gates/evidências em alto nível. |
| `/ajuda` | Ajuda | Deve orientar uso inicial. |

## Componentes recomendados

| Componente | Responsabilidade |
|---|---|
| `UserFinalShell` | Estrutura geral de layout. |
| `EnvironmentBadge` | Exibir DEV/HML/PRD. |
| `MainNavigation` | Menu principal. |
| `OperationalCard` | Card clicável com status e drill-down. |
| `UiState` | Estado loading/empty/error/success/unauthorized. |
| `TechnicalFooter` | Versão, ambiente e correlation_id. |

## Regras de implementação

- Não acoplar texto visual diretamente a regra crítica; preferir contrato/configuração.
- Não expor dado sensível ou segredo operacional.
- Tratar ausência de dados como estado `empty`, não como erro.
- Erro técnico deve ser traduzido para mensagem segura ao usuário.
- Layout deve funcionar em desktop e mobile.

## Validação mínima

- Build do frontend verde.
- CI geral verde.
- Nenhuma rota mínima quebrando.
- Estados visuais representados.
- Ambiente visível.
- Sem vazamento de dado sensível ou segredo operacional.

## Status de execução

| Item | Status | Evidência |
|---|---|---|
| View visual do shell | Implementado | `frontend/src/views/UserFinalShellView.vue` |
| Rotas `/home`, `/workspace`, `/analytics`, `/ajuda` | Implementado | `frontend/src/router/index.js` |
| Cards com drill-down preparado | Implementado | `UserFinalShellView.vue` |
| Estados visuais padrão | Implementado | `UserFinalShellView.vue` |
| Ambiente visível | Implementado | `UserFinalShellView.vue` |
| Menu lateral global | Pendente | Alteração integral do layout foi bloqueada pela ferramenta nesta execução |
| CI | Pendente | Aguardar GitHub Actions do novo head |

## Critério de pronto

O PR-001B estará pronto quando o usuário final conseguir acessar a aplicação, entender onde está, navegar entre áreas principais e identificar o próximo passo operacional sem depender de documentação externa.
