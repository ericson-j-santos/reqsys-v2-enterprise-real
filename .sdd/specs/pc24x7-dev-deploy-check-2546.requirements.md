# ReqSys #2546 — diagnóstico DEV governado sem alteração física

## Objetivo
Disponibilizar a operação read-only deploy-check já implementada em scripts/dev_runtime_recovery.py no PC24x7 Desktop sem criar tarefa, fila, scheduler ou runtime adicional.

## Critérios de aceite
1. Comando literal do proprietário /reqsys run pc24x7-dev-deploy-check na issue #1705; não aceitar entrada livre.
2. Reutilizar o workflow codex-worker-pool-smoke-dev.yml com mode dev-deploy-check, sem criar workflow novo.
3. Executar em DESKTOP-PDQK954 via Session Launcher, BOOTSTRAP_OK/SESSION_LAUNCH_OK, runner-version-preflight e Command Gateway risk 1.
4. Chamar exclusivamente dev_runtime_recovery.py deploy-check --expected-sha=SHA validado no HEAD do workflow; verificação read-only de projeto, endpoints, runtime SHA e SELECT 1.
5. Recibo JSON sanitizado com host, SHA, correlation_id, categoria e controles negativos, publicado mesmo se falhar.
6. Duplicidade em 120 s suprimida por identidade do comando + proprietário; corpo inválido, autor externo e readback ausente falham fechados.
7. READY_FOR_PR no HEAD atual, CI de PR e gates completos antes de merge, E2E físico após integração, artifact SHA-256/CRC e readback independente.

## Limites
Não autoriza deploy, restart, Compose up/down, segredo, HML/STG/PROD, cutover 1.2→1.4, claim ou requeue. Task cwp-cdb85c31e3cc4e972f3094ab e request 4f6f18810783cdc6872f04f1 permanecem originais. Falha de runtime SHA deve permanecer bloqueada, não corrigida automaticamente.
