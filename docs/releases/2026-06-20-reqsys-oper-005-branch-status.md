# 2026-06-20 — REQSYS-OPER-005 — Status da branch

## Estado

Branch criada para o incremento `/monitoramento-operacional`.

## Arquivos alterados

- Backend API.
- Registro do router no backend.
- Testes backend.
- View frontend.
- Registro de rota frontend.
- Documentação de API.
- ADR.
- Release notes.

## Observação operacional

A comparação inicial indicou branch `diverged`, pois a `main` avançou após criação da branch. Antes de qualquer merge, a branch deve ser atualizada/rebaseada contra `main` e validada por CI.

## Regra de bloqueio

Este incremento não pode ser considerado pronto enquanto:

- branch estiver atrasada em relação à `main`;
- CI não estiver verde;
- PR estiver em draft;
- não houver evidência de execução dos testes.

Refs #46
