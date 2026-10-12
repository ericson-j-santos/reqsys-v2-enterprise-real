# Worker Pool DEV — versão física e elegibilidade da task #2547

## Objetivo
Depois da integração da PR #20 do engineering-worker-pool, verificar se a versão efetivamente executada no Desktop PC24x7 possui o endpoint aditivo de diagnóstico, e se disponível, ler as pré-condições de Builder/Validator da tarefa da lupa ReqSys.

## Identidades fixas
- Repositório: ericson-j-santos/reqsys-v2-enterprise-real
- Issue: #2547
- Task: cwp-7d84018f3319356181ab9b47
- Request ID: 9a9783d5ac78199eacfd13c0
- Base SHA da task: 14232beac63c8d202f90bed1cf23df8680a54b2e
- Host: DESKTOP-PDQK954, loopback http://127.0.0.1:8097
- Código novo de referência: engineering-worker-pool/main d05ad0ce7c2945db1914a400127621bce4256a8b (PR #20)
- Deploy autorizado por este incremento: nenhum

## Critérios de aceite
1. Só o comentário literal do proprietário na issue operacional #1705 pode despachar /reqsys run codex-worker-pool-version-2547-read-dev; proibir URL, token, task ID ou modo parametrizável.
2. Reusar o workflow DEV governado; PC24x7 self-hosted Windows; checkout SHA imutável; regras pinadas; Session Launcher com preflight de runner; Command Gateway; host/SHA validados antes da leitura do token local protegido.
3. Consultar somente GET /health, GET /openapi.json, GET /v1/tasks/cwp-7d84018f3319356181ab9b47 e, se anunciado pelo OpenAPI, GET /v1/tasks/cwp-7d84018f3319356181ab9b47/diagnostics.
4. Serviço legado ReqSys Codex Worker Pool versão 1.2.0 sem diagnóstico produz prova de atualização necessária; Engineering Worker Pool versão 1.4.0 com diagnóstico valida SQLite mode=ro, claim_performed=false, reconciliation_requested=false, identidade e elegibilidade.
5. Nunca deduzir SHA do container pela versão do OpenAPI. O SHA de código registrado é referência, não atestado do binário: runtime_source_sha_attested=false.
6. Resumir capacidade apenas com números e reason codes allowlisted. Não expor worker_id, token, lease_token, paths locais, headers, logs crus ou credenciais.
7. Host/SHA divergente, resposta incorreta, versão inconsistente, identidade inesperada, HTTP de erro ou segredo indisponível devem falhar fechados.
8. Não consultar GET /v1/snapshot, GET /v1/workers ou GET /v1/repositories, capazes de recuperar leases no legado. Não chamar POST/PUT/PATCH/DELETE nem alterar container, lane ou worker.
9. Exigir controles positivos, negativos e idempotentes no Pre-PR Readiness Gate do SHA final; criar PR somente após READY_FOR_PR=passed e merge exclusivamente após gates obrigatórios verdes no HEAD corrente.
10. Quando a versão física estiver atrasada, somente preparar o plano DEV com compatibilidade de banco, backup, rollback, CI/E2E e autorização independente de deploy/restart. Não alterar o runtime nesta entrega.
11. Se a versão nova já estiver disponível, não atualizar o container; reportar a razão exata de inelegibilidade, sem confundir precheck com claim.
12. O arquivo emitido por `scripts/codex_worker_pool_version_2547_probe_dev.py` deve coincidir exatamente com `EVIDENCE_REL` e `upload-artifact` do job `version-2547-read`, em `artifacts/codex-worker-pool-version-2547-read-dev/evidence.json`; o teste de regressão deve rejeitar o caminho divergente antigo.

## Proibições
Nenhum novo enqueue, claim, requeue, leitura de snapshot, rotação de token, reinício, deploy, alteração HML/STG/PROD ou custo adicional. Falhar fechado diante de bloqueio.
