# Fila recuperada event-driven sem Work

## Objetivo

Executar a fila `ci:recuperado` por eventos do GitHub, sem ChatGPT Work e sem polling horário como motor técnico.

## Requisitos

1. `PR CI Remediation` reage por `workflow_run` aos gates primários e usa o cron apenas como watchdog.
2. O evento de remediação deve atuar somente no PR e HEAD associados; SHA stale não pode produzir mutação.
3. Workflows ainda pendentes não podem marcar PR como recuperado.
4. Falhas transitórias allowlisted podem ser reexecutadas automaticamente no mesmo HEAD.
5. Falhas técnicas determinísticas elegíveis seguem por `Ollama CI Triage` → Worker Pool, mantendo a mesma branch e `base_sha`.
6. Bloqueio persistente em PR `ci:recuperado` deve virar checkpoint durável e aviso Teams.
7. `Teams Commit Notification` pode notificar triagem/remediação concluídas e merge governado; ausência de Teams não bloqueia CI.
8. Notificação não pode reintroduzir Fly.io.
9. Draft comum continua bloqueado; somente `ci:recuperado` pode ser sincronizado em draft.
10. Havendo várias recuperadas, somente a mais antiga por número avança por vez.
11. Draft recuperado só vira ready com HEAD/base/mergeabilidade/label e workflows obrigatórios verdes.
12. O mesmo run que promove ready não pode mergear.
13. Merge continua squash com SHA esperado.
14. Pós-merge validado gera checkpoint e dispatch da próxima sincronização.
15. Teams é notificação; GitHub continua fonte de verdade.
16. Nenhum workflow novo é criado e nenhuma etapa depende de ChatGPT Work.
17. Nenhuma etapa executa deploy, promoção, force-push, segredo ou branch protection.

## Critérios de aceite

- `PR CI Remediation` possui caminho `workflow_run` e mantém o cron somente como watchdog.
- Evento stale é ignorado e workflow pendente não marca recuperado.
- `Ollama CI Triage` permanece event-driven e enfileira Worker Pool quando elegível.
- `Teams Commit Notification` consome artifacts sanitizados de triagem/remediação e reconhece merge governado.
- contratos da fila e dos agentes existentes ficam verdes;
- Pre-PR Readiness verde no HEAD exato e `behind_by=0`;
- crescimento líquido zero em `.github/workflows`;
- checkpoint pós-merge e avanço da próxima PR permanecem preservados.
