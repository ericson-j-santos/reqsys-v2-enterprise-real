# Runbook: governed PC24x7 DEV recovery

## Preconditions

- Use the repository session launcher and Command Gateway.
- Confirm the physical host is `DESKTOP-PDQK954` and the target is DEV only.
- Confirm all three Compose services report working directory
  `C:\dev\chatgpt-workers\wt-pc24x7-public-dev-governed`.
- Preserve the fingerprint printed by each successful evidence-producing phase
  outside the JSON manifest.
- Obtain review and explicit approval before `prepare` or `rollback`; both mutate
  Docker state. `capture` is read-only except for writing its local evidence file.

## Commands

Read-only post-deploy readiness and database check (no manifest or rollback required):

```text
python -B scripts/dev_runtime_recovery.py deploy-check \
  --expected-sha <deployed-full-sha>
```

This command performs no Compose write, restart, tag, or evidence-file write. It
waits for the exact SHA plus healthy runtime endpoints, resolves exactly one DEV API
container, and runs the fixed sanitized `SELECT 1` probe by stdin. It fails on host,
project, root, label or cardinality mismatch; readiness deadline; SHA mismatch;
database timeout/query failure; or malformed probe JSON.

Liveness must return HTTP 200 with either `alive: true` or `status: "alive"`, as
defined by the two existing route implementations. Redirects, timeouts, HTTP
errors, malformed JSON, `alive: false`, missing fields, or contradictory status are
terminal/transient failures handled within the bounded readiness deadline.
If both `alive` and `status` are returned, both must be valid; one valid field never
masks a false, mistyped, null, missing, or contradictory companion field.
Non-string `status` and non-boolean `alive` values are represented only by sanitized
invalid-type markers and always fail the gate; their original values are never
included in diagnostic output.

Capture current rollback evidence:

```text
python -B scripts/dev_runtime_recovery.py capture --manifest <approved-evidence-path>
```

After independent review, preserve images and create the durable override:

```text
python -B scripts/dev_runtime_recovery.py prepare \
  --manifest <approved-evidence-path> \
  --expected-fingerprint <capture-fingerprint> \
  --confirm PREPARE-ROLLBACK-PC24X7-PUBLIC-DEV
```

Validate prepared evidence without changing Docker:

```text
python -B scripts/dev_runtime_recovery.py validate \
  --manifest <approved-evidence-path> \
  --expected-fingerprint <prepared-fingerprint>
```

Execute rollback only after a failed or partial approved DEV deployment:

```text
python -B scripts/dev_runtime_recovery.py rollback \
  --manifest <approved-evidence-path> \
  --expected-fingerprint <prepared-fingerprint> \
  --confirm ROLLBACK-PC24X7-PUBLIC-DEV
```

## Stop conditions

Stop without improvising if host/root/project identity differs, service cardinality
is ambiguous, any service lacks an ordered Compose source, a source changes after
capture, a reparse point is found, a deterministic tag points to another image,
evidence fingerprint differs, readiness reaches its deadline, or the sanitized
database probe fails. Ordered sources may differ between services after a governed
partial recreation; schema 3 preserves and replays each chain separately.

Do not delete `.reqsys-recovery` while containers reference its override. Do not
retag, rebuild, recreate, or prune images outside the reviewed command sequence.

## Evidence

Record only command exit status, external fingerprint, sanitized phase category,
observed runtime SHA, and test results. Never attach env-file contents, raw driver
errors, connection strings, credentials, container logs, or database contents.

## Public DEV cutover wrapper

O workflow `Noteri Study Mode DEV Reconcile`, modo `public-static`, usa
`scripts/pc24x7_public_dev_cutover_guard.py` para encadear este rollback com um
backup PostgreSQL protegido. O modo `prepare` exige a confirmação literal
`PREPARE-PC24X7-PUBLIC-DEV-CUTOVER`, cifra o dump com DPAPI e prova uma restauração
em contêiner descartável, sem rede, usando a imagem PostgreSQL observada. Ele
também preserva snapshots privados e ordenados apenas dos manifests Compose, para
que o fast-forward do runtime não invalide o rollback; env-files não são copiados.
O modo
`rollback` exige `ROLLBACK-PC24X7-PUBLIC-DEV-CUTOVER` e pode restaurar as imagens
mesmo quando a API candidata não responde; host, raiz, projeto, cardinalidade e
image IDs continuam sendo revalidados antes da mutação.

Não execute esses comandos fora do Session Launcher e da rota separada
`owner_risk3_gateway.py`. O Command Gateway geral permanece fail-closed para
Risk 3. Após reler o comentário exato e recente do owner na issue `#1705` e o SHA
de `main` capturado pelo gateway, o modo `public-static` materializa autorizações
privadas, específicas e temporárias com `set_owner_risk3_action.py`. Cada ação é
vinculada ao ambiente DEV, scope, worktree limpo, SHA, script rastreado e argumentos
exatos; o readback precisa confirmar que o modo amplo `standard_gold_development`
não foi alterado. O `owner_risk3_gateway.py` executa então a ação cadastrada, sem
aceitar comando ad-hoc. O workflow nunca ativa automaticamente o modo amplo, e
qualquer divergência ou expiração bloqueia antes da mutação. O manifesto, ciphertext e override em
`.reqsys-recovery` são privados e não devem ser anexados à execução. A base ativa
não é restaurada automaticamente: qualquer mudança observada após rollback
bloqueia o fluxo para avaliação específica.

Se o `prepare` falhar, o wrapper grava um recibo público mínimo com `status=blocked`,
um `reason_code` normalizado por allowlist e somente flags de segurança negativas.
O workflow valida esquema, tipos e allowlist antes de substituir o motivo placeholder
da evidência pública. Recibo ausente, malformado, com campos extras ou código não
permitido vira `prepare_failure_receipt_missing_or_invalid`; em todos os casos o job
permanece bloqueado antes de OIDC, deploy, locator ou E2E. Saída bruta do processo,
stderr, caminhos privados, credenciais e conteúdo do banco nunca são publicados.
