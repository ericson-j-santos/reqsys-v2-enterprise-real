# Worker Pool 1.4 — canário físico isolado PC24x7 DEV

Origin: `engineering-worker-pool#8`, ReqSys `#2020`, tarefas `#2546`/`#2547`.

## Requisitos

1. Executar **apenas** em `DESKTOP-PDQK954` / DEV com Session Launcher, preflight do runner, worktree reservado e Command Gateway (risco 2). Exigir comando literal do owner na issue operacional #1705. Sem shell remoto/GUI/SSH/RDC de contingência.
2. Usar ReqSys `main` no SHA real do workflow, regras fixadas em `f6ccb143a581e28650e9b640226f9ef671d469f2` e fonte `engineering-worker-pool` em `9074b170d47a7d63a4e0ef6cee2d37282bbbace8`. Recusar SHA divergente, origem diferente ou checkout sujo. Build Docker somente de Dockerfile/requirements/app do checkout verificado, com label da revisão e imagem de nome exclusivo.
3. O serviço legado 1.2, bind `127.0.0.1:8097`, volume, token e banco **nunca** são reiniciados, alterados ou montados no canário. Antes e depois, inspecionar identidade/container/imagem/loopback via rota já versionada; não consultar `GET /v1/snapshot`/`GET /v1/workers` no legado.
4. Reaproveitar unicamente o backup DPAPI já realizado pelo run #38389083856 (origem/correlação/hash exatos), sob a mesma identidade Windows; falhar fechado se faltar/mudar. Descriptografar exclusivamente em memória; canalizar bytes SQLite via stdin a um container temporário **sem rede** para montar volume Docker novo. Nenhum SQLite plaintext deve ficar no host, Git ou artifacts.
5. Candidato efêmero isolado em `127.0.0.1:18099`, volume `wp-physical-canary-RUN-ATTEMPT`, token efêmero em arquivo privado com DACL restrita; usuário não-root, raiz somente leitura, caps removidas, sem privilégios. Proibir nomes/volumes/portas em uso e tags flutuantes ou origem não verificada.
6. Executar E2E físico: inspeção independente de Docker/image digest, health, API 1.4, `/v1/contract` v1, 401 sem token/401 token inválido, GET de ambas as tasks da cópia com estado queued, sem lease e sem tentativas; `/v1/tasks/{task_id}/diagnostics` SQLite RO, GET 404 negativo e SQLite direto em modo `ro` no **candidato**. Nunca chamar POST de enqueue/register/claim.
7. Mesmo em sucesso, remover apenas recursos efêmeros comprovadamente próprios, confirmar ausência do container/volume, validar que o legado permaneceu idêntico e registrar recibo sanitizado. Em falha de limpeza, falhar e não declarar sucesso.
8. O relatório deve provar host, SHAs, correlação, imagem do candidato, backup privado reutilizado, duas tasks preservadas, controles negativos, cleanup, `live_database_modified=false`, `enqueue_performed=false`, `claim_performed=false`, `secrets_exposed=false`, `production_touched=false`; nunca conter token, SQLite, paths privados ou IDs de lease.
9. **Não homologar cutover.** Mesmo se o canário passar, `rollback_rehearsal_passed=false`, `cutover_ready=false` e Builder/Validator físicos continuam ausentes. A prova do canário é distinta do ensaio de rollback 1.4→1.2 e da entrega de handlers reais.
10. Testar previamente sintaxe, esquema YAML, caso positivo, controles negativos de host/SHA/credencial/isolation/SQLite, replay e cenário de falha de Docker. Sem E2E físico completo, resultado 🟡 parcial e checkpoint na issue.

## Design e tarefas

- Extendendo **sem novo workflow** o `codex-worker-pool-smoke-dev.yml` com mode `physical-canary` e o gateway allowlisted.
- Script fixo `scripts/pc24x7_worker_pool_physical_candidate_dev.py`; teste `tests/test_pc24x7_worker_pool_physical_candidate_dev.py`; contrato do workflow `tests/test_pc24x7_worker_pool_physical_canary_workflow.py`.
- Implementar fora de HML/STG/PROD. Não encerrar tarefas ou remover legado.
