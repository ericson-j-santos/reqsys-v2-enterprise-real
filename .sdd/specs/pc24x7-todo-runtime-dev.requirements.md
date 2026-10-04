# Requisitos — ReqSys Runtime TODO Global no PC24x7 DEV

## Contexto evidenciado

O ciclo `TODO Global Hourly Cycle` possui contrato local válido, porém a execução real estava bloqueada porque não existia uma superfície pública materializada para `runtime/app`. O backend já contém o adapter Notion, mas o router não estava montado na aplicação principal. Fly.io é legado e não pode ser usado como fallback.

## Estado alvo

Materializar no Desktop PC24x7, somente em DEV, o `ReqSys Runtime` com Redis durável e uma superfície pública mínima sob o locator PC24x7 assinado:

- `/runtime-core/health`;
- `/runtime-core/api/runtime/build-info`;
- `/runtime-core/api/todo-events`;
- `/runtime-core/api/todo-events/{event_id}`.

Nenhum endpoint genérico de jobs, Central ou administração do Runtime deve ser publicado por essa superfície.

## Requisitos

1. O worktree físico deve ser o repositório ReqSys esperado, árvore rastreada limpa e atualização somente por fast-forward até SHA pertencente à `origin/main`.
2. O runtime deve usar `QUEUE_BACKEND=redis`, `STORAGE_BACKEND=redis`, volume persistente e worker assíncrono habilitado.
3. O adapter deve apontar internamente para `http://api:8000/api/internal/todo-global/upsert`.
4. O router do adapter Notion deve estar montado no backend e expor readiness autenticada sem retornar segredo.
5. `todo-events` deve exigir token de produtor; ausência de configuração falha 503 e token inválido falha 401.
6. O token produtor e o token S2S do adapter devem residir no Azure Key Vault e nunca em Git, log ou artifact.
7. O token S2S do adapter deve ter somente o escopo `todo_global:upsert`; token inválido pode ser substituído de forma governada usando a credencial admin DEV já autorizada.
8. O cycle horário deve resolver o locator Ed25519 vigente, derivar `/runtime-core`, ler o token produtor do Key Vault por OIDC e exigir same-SHA antes de publicar evento.
9. Nenhum URL Fly, Render ou fallback alternativo é permitido.
10. HML/STG/PROD não podem ser alterados.

## E2E obrigatório

No SHA corrente de `main`:

1. API principal e Runtime Core reportam o mesmo `build_sha`.
2. POST sem token é rejeitado com 401.
3. Payload inválido com token é rejeitado com 400/422.
4. Evento válido é aceito e chega a estado terminal.
5. Resultado terminal contém `readback_verified=true` vindo do adapter Notion.
6. Replay do mesmo `event_id` retorna o mesmo `job_id` e `duplicate_event=true`.
7. O mesmo fluxo é repetido pela superfície pública resolvida pelo locator assinado.
8. Evidência registra ambiente, host, SHA, correlation_id e run, sem valores secretos.

## Critérios de aceite

- [ ] Contrato e testes locais verdes.
- [ ] Pre-PR Readiness `passed` no HEAD exato, `behind_by=0`.
- [ ] PR integrada apenas com gates obrigatórios verdes.
- [ ] Runner Desktop faz pickup físico.
- [ ] Runtime + Redis materializados e saudáveis.
- [ ] Adapter Notion ready.
- [ ] E2E físico aprovado.
- [ ] E2E público aprovado no mesmo SHA.
- [ ] TODO Global Hourly Cycle terminal com readback e replay.
