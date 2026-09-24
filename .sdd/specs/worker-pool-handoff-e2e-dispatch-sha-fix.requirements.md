# Worker Pool handoff E2E — vínculo do SHA no dispatch

## Problema

O comando governado `/reqsys run codex-worker-pool-handoff-e2e-dev` chega à etapa
de dispatch, mas usa `$EXPECTED_SHA` com `set -u` sem expor o SHA capturado
pela etapa `Capture current main SHA` no ambiente do dispatch.

Evidência da falha:
- gateway run: `36030782381`;
- main: `7c84f37e019403304d84cfb2c9961d5d78a902c2`;
- erro: `EXPECTED_SHA: unbound variable`;
- nenhum workflow físico foi despachado nessa execução.

## Correção

Injetar exclusivamente:

`EXPECTED_SHA: ${{ steps.main.outputs.sha }}`

na etapa `Dispatch fixed workflow on main`.

O SHA continua sendo obtido da `main` pelo próprio gateway; nenhum SHA vindo do
comentário ou do usuário é aceito.

## Critérios de aceite

1. O dispatch do handoff recebe o SHA capturado pela etapa `main`.
2. O teste estrutural verifica o vínculo dentro da etapa de dispatch, e não apenas
   a presença de `EXPECTED_SHA` em outra etapa.
3. Os inputs fixos do E2E permanecem: issue `2020`, base `main`,
   request_id determinístico e correlation_id do run.
4. Nenhum novo parâmetro arbitrário, segredo, deploy ou produção é introduzido.
5. `Pre-PR Readiness` deve produzir `READY_FOR_PR=passed` no HEAD exato.
6. Após integração, o comando governado deve ser reexecutado; indisponibilidade
   do runner físico permanece um bloqueio separado e deve falhar fechado.
