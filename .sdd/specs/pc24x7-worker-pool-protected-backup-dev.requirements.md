# Backup protegido do Worker Pool PC24x7 DEV

## Objetivo
Criar caminho governado para backup SQLite 1.2.0 do coordenador físico e validação
de restauração em instância SQLite isolada, sem transferir conteúdo do banco ao
GitHub e sem alterar serviço, fila, tokens ou variáveis do runtime.

## Escopo e invariantes
- Reaproveitar o workflow `codex-worker-pool-smoke-dev.yml` com modo literal
  `backup-restore` e gateway allowlisted da issue #1705; não criar workflow novo.
- Host físico exato `DESKTOP-PDQK954`, `SESSION_LAUNCH_OK`, Command Gateway,
  `expected_head`, versão do runner e regras canônicas fixadas.
- Reaproveitar inventário Docker verificado: porta local 127.0.0.1:8097,
  serviço único, `/data` persistente, token bind somente leitura.
- Dentro do contêiner já em execução: `sqlite3.connect(...mode=ro)`,
  `PRAGMA query_only=ON`, `Connection.backup` para memória incluindo WAL.
  Rejeitar banco ausente, formato inválido ou superior a 64 MiB.
- Validar `integrity_check`, `foreign_key_check`, tabelas e identidades exatas
  das tarefas #2546/#2547; sem modificar leases ou chamar `GET /v1/snapshot`.
- Transportar bytes brutos somente pelo pipe local Docker → processo de teste,
  sem logging. Criptografar com DPAPI da conta do runner e persistir apenas
  arquivo .dpapi em `%LOCALAPPDATA%/ReqSys/WorkerPoolBackups` protegido por
  identidade do usuário; nenhum caminho de armazenamento arbitrário.
- Reabrir o arquivo cifrado e validar descriptografia, SHA e restore em banco
  `:memory:` independente. Replay com mesmo correlation_id deve comprovar
  ausência de cópia duplicada e falhar quando o conteúdo fonte divergir.
- Publicar ao GitHub SOMENTE JSON sanitizado contendo identidade, SHA,
  tamanho/hash, integridade, tarefas preservadas e flags negativas de mutação.
- Nenhum deploy/restart, restore sobre volume vivo, secrets, HML, STG, PROD.

## Critérios de aceite
1. Testes positivos com SQLite WAL, backup cifrado e leitura independente.
2. Negativos de host, SHA, confirmação, contêiner não confiável, token RW, banco
   faltante, corrupção, digest divergente e replay com fonte alterada.
3. Sintaxe, Ruff e Pre-PR Readiness no SHA exato antes da PR.
4. CI/PR Evidence/Governed Merge Queue e controles negativos executados no SHA.
5. Após integração, comando de proprietário único
   `/reqsys run pc24x7-worker-pool-backup-restore-dev` via issue #1705,
   artefato privado só no host e relatório sanitizado com readback físico.
6. Após a restauração `:memory:`, reabrir o backup cifrado pela conta do runner,
   restaurar uma cópia SQLite em arquivo temporário exclusivo dentro da pasta
   privada da mesma conta e verificar `integrity_check`, `foreign_key_check`,
   hash, identidade e contagem das tasks pelo arquivo real em `mode=ro`. Remover
   o arquivo temporário após fechar todas as conexões; falhar fechado se ocorrer
   erro ou limpeza incompleta. Publicar `separate_file_restore_verified=true`
   somente quando o teste físico passar, com `cutover_ready=false` até canário
   1.4, rollback, E2E consumidor e autorização específica de atualização DEV.
7. Ausência de evidência, custo extra, falta de acesso ou erro de permissão
   devem bloquear, sem fallback remoto/GUI ou retry cego.

8. O módulo auxiliar de inventário é carregado somente pelo caminho fixo da
   worktree validada no SHA. O teste `python -I` positivo e o negativo de
   módulo ausente devem detectar o erro do run físico #38331728505.

8. Testes novos devem comprovar restauração positiva em arquivo separado,
   detecção negativa de corrupção dos bytes do arquivo, limpeza após falha,
   ausência de snapshot quando a pasta privada não existe e replay sem segundo
   arquivo de backup cifrado para a mesma correlação. Arquivo temporário
   plaintext nunca pode ser publicado ou exposto em logs/artifacts.

## Incremento DEV: restore verificado em Docker volume isolado

1. Reutilizar `backup-restore` com o modo adicional `backup-volume-restore`, acionado apenas pelo comando literal `/reqsys run pc24x7-worker-pool-backup-volume-restore-dev` da issue #1705. O modo antigo não deve executar Docker-volume restore automaticamente.
2. Depois de criar e reabrir a cópia DPAPI e validar o restore em arquivo temporário, transferir o SQLite **somente por stdin local** para um contêiner descartável, sem rede, privilégio, shell, mounts do legado ou token, com volume novo identificado pela correlação e imagem SHA-256 real do coordenador já verificado.
3. Reabrir o SQLite a partir do volume em contêiner separado com `mode=ro`, comparar SHA-256, `integrity_check`, `foreign_key_check` e identidades das tasks #2546/#2547; repetir a importação deve falhar em `O_EXCL` sem modificar a cópia.
4. O volume descartável deve ser removido apenas quando `Name` e label de propriedade corresponderem à correlação. Falha de limpeza bloqueia resultado; não usar `docker prune`, Compose, volume vivo, `GET /v1/snapshot` ou fallback remoto/GUI.
5. Nenhum byte plaintext do banco, token, caminho privado ou dado de tarefa deve ir para logs, GitHub ou artefatos. Apenas recibo sanitizado com `separate_volume_restore_verified`, `volume_cleanup_verified`, `volume_replay_negative_verified` e flags negativas de cutover.
6. Validar sintaxe, testes positivos/negativos/replay/colisão/owner drift, SDD, Pre-PR e E2E físico no SHA de merge antes de declarar o incremento concluído.
7. **Não** considerar a imagem legada de leitura como execução da API 1.4 com dados reais; `real_backup_imported_into_worker14=false`, `rollback_rehearsal_passed=false`, `cutover_ready=false` e nenhum Builder/Validator registrado permanecem bloqueios.
