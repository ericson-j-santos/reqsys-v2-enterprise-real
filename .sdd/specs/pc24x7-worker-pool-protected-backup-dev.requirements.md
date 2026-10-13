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
6. Ensaio de restauração `:memory:` **não comprova** restauração em arquivo/
   volume físico separado exigido por `engineering-worker-pool`. O resultado
   `separate_file_restore_verified=false` e `cutover_ready=false` são
   obrigatórios até operação física distinta, canário 1.4, rollback e E2E.
7. Ausência de evidência, custo extra, falta de acesso ou erro de permissão
   devem bloquear, sem fallback remoto/GUI ou retry cego.

8. O módulo auxiliar de inventário é carregado somente pelo caminho fixo da
   worktree validada no SHA. O teste `python -I` positivo e o negativo de
   módulo ausente devem detectar o erro do run físico #38331728505.
