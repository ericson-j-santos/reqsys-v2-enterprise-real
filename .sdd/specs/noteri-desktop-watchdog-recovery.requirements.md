# Requisitos — recuperação do watchdog Desktop via Noteri

## Objetivo

Quando o DESKTOP-PDQK954 estiver com RDC e runner GitHub simultaneamente indisponíveis, usar o Noteri apenas para consultar e iniciar a tarefa Windows já existente `\Automation\ReqSysDesktopControlPlaneWatchdog`.

## Restrições

1. O executor é exclusivamente o runner self-hosted do host `Noteri`.
2. O destino é fixo: `DESKTOP-PDQK954`.
3. A única tarefa permitida é `\Automation\ReqSysDesktopControlPlaneWatchdog`.
4. O transporte usa `schtasks.exe /S` nativo do Windows, sem credenciais fornecidas pelo workflow.
5. O script pode executar somente `/Query` e `/Run`; `/Create`, `/Change` e `/Delete` são proibidos.
6. Antes de `/Run`, a leitura XML deve comprovar `BootTrigger` e `LogonType=S4U`.
7. Falha de RPC, autorização, ausência da tarefa ou configuração divergente deve falhar fechado.
8. Nenhum segredo, deploy, produção, reboot, RBAC ou bypass de UAC é permitido.
9. Evidência registra reachability TCP 135/445 e resultado sem persistir XML bruto.
10. O Authorized Actions Gateway expõe somente o comando exato `/reqsys run noteri-desktop-watchdog-recovery`.
11. Sem pickup do Noteri, o gateway cancela o run abandonado e registra `SELF_HOSTED_RUNNER_UNAVAILABLE`.
12. Após sucesso, E2E independente deve comprovar pickup do runner Desktop.
13. Os passos PowerShell do workflow DEV devem usar `shell: powershell`, compatível com o runner Noteri evidenciado; `pwsh` não é requisito do host.

14. Antes de executar o RPC, o workflow deve materializar sessão governada por `session_launcher.py` no SHA exato do ReqSys e exigir `SESSION_LAUNCH_OK` + `state_validated=true`.
15. O script de recuperação deve executar exclusivamente por `command_gateway.py`, risco 2, dentro do `target_path` isolado e com `expected-head` igual ao SHA da execução.
16. As regras operacionais usadas no E2E devem ser fixadas por SHA imutável e o checkout não pode persistir credenciais.
17. A evidência produzida no worktree deve ser validada antes do upload: origem Noteri, destino DESKTOP-PDQK954, `EXISTING_DESKTOP_WATCHDOG_RUN_REQUESTED`, sem criação/alteração de tarefa, segredo, credencial ou produção.

## Critérios de aceite

- workflow executa no Noteri após Session Launcher válido e por Command Gateway risco 2;
- consulta encontra a tarefa exata;
- AtStartup + S4U são comprovados;
- `/Run` retorna sucesso;
- novo workflow self-hosted do Desktop faz pickup.
