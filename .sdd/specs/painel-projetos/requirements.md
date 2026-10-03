# Painel de projetos no acesso público DEV

## Objetivo

Disponibilizar, dentro do ReqSys autenticado, um acesso explícito ao painel já
existente de projetos e integrações sem duplicar telas ou quebrar endereços
anteriores.

## Critérios de aceite

1. O menu **Meu trabalho** apresenta o item **Painel de projetos**.
2. A rota `/painel-projetos` exige o recurso `dashboard:read` e reutiliza a tela
   consolidada de projetos e integrações.
3. A rota legada `/painel-integracao` continua funcionando.
4. A tela identifica claramente o acompanhamento de Planner, integrações,
   notificações e evidências.
5. O frontend compila e os testes de rota e navegação são aprovados.
6. A publicação ocorre somente em DEV pelo pipeline canônico do GitHub Pages.

## Fora de escopo

- alteração de APIs, dados, papéis ou permissões;
- promoção automática para HML ou PROD;
- criação de uma segunda aplicação independente do ReqSys.
