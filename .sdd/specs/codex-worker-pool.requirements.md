# Requisitos — Codex Worker Pool distribuído

## Escopo

Consolidar o mecanismo operacional das issues #1767, #1768, #1769, #1770 e #1771.

## Requisitos funcionais

1. Registrar workers com `worker_id`, host, role, profile, capacidade, heartbeat, controller version, rules SHA, Gateway e `state_validated`, recusando claim quando o rules SHA divergir do SHA canônico esperado.
2. Derivar `idempotency_key` estável de repositório, issue e `request_id`.
3. Impedir duas aquisições da mesma task sob concorrência.
4. Manter lease com expiração e recuperação governada.
5. Limitar tentativas e enviar falha permanente para quarentena.
6. Derivar branch e `workspace_key` determinísticos.
7. Impedir mais de uma task ativa por worker e mais de uma task ativa no mesmo workspace.
8. Worker em `ESTUDO`, offline/stale ou não governado não pode receber desenvolvimento.
9. Builder deve publicar `produced_sha` exato antes do handoff.
10. Validator deve ser um worker diferente do Builder e concluir exatamente o SHA entregue.
11. Bloqueio externo deve liberar o worker sem concluir a task falsamente.
12. Snapshot deve informar host, worker, papel, profile, task, SHA, heartbeat, fila e `why_idle`, sem lease token ou segredo.
13. API mutável e snapshot devem exigir bearer token lido de arquivo; `/health` deve falhar readiness quando o token não estiver configurado.
14. O serviço não executa merge, deploy, alteração de segredo ou permissão administrativa.
15. Toda task deve informar `base_sha` explícito antes de ser aceita.
16. O SQLite é estado de coordenação local/DEV do pool e não substitui `OperationalQueue`/Redis Streams como transporte durável corporativo em STG/PROD.

## Requisitos de qualidade

- SQLite em WAL e transações imediatas para claim/recovery.
- logs com `correlation_id` sem corpo/token;
- erros explícitos;
- configuração por ambiente;
- persistência em volume;
- bind PC24x7 somente em loopback por padrão;
- testes positivos, negativos, concorrência, replay, recuperação e leitura independente.

## Critérios de aceite

- suíte `services/codex-worker-pool/tests` verde;
- teste concorrente entrega uma task para exatamente um Builder;
- lease expirado volta à fila e pode ser adquirido por outro Builder;
- falha permanente cria quarentena;
- replay não cria nova task;
- Builder/Validator diferentes fecham o fluxo pelo mesmo `produced_sha`;
- leitura HTTP independente confirma estado final;
- `lease_token` não aparece em leitura normal/snapshot;
- E2E físico multi-host permanece `PARCIAL/BLOQUEADO` enquanto um host não estiver elegível.
