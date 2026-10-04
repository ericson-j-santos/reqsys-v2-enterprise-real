# Reconciliação do PR #89 — roteamento de CI e Codex Online

## Estado observado

O objetivo histórico do PR #89 já foi incorporado e evoluído na `main`.

A implementação atual substituiu o filtro antigo por uma arquitetura mais robusta:

- `workflow_dispatch` continua disponível;
- `CI Admission Controller` bloqueia trabalho caro quando o HEAD não está pronto;
- `CI Router (paths + Pareto)` classifica backend, frontend, docs, Codex e workflows;
- backend e frontend executam somente quando o escopo atual exige;
- E2E é roteado por paths e contratos de risco;
- Codex Online mantém workflow próprio de validação/publicação em GitHub Pages;
- o README atual preserva o uso local VS Code + Ollama e a publicação Pages.

## Decisão

Não restaurar o `dorny/paths-filter` e o `paths-ignore` históricos do PR #89, pois isso substituiria a governança atual por uma versão menos completa e poderia mascarar alterações que hoje exigem CI completo.

## Evidência de preservação

O trabalho do PR #89 não foi descartado: seu objetivo funcional — evitar backend coverage desnecessário e suportar disparo manual/publicação do Codex — está presente na arquitetura canônica atual, com controles adicionais.

## Critério de conclusão

- branch sincronizada com a `main` vigente;
- nenhum workflow atual substituído por versão histórica;
- `behind_by=0`;
- PR sem conflitos;
- gates do HEAD reconciliado verdes.
