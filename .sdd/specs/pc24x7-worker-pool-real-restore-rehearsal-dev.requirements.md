# Ensaio DEV: snapshot real 1.2 → cópia isolada 1.4 → rollback isolado 1.2

## Objetivo e risco
Comprovar compatibilidade física de um SQLite **capturado por Online Backup** do coordenador 1.2 ativo, com WAL e preservação de identidades. Testar o candidato 1.4.0 e a imagem legada 1.2.0 **somente** em novo volume Docker privado, no Desktop PC24x7 DEV. Manter serviço original, banco, token real, porta 8097 e tasks #2546/#2547 intocados. Não executar cutover.

## Ação governada e fonte
- Comando literal do owner, somente issue ReqSys #1705: `/reqsys run pc24x7-worker-pool-real-restore-dev`.
- Reutilizar workflow `.github/workflows/codex-worker-pool-smoke-dev.yml` com modo fixo `restore-rehearsal`; não criar workflow/runner/fila nova.
- Exigir `DESKTOP-PDQK954`, regras pinadas `f6ccb143a581e28650e9b640226f9ef671d469f2`, Worker Pool SHA `e9f2627938a9e4d741d1d50796a72f69b35f547f`, ReqSys `github.sha`, `SESSION_LAUNCH_OK`, Command Gateway e `expected_head`.
- O código `scripts/pc24x7_worker_pool_real_restore_rehearsal_dev.py` reutiliza funções versionadas do backup e canário anteriores.
- Primeiro validar contêiner legado único por Docker inspect + porta/volume/token RO e leitura SQL mode=ro; bloquear se tasks originais não estiverem queued/sem lease/0 tentativas ou se existir Builder/Validator.
- Criar **um novo** Online Backup, criptografar apenas com DPAPI Windows user-scope em diretório protegido fora do Git, validar integridade/identidade em RAM e arquivo privado temporário. Não copiar plaintext para worktree, artifact, issue ou log.
- Passar bytes temporariamente por stdin para `docker run --rm --network none` escrevendo com `open('xb')` exclusivamente em volume novo etiquetado por correlação, validado por hash, `integrity_check` e `foreign_key_check`.
- Usar origem Docker image 1.4 pinada por SHA/label e digest local, usuário `reqsys`, cap-drop, rootfs RO, bind sintético de token RO e `127.0.0.1:18098`. HTTP autenticado somente GET de contrato/diagnóstico; 401 negativo; leitura SQL independente de **todas** tasks e digest sem publicar linhas.
- Remover exclusivamente o contêiner 1.4 etiquetado, iniciar a **mesma cópia privada** na imagem antiga identificada pelo Compose (digest local pré-verificado), `127.0.0.1:18099`, e comprovar API 1.2 + digest e IDs iguais. Isso é ensaio de rollback **em cópia**, não parada/troca do serviço ativo.
- Em `finally`, remover somente containers, volume, tag de imagem e token temporários com label exata; qualquer colisão, falha de cleanup, identidade, hash, permissão, SQL, readiness ou negativo deve produzir estado BLOQUEADO.
- Confirmar identidade/estado do legado por readback independente ao final. Nenhum `GET /v1/snapshot`, claim, requeue, register worker, Docker Compose up/down, restart/produção/segredo real. Não reutilizar evidência de SHA antigo.

## Validação
1. Testar sintaxe, Ruff, JSON/YAML/SDD; positivo/negativo, replay, idempotência do import (open xb), detecção de alteração de digest, autenticação, restrição de URL e rejeição de recursos não pertencentes.
2. Gate `READY_FOR_PR=passed` em HEAD exato, sem atraso da main, antes de abrir PR. CI completo, CodeQL/revisões/GMQ e expected_head_sha antes de integrar.
3. Depois do merge governado, **um único** teste físico, sem reexecução concorrente; artifact sanitizado + SHA256 e leitura independente do efeito no mesmo par de SHAs.
4. Flags de recibo `physical_snapshot_restored_to_candidate=true`, `rollback_to_legacy_copy_passed=true` podem ser verdadeiras **apenas quando ocorreram de fato**. A política mantém `cutover_ready=false`; homologação de cutover real, Builder/Validator e E2E das issues permanecem separados.

## Critério de aceite e bloqueio
O ensaio só está concluído com prova física de 1.4 e 1.2 na cópia privada, tasks idênticas após cada fase, nenhum recurso temporário remanescente e legado original inalterado. Sem essas provas, usar `RESTORE_REHEARSAL_BLOCKED`. Nunca definir `CUTOVER_READY` por este teste.

## Regressão do contrato de admissão do comando físico (P0)

- O parser versionado \`scripts/authorized_teams_e2e_admission.py\` deve aceitar o comando literal \`/reqsys run pc24x7-worker-pool-real-restore-dev\` já mapeado no Gateway, sem introduzir parâmetros livres ou capacidade de execução arbitrária.
- Reutilizar o controle de identidade do owner, Issue #1705, SHA, \`comment_id\` e janela anti-duplicidade de 120 segundos. Um único comando deve ser admitido; replay dentro da janela deve ser suprimido; comando não allowlisted ou registro incompleto deve falhar fechado.
- \`tests/test_authorized_teams_e2e_admission.py\` deve cobrir contrato entre workflow e parser, cenário positivo, duplicado, fora da janela e comando indevido. Uma nova emissão física somente após \`READY_FOR_PR=passed\`, CI e integração governada.
- Falha anterior: Gateway #38496349534 rejeitou o argumento antes do despacho. Escopo exclusivamente DEV isolado, sem cutover, secrets ou produção.
