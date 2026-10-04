# Fila recuperada event-driven sem Work

## Objetivo

Executar a fila `ci:recuperado` por eventos do GitHub, sem ChatGPT Work e sem polling horário como motor técnico.

## Requisitos

1. `PR CI Watch` continua tratando falhas transitórias após CI.
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

## Limite atual

Falhas transitórias podem ser reexecutadas automaticamente. Falhas determinísticas de código continuam fail-closed e são registradas/notificadas; este incremento não autoriza geração de código no PR sem executor governado específico.

## Critérios de aceite

- contratos da fila e dos agentes existentes verdes;
- Pre-PR Readiness verde no HEAD exato e `behind_by=0`;
- crescimento líquido zero em `.github/workflows`;
- checkpoint pós-merge e avanço da próxima PR evidenciados.
