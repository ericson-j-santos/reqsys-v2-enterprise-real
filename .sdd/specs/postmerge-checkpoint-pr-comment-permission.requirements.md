# Requisitos — permissão do checkpoint pós-merge

## Problema

O job `Checkpoint e avanço da fila recuperada` materializa a evidência pós-merge e grava um comentário na PR integrada. No run `37922432634`, o token tinha `issues: write`, mas apenas `pull-requests: read`; a API rejeitou `POST /issues/2514/comments` com HTTP 403 (`Resource not accessible by integration`).

## Requisitos funcionais

1. O Actions Dispatcher deve manter `actions: write`, necessário para avançar a fila.
2. O workflow deve manter `issues: write` para comentários em issues.
3. O workflow deve conceder `pull-requests: write` para criar ou atualizar o checkpoint quando o alvo for uma PR.
4. Nenhum segredo, permissão administrativa do repositório ou ambiente de produção deve ser alterado.

## Critérios de aceite

- O contrato automatizado deve rejeitar regressão de `pull-requests: write` para `read`.
- Os testes focados do Actions Dispatcher devem passar.
- A mudança deve permanecer limitada ao workflow, contrato regressivo e esta especificação.
