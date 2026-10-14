# Canário físico isolado do Worker Pool 1.4 no Desktop DEV

## Objetivo
Acrescentar uma rota literal no Authorized Actions Gateway da issue #1705 para
executar, no runner Windows DESKTOP-PDQK954, um canário **descartável** da
implementação dedicada 1.4.0, sem trocar ou reiniciar a API legada 1.2.

## Contrato e limites
- Comando fixo de proprietário: `/reqsys run pc24x7-worker-pool-candidate-canary-dev`.
  Não aceitar URL, host, porta, nome de tarefa, commit ou segredo via comentário.
- Reutilizar `.github/workflows/codex-worker-pool-smoke-dev.yml` com modo
  `candidate-canary`; não criar workflow paralelo nem novo serviço permanente.
- Usar GitHub Actions no host exato DESKTOP-PDQK954; checkout ReqSys no
  `github.sha`, checkout do Worker Pool dedicado no SHA fixo
  `e9f2627938a9e4d741d1d50796a72f69b35f547f`, regras
  `f6ccb143a581e28650e9b640226f9ef671d469f2`.
- Exigir Session Launcher com preflight do runner e `SESSION_LAUNCH_OK`,
  worktree reservado e Command Gateway com `expected_head` atual.
- Validar em primeiro lugar a identidade do serviço legado (imagem,
  container, bind local em 8097, token bind RO) e a leitura SQLite mode=ro.
- Copiar somente `Dockerfile`, `requirements.txt` e `app/` do checkout
  do Worker dedicado para um contexto temporário privado, rejeitando
  symlinks e arquivos fora da whitelist, sem dados do usuário nem segredos.
- Criar apenas contêiner, imagem e volume novos por correlação; usar
  `127.0.0.1:18098`, usuário não-root, read-only root filesystem,
  `--cap-drop ALL`, limite de recursos, token aleatório temporário.
  Dados de teste devem ser sintéticos e exclusivos desse volume.
- Verificar contrato v1, versão 1.4.0, 401 sem token válido,
  diagnóstico read-only/422 inválido, ReqSys bridge com fallback desativado,
  replay idempotente, estado SQLite pelo processo separado.
- Confirmar que o legado mantém identidade/estado; remover todos os
  recursos do canário. Falhas de limpeza, host, SHA ou contrato bloqueiam
  o resultado sem retry cego.
- A revisão física de SHA deve manter o checkout do workflow, o preflight
  do script e o spec SDD no mesmo Worker Pool SHA imutável. O teste de
  contrato deve rejeitar divergência de SHA antes de consumir o runner.
- Artifact GitHub conterá **somente JSON sanitizado**, com
  `cutover_ready=false`, `real_backup_imported_into_candidate=false`,
  `rollback_rehearsal_passed=false`. Não elevar essas flags por CI verde.

## Critérios de aceite
1. Sintaxe, Ruff e testes positivos/negativos da validação isolada aprovados.
2. Pre-PR Readiness `READY_FOR_PR=passed`, `behind_by=0` e
   testes de contrato/Security/SDD no SHA exato, antes de abrir PR.
3. CI e todos os gates de governança/revisão realmente executados
   antes de qualquer merge com expected_head_sha.
4. Após integração, somente uma execução física por comentário literal
   autorizado, com artefato SHA-bound e readback independente.
5. Nunca executar `docker compose up/down`, escrever no SQLite vivo,
   recuperar lease, registrar Builder/Validator no legado,
   alterar porta/volume 8097, reiniciar serviço, usar RDC/GUI,
   tocar HML/STG/PROD ou migrar segredo.
6. Se a execução física ou o Docker estiver indisponível, manter
   `CUTOVER_BLOCKED`, classificar causa e não substituir por mock.

## Próximas etapas separadas
Testar restauração do backup **real** em volume de candidato isolado,
ensaiar rollback físico e comprovar capacidade Builder/Validator,
seguindo `engineering-worker-pool/migration/cutover-policy-v1.json`.
Este incremento não autoriza atualização/cutover ou remoção do legado.
