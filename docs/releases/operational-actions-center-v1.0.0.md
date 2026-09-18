# Release Note — Operational Actions Center v1.0.0

## Resumo

Implementa o primeiro incremento do ReqSys Operational Actions Center para capturar, normalizar e classificar execuções do GitHub Actions.

## Entregas

- Serviço `actions_runtime_monitor`.
- API `actions_runtime_center`.
- Classificação operacional de workflow runs.
- Score de saúde.
- Endpoint de consulta GitHub Actions API.
- Endpoint de webhook GitHub para eventos `workflow_run`.
- Testes unitários.
- ADR-025.
- Runbook operacional.

## Benefício

Reduz dependência de links manuais de run e cria base para analytics operacional, self-healing CI e Runtime Center.

## Critério de aceite

- Testes backend verdes.
- Endpoints registrados na API.
- Classificador cobre sucesso, falha e execução em andamento.
- Documentação operacional disponível.

## Próximo incremento recomendado

Adicionar persistência de snapshots e painel operacional no frontend.
