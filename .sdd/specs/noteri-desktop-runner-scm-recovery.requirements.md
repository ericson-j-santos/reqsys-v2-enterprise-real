# Requisitos — recuperação do runner Desktop via SCM a partir do Noteri

Issue: #1705  
Tipo: `gap_fix`

## Objetivo

Usar um canal Windows nativo e governado, diferente de Task Scheduler/RDC/WinRM/SSH, para verificar e iniciar o serviço já existente do GitHub Actions Runner no `DESKTOP-PDQK954` a partir do `Noteri`. A meta é restaurar o executor necessário para o workflow canônico de atualização do Engineering Orchestrator.

## Requisitos funcionais

1. A execução física DEVE ocorrer somente no host `Noteri`, Windows X64, ambiente `reqsys-dev`.
2. O destino DEVE ser constante `DESKTOP-PDQK954`; nenhum input pode alterar host, serviço ou comando.
3. O transporte DEVE ser a API nativa do Windows Service Control Manager (SCM) remoto.
4. A descoberta DEVE considerar somente serviços cujo nome/display contenha `actions.runner` ou `github actions runner`.
5. Zero serviços encontrados DEVE falhar fechado com `runner_service_not_found`.
6. Mais de um serviço encontrado DEVE falhar fechado com `runner_service_ambiguous`.
7. Se o serviço já estiver `running`, a execução DEVE ser idempotente e não reiniciá-lo.
8. Se estiver `stopped`, a execução PODE chamar somente `StartServiceW` para o serviço único descoberto e deve aguardar no máximo 20 segundos pela leitura independente `running`.
9. Estados diferentes de `stopped`, `start_pending` e `running` DEVEM falhar fechados.
10. A evidência NÃO DEVE persistir lista de serviços, credenciais, tokens, command line, caminho binário ou dados de processo.
11. A evidência DEVE registrar correlation_id, origem, destino, transporte, serviço único, estados antes/depois, changed, timestamp e marcadores de segurança.
12. A execução NÃO DEVE usar RDC, GUI, WinRM, SSH, PowerShell Remoting, criação/alteração de serviço, alteração de ACL, firewall, reboot ou produção.
13. A recuperação DEVE reutilizar o workflow Noteri já existente, permanecer inputless, executar somente no runner Noteri allowlisted e publicar artifact sanitizado quando a ação física for tentada.
14. A mudança é descartável/diagnóstica e não autoriza merge automático.

## Controles contra falso positivo

- `StartServiceW` aceito não comprova sucesso; a pós-condição é nova leitura de estado `running`.
- Serviço já em execução deve retornar `changed=false`.
- Ausência/ambiguidade de serviço nunca pode escolher um alvo por heurística.
- `ERROR_ACCESS_DENIED` deve ser evidenciado por código sanitizado e encerrar sem fallback.
- O artifact deve pertencer ao SHA e correlation_id da execução atual.

## Validação

- Testes: `tests/test_noteri_desktop_runner_scm_recovery.py`, governança self-hosted e SDD.
- E2E físico: job SCM condicionado à branch `fix/noteri-desktop-runner-scm-recovery-*` no workflow existente `noteri-desktop-network-probe.yml`.
- Após sucesso, a fonte independente é a retomada do runner Desktop e a capacidade do workflow `PC24x7 Orchestrator DEV Recovery` ser assumido pelo host correto.

## Critérios de aceite

1. O script é idempotente e fixo Noteri→Desktop.
2. Ações remotas se limitam a enumeração sanitizada e `StartServiceW` do único runner.
3. O workflow produz artifact terminal em sucesso ou bloqueio.
4. Em sucesso, o runner Desktop volta a assumir jobs e habilita a atualização canônica do Orchestrator.
5. Em bloqueio, nenhuma outra rota determinística é repetida automaticamente.
