# Requisitos — recuperação local do watchdog Desktop

## Objetivo

Quando o runner GitHub do DESKTOP-PDQK954 estiver disponível, usá-lo para consultar e iniciar localmente a tarefa Windows já existente `\Automation\ReqSysDesktopControlPlaneWatchdog`. A rota local substitui o RPC `schtasks /S`, que depende de autorização administrativa remota não fornecida pelo workflow. Quando o runner estiver indisponível, a recuperação continua pertencendo ao modo separado `runner-recover`, via Orchestrator governado.

## Restrições

1. O executor é exclusivamente o runner self-hosted do host `DESKTOP-PDQK954`, com labels `[self-hosted, Windows, X64, pc24x7, reqsys-dev]`.
2. O host local e destino são fixos: `DESKTOP-PDQK954`.
3. A única tarefa permitida é `\Automation\ReqSysDesktopControlPlaneWatchdog`.
4. A execução usa `schtasks.exe` local, sem `/S` e sem credenciais fornecidas pelo workflow.
5. O script pode executar somente `/Query` e `/Run`; `/Create`, `/Change` e `/Delete` são proibidos.
6. Antes de `/Run`, a leitura XML deve comprovar `BootTrigger` e `LogonType=S4U`.
7. Falha de autorização local, ausência da tarefa ou configuração divergente deve falhar fechado.
8. Nenhum segredo, deploy, produção, reboot, RBAC ou bypass de UAC é permitido.
9. A evidência registra `execution_mode=local_pc24x7_runner`, `remote_access_attempted=false` e o resultado sem persistir XML bruto.
10. O Authorized Actions Gateway expõe somente o comando exato `/reqsys run noteri-desktop-watchdog-recovery`.
11. Sem pickup do runner Desktop, o gateway cancela o run abandonado e registra `SELF_HOSTED_RUNNER_UNAVAILABLE`; a recuperação do listener usa o modo separado `runner-recover`.
12. O próprio job deve comprovar pickup no host Desktop exato antes de operar a tarefa.
13. Os passos DEV usam `shell: powershell`, compatível com o runner Desktop evidenciado; `pwsh` não é requisito.
14. Antes da operação local, o workflow materializa sessão governada por `session_launcher.py` no SHA exato do ReqSys e exige `SESSION_LAUNCH_OK` + `state_validated=true`.
15. O script executa exclusivamente por `command_gateway.py`, risco 2, dentro do `target_path` isolado e com `expected-head` igual ao SHA da execução.
16. As regras operacionais usadas no E2E são fixadas por SHA imutável e o checkout não persiste credenciais.
17. Antes do upload, a evidência deve comprovar origem/destino DESKTOP-PDQK954, modo local, `EXISTING_DESKTOP_WATCHDOG_RUN_REQUESTED`, sem acesso remoto, criação/alteração de tarefa, segredo, credencial ou produção.
18. No Desktop, o clone governado `C:\dev\reqsys-v2-enterprise-real` é a fonte do Session Launcher; a execução é materializada sob `C:\dev\chatgpt-workers`. O checkout do runner em `%LOCALAPPDATA%` não pode ser `target_repo`.
19. O script de recuperação é resolvido a partir do `target_path` retornado pelo Session Launcher, não da raiz do workspace.
20. Cada modo físico prepara CPython 3.12.10 embeddable x64 oficial em `RUNNER_TEMP`, validado pelo SHA-256 `4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3`, sem instalador, registro, toolcache, UAC ou dependência do PATH. `actions/setup-python` permanece proibido.
21. Os modos `watchdog`, `runner-recover`, `runner-bootstrap` e `runner-canary` usam `session_launcher.py --require-runner-version-preflight` antes do Command Gateway.
22. O modo `watchdog` não pode emitir `schtasks /S`; o bloqueio `Acesso negado` do RPC remoto não pode voltar a ser dependência dessa operação.

## Critérios de aceite

- Python 3.12.10 embeddable oficial validado por SHA-256, sem instalar runtime no host;
- execução no Desktop após sessão válida, por Command Gateway risco 2;
- clone canônico do Desktop usado somente como fonte do bootstrap, com execução no worktree governado;
- consulta local encontra a tarefa exata e comprova AtStartup + S4U;
- `/Run` local retorna sucesso sem tentar RPC remoto;
- o job comprova pickup no runner Desktop exato.

## Regras canônicas atuais

O workflow usa o SHA canônico `562fc4274aff24f7058cb135f27a509aa69031c1` nos modos `watchdog`, `runner-recover`, `runner-bootstrap` e `runner-canary`. Pin histórico de regras é bloqueio de execução física.
