# Requisitos — Higiene de workflow_run pós-merge

## Objetivo

Eliminar falhas vermelhas falsas e fan-out desnecessário após merge na branch padrão, sem enfraquecer os gates que protegem Pull Requests abertos.

## Classificação

`gap_fix`.

## Evidência de causa raiz

No merge da PR #1957 para `main`, workflows orientados a PR receberam eventos `workflow_run` com `head_branch=main` e associação residual ao PR já mergeado:

- PR Evidence Gate executou novamente e falhou;
- PR CI Watch entrou no caminho de remediação e falhou;
- Ollama CI Triage abriu múltiplas execuções auxiliares e algumas falharam com `github_http_403`.

Esses resultados não representavam regressão do código mergeado; eram fan-out pós-merge e falha de uma camada auxiliar.

## Requisitos

1. `PR Evidence Gate` deve ignorar `workflow_run` cuja `head_branch` seja a branch padrão, mesmo quando o payload mantenha referência a um PR já mergeado.
2. `PR CI Watch` não deve iniciar remediação automática para `workflow_run` da branch padrão.
3. `Ollama CI Triage` automático deve atuar apenas em falha associada a PR/branch não padrão; execução manual continua disponível.
4. Os três controles devem preservar o caminho normal de PR aberto.
5. A triagem Ollama é auxiliar: falhas de acesso/infraestrutura para leitura de evidência GitHub, como `github_http_403`, devem produzir `OLLAMA_CI_TRIAGE_DEGRADED`, sem enqueue no Worker Pool e sem gerar uma segunda falha vermelha enganosa.
6. Erros internos não classificados como degradáveis continuam falhando fechado.
7. Nenhum merge, deploy, promoção, segredo, permissão administrativa ou escrita em branch protegida faz parte deste incremento.

## Controles negativos

- `workflow_run` com `head_branch=main` e PR residual => PR Evidence não executa gate de PR.
- `workflow_run` com `head_branch=main` => PR CI Remediation não executa.
- `workflow_run` com `head_branch=main` => Ollama automático não executa.
- `github_http_403` dentro da triagem opcional => artifact DEGRADED e exit code 0.
- erro interno não degradável => permanece BLOCKED/non-zero.

## Critérios de aceite

- testes de contrato dos três workflows passam;
- teste unitário comprova degradação de `github_http_403` sem Worker Pool;
- Pre-PR Readiness fica verde no HEAD exato e `behind_by=0`;
- PR criada somente após evidência Pre-PR válida;
- checks da PR permanecem verdes no mesmo SHA;
- nenhum merge/deploy é executado por este incremento.
