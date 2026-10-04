# Fila recuperada event-driven sem Work

## Objetivo

Executar a fila `ci:recuperado` por eventos do GitHub, sem ChatGPT Work e sem polling horário como motor técnico.

## Requisitos

1. `PR CI Watch` continua tratando falhas transitórias após CI; falhas determinísticas técnicas elegíveis são analisadas pelo `Ollama CI Triage` e escaladas ao Codex Worker Pool existente, preservando a branch e o SHA da própria PR.
2. Bloqueio persistente em PR `ci:recuperado` deve virar checkpoint durável e aviso Teams.
3. Notificação não pode reintroduzir Fly.io.
4. Draft comum continua bloqueado; somente `ci:recuperado` pode ser sincronizado em draft.
5. Havendo várias recuperadas, somente a mais antiga por número avança por vez.
6. Draft recuperado só vira ready com HEAD/base/mergeabilidade/label e workflows obrigatórios verdes.
7. O mesmo run que promove ready não pode mergear.
8. Merge continua squash com SHA esperado.
9. Pós-merge validado gera checkpoint e dispatch da próxima sincronização.
10. O avanço usa `governed_post_merge_validation`, sem depender de novo push do token de workflow.
11. Teams é notificação; GitHub continua fonte de verdade.
12. Nenhum workflow novo é criado.
13. Nenhuma etapa executa deploy, promoção, force-push, segredo ou branch protection.

## Correção automática governada

Falhas transitórias podem ser reexecutadas pelo `PR CI Watch`. Para falhas determinísticas, o `Ollama CI Triage` já opera em modo `execute`: somente categorias técnicas com confiança suficiente, sinal determinístico e PR same-repo no SHA atual podem ser escaladas. O Worker Pool recebe `target_branch` da própria PR e `base_sha` igual ao HEAD analisado. Segurança, governança, permissões, conflito, quota, artifact, timeout, fork externo e SHA obsoleto permanecem fail-closed.

## Critérios de aceite

- contratos da fila e dos agentes existentes verdes;
- Pre-PR Readiness verde no HEAD exato e `behind_by=0`;
- crescimento líquido zero em `.github/workflows`;
- checkpoint pós-merge e avanço da próxima PR evidenciados;
- contrato comprova reutilização do `Ollama CI Triage`/Worker Pool para correção técnica na mesma branch.
