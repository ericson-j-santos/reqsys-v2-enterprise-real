# Inventário físico estritamente read-only do Worker Pool DEV

## Escopo autorizado
Somente DESKTOP-PDQK954, serviço Docker Compose codex-worker-pool em
127.0.0.1:8097 e duas tasks já enfileiradas, ReqSys #2546 e #2547.
Não habilita Builder/Validator, não migra banco nem inicia cutover.

## Requisitos
1. Reutilizar .github/workflows/codex-worker-pool-smoke-dev.yml com
   mode=inventory-read e workflow_dispatch no runner PC24x7.
   Nenhum workflow novo, push, schedule ou entrada livre.
2. Comando literal do proprietário na issue #1705:
   /reqsys run pc24x7-worker-pool-inventory-dev. Preservar os gates
   do Authorized Actions Gateway para autor, issue, SHA e pickup.
3. Session Launcher obrigatório com preflight do runner e regras
   canônicas no SHA exato. Todo comando passa por Command Gateway.
4. Confirmar host, SHA, correlation_id, 127.0.0.1:8097, único
   container do Compose e volume persistente /data. Recusar bind
   aberto, duplicidade, token com montagem não read-only e Docker ausente.
5. Executar somente docker ps, inspect e exec não privilegiado no
   container existente. SQLite URI mode=ro e PRAGMA query_only=ON.
   Nunca usar snapshot, workers GET mutável, claim, requeue,
   docker compose up/down, restart ou deploy.
6. Validar integridade, tabelas e coluna last_material_progress_at.
   Não criar banco ausente.
7. Fixar identidades exatas:
   cwp-cdb85c31e3cc4e972f3094ab/#2546/request 4f6f18810783cdc6872f04f1;
   cwp-7d84018f3319356181ab9b47/#2547/request 9a9783d5ac78199eacfd13c0;
   ambas no ReqSys, base SHA 14232beac63c8d202f90bed1cf23df8680a54b2e.
   Nunca reenfileirar se tarefa não existir.
8. Publicar somente resumo sanitizado de estado, perfil,
   Builder/Validator, heartbeat, readiness, regras SHA, afinidade,
   ocupação e motivo de inelegibilidade. Hash truncado em IDs de worker.
   Não expor volumes, caminhos do host, tokens, leases ou raw SQL.
9. Fail-closed para host, SHA, schema, tarefa, mount, JSON inesperado,
   DB ausente, regras inválidas e timeout.
10. Testar positivo, negativos host/SHA/mount RW/porta, ESTUDO,
    rules_sha incorreto, DB inexistente, replay/idempotência,
    ausência de mutação e controle de dados sensíveis.
11. CI do HEAD, upload obrigatório do artifact sanitizado e
    leitura independente no host/version/SHA.
12. Migração 1.2.0 -> 1.4.0 em etapa separada. Exigir backup
    consistente do SQLite/WAL, restore testado, imagem/SHA fixados,
    rollback, E2E, e política engineering-worker-pool/
    migration/cutover-policy-v1.json. Nunca excluir legado.

## Critérios de aceite
WORKER_POOL_PHYSICAL_INVENTORY_READ_OK no Desktop no SHA integrado;
artefato íntegro, integridade DB, identidades originais,
contagem real de Builder/Validator e prova de não-mutação.
Apenas o inventário não prova execução nem CUTOVER_READY.
