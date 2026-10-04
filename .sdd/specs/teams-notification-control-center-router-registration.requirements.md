# Teams Notification Control Center — registro do router

## Objetivo

Garantir que as rotas já implementadas do Control Center de notificações Teams sejam registradas no FastAPI sob `/v1/teams-gateway/notificacoes`, evitando falso 404 antes da autenticação.

## Requisitos

1. `backend/app/api/notificacoes.py` continua sendo a implementação canônica do Control Center.
2. O app principal deve importar o módulo `notificacoes`.
3. O router deve ser incluído com prefixo `/v1/teams-gateway`.
4. Requisição sem autenticação para endpoints protegidos deve responder 401/403, nunca 404.
5. O ajuste não altera credenciais, destinatários, envio externo ou produção.
6. Teste de regressão deve provar que dashboard, fila, DLQ e logs estão registrados.
7. O smoke de runtime continua sendo a evidência ponta a ponta após integração/publicação aplicável.

## Critérios de aceite

- teste explícito de registro das quatro rotas;
- testes de Teams notifications verdes;
- Pre-PR Readiness verde no HEAD exato e base atual;
- smoke posterior deixa de falhar por 404; autenticação permanece uma etapa separada.
