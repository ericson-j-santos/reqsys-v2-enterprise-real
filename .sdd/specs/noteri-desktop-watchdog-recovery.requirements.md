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
18. No Noteri, `${{ github.workspace }}` é somente a fonte transitória exata do Session Launcher; as regras ficam em `_rules` e a execução técnica deve ser materializada pelo launcher em worktree governado sob `C:\\dev\\chatgpt-workers`, sem depender de clone persistente `C:\\dev\\reqsys-v2-enterprise-real`.
19. O script de recuperação deve ser resolvido a partir do `target_path` retornado pelo Session Launcher, não da raiz do workspace.
20. Antes de qualquer invocação Python, cada modo físico deve preparar CPython 3.12.10 embeddable x64 oficial em `RUNNER_TEMP`, baixado de `python.org`, validado pelo SHA-256 `4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3` antes da extração e executado diretamente sem instalador, registro, toolcache, UAC ou dependência do PATH do host. `actions/setup-python` permanece proibido nesses runners de recovery.\n21. Os modos `watchdog`, `runner-recover`, `runner-bootstrap` e `runner-canary` devem usar `session_launcher.py --require-runner-version-preflight`, registrando a versão real do GitHub Actions runner antes do Command Gateway.

## Critérios de aceite

- workflow usa Python 3.12.10 embeddable oficial validado por SHA-256, sem instalar runtime no host, e executa no Noteri após sessão válida, por Command Gateway risco 2;
- checkout transitório aceito somente como fonte do bootstrap, com execução posterior no worktree governado e sem dependência de `C:\\dev\\reqsys-v2-enterprise-real` no Noteri;
- consulta encontra a tarefa exata;
- AtStartup + S4U são comprovados;
- `/Run` retorna sucesso;
- novo workflow self-hosted do Desktop faz pickup.


## Regras canônicas atuais

O workflow deve usar o SHA canônico atual
`562fc4274aff24f7058cb135f27a509aa69031c1` em todos os modos
`watchdog`, `runner-recover`, `runner-bootstrap` e `runner-canary`.
Pin histórico de regras é bloqueio de execução física.
