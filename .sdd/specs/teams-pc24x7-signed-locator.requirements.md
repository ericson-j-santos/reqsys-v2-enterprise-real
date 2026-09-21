# Central IA/Teams DEV via locator PC24x7 assinado — Requisitos

## Contexto evidenciado

O run `35649334799` do workflow `PC24x7 Teams Service Token Bootstrap`, no SHA `3c744ba2bc55548baf7f66465a9fa5909191c433`, autenticou com sucesso no Azure por OIDC e acessou o Key Vault, porém falhou fechado ao emitir o token S2S com `service_token_mint_failed:http_401`.

A causa de arquitetura é que o bootstrap e o E2E ainda fixavam `https://reqsys-api-dev.fly.dev`, apesar de o runtime DEV canônico já ser PC24x7 e o contrato do projeto exigir que consumidores CI resolvam o locator público Ed25519 vigente.

## Requisito 1 — nenhuma dependência Fly no bootstrap/E2E Teams DEV

Os workflows `pc24x7-teams-token-bootstrap.yml` e `pc24x7-teams-ephemeral-e2e.yml`, bem como seus scripts executores, não podem usar `reqsys-api-dev.fly.dev` como URL padrão ou fallback.

A ausência de runtime resolvido deve falhar fechado como configuração ausente, sem tentar Fly.

## Requisito 2 — resolução pelo locator PC24x7 assinado

Antes de qualquer chamada ao runtime DEV, ambos os workflows devem:

1. executar `node scripts/resolve_pc24x7_dev_locator.mjs --self-test`;
2. resolver o locator vigente com `--output`;
3. aceitar apenas a URL retornada por `steps.locator.outputs.base_url`;
4. exportar essa URL como `REQSYS_API_BASE_URL`;
5. preservar o locator sanitizado no artifact da execução.

O resolver existente já valida Ed25519, ambiente `dev`, TTL máximo, `issued_at`, `selected_url` e domínio HTTPS `*.trycloudflare.com`.

## Requisito 3 — E2E same-SHA

O E2E da Central IA/Teams só pode executar contra runtime cujo `GET /api/runtime/build-info` reporte `build_sha` exatamente igual a `github.sha` do `workflow_dispatch`.

Divergência deve falhar antes de emitir token efêmero ou criar conversa.

## Requisito 4 — disparo runtime governado

O E2E real deve executar somente por `workflow_dispatch` governado. O gatilho legado `workflow_run: Fly DEV Fast Deploy` deve ser removido.

Em PR, apenas o contrato/testes podem rodar; nenhuma chamada real ao runtime Teams DEV deve ocorrer.

## Requisito 5 — preservação de segurança

- DEV apenas;
- nenhum TEST/HML/PROD;
- nenhum segredo em log/artifact;
- bootstrap continua usando OIDC + Key Vault;
- E2E continua revogando token efêmero em `finally`;
- locator contém somente evidência pública/sanitizada;
- falha de locator, SHA, readiness, autenticação, entrega ou revogação permanece fail-closed.

## Critérios de aceite

1. `reqsys-api-dev.fly.dev` não aparece nos dois workflows nem como default nos dois scripts executores.
2. Ambos os workflows resolvem `resolve_pc24x7_dev_locator.mjs` e usam `steps.locator.outputs.base_url`.
3. O bootstrap falha com `REQSYS_API_BASE_URL_missing` quando executado sem runtime resolvido.
4. O E2E falha com `REQSYS_API_BASE_URL_missing` quando executado sem runtime resolvido.
5. O E2E valida `/api/runtime/build-info` e bloqueia em `pc24x7_runtime_sha_mismatch`.
6. O E2E não contém mais `workflow_run: Fly DEV Fast Deploy`.
7. Testes direcionados e operacionais ficam verdes no HEAD exato.
8. Após eventual merge autorizado, reexecutar bootstrap via gateway; somente se `READY`, executar E2E no mesmo SHA do runtime.
