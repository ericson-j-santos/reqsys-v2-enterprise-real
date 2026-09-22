# Release notes — PR #145 clean replacement

## Resumo

Cria substituto limpo para o PR #145, baseado na `main` atual, para remover conflito de merge e preservar o escopo aprovado de substituição do CodeRabbit.

## Entregas

- CodeRabbit neutralizado no repositório.
- Workflow próprio `PR Quality Review`.
- Script determinístico de análise de PR.
- ADR e runbook operacional.
- Ajuste do `PR CI Watch` para não bloquear por estados pendentes ou warnings informativos.
- Testes do watcher e do novo review determinístico.

## Observação

O PR #145 original ficou não mergeável por conflito de ancestralidade com mudanças recentes na `main`. Esta branch substituta evita merge manual conflitado.
