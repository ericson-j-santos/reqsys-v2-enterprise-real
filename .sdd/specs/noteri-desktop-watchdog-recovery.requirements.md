# Requisitos — recuperação local do watchdog Desktop

## Objetivo

Quando o runner GitHub do DESKTOP-PDQK954 estiver disponível, usá-lo para consultar e iniciar localmente a tarefa Windows `\Automation\ReqSysDesktopControlPlaneWatchdog`. Se a tarefa exata estiver ausente, o mesmo fluxo pode reparar somente essa tarefa com runtime persistente verificado e registro local sem senha. A rota local substitui o RPC `schtasks /S`, que depende de autorização administrativa remota não fornecida pelo workflow. Quando o runner estiver indisponível, a recuperação continua pertencendo ao modo separado `runner-recover`, via Orchestrator governado.

## Restrições

1. O executor é exclusivamente o runner self-hosted do host `DESKTOP-PDQK954`, com labels `[self-hosted, Windows, X64, pc24x7, reqsys-dev]`.
2. O host local e destino são fixos: `DESKTOP-PDQK954`.
3. A única tarefa permitida é `\Automation\ReqSysDesktopControlPlaneWatchdog`.
4. A execução usa `schtasks.exe` local, sem `/S` e sem credenciais fornecidas pelo workflow.
5. O caminho normal pode executar somente `/Query` e `/Run`. Apenas quando a consulta indicar inequivocamente tarefa ausente, uma reparação pode executar `/Create` para o nome exato com `/SC ONSTART /RL LIMITED /NP /F`; `/Change`, criação arbitrária e acesso remoto permanecem proibidos.
6. Antes de `/Run`, inclusive após reparação, a leitura XML independente deve comprovar tarefa habilitada, `BootTrigger` e `LogonType=S4U`.
7. Falha de autorização local, erro de consulta diferente de tarefa ausente ou configuração divergente deve falhar fechado sem tentativa de reparação.
8. Nenhum segredo, deploy, produção, reboot, RBAC ou bypass de UAC é permitido.
9. A evidência registra `execution_mode=local_pc24x7_runner`, `remote_access_attempted=false` e o resultado sem persistir XML bruto.
10. O Authorized Actions Gateway expõe somente o comando exato `/reqsys run noteri-desktop-watchdog-recovery`.
11. Sem pickup do runner Desktop, o gateway cancela o run abandonado e registra `SELF_HOSTED_RUNNER_UNAVAILABLE`; a recuperação do listener usa o modo separado `runner-recover`.
12. O próprio job deve comprovar pickup no host Desktop exato antes de operar a tarefa.
13. Os passos DEV usam `shell: powershell`, compatível com o runner Desktop evidenciado; `pwsh` não é requisito.
14. Antes da operação local, o workflow materializa sessão governada por `session_launcher.py` no SHA exato do ReqSys e exige `SESSION_LAUNCH_OK` + `state_validated=true`.
15. O script executa exclusivamente por `command_gateway.py`, risco 2, dentro do `target_path` isolado e com `expected-head` igual ao SHA da execução.
16. As regras operacionais usadas no E2E são fixadas por SHA imutável e o checkout não persiste credenciais.
17. Antes do upload, a evidência deve comprovar origem/destino DESKTOP-PDQK954, modo local, `EXISTING_DESKTOP_WATCHDOG_RUN_REQUESTED`, sem acesso remoto, segredo, credencial ou produção; eventual criação deve estar marcada como reparação tentada e verificada da tarefa exata.
18. No Desktop, o clone dedicado limpo `C:\dev\chatgpt-workers\reqsys-watchdog-session-source` é a fonte do Session Launcher; ele é criado do checkout imutável, vinculado ao remoto canônico e validado contra `origin/main` no SHA exato antes da sessão. O checkout do runner em `%LOCALAPPDATA%` e o clone operacional divergente não podem ser `target_repo`.
19. O script de recuperação é resolvido a partir do `target_path` retornado pelo Session Launcher, não da raiz do workspace.
20. Cada modo físico prepara CPython 3.12.10 embeddable x64 oficial em `RUNNER_TEMP`, validado pelo SHA-256 `4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3`, sem instalador, registro, toolcache, UAC ou dependência do PATH. `actions/setup-python` permanece proibido.
21. Os modos `watchdog`, `runner-recover`, `runner-bootstrap` e `runner-canary` usam `session_launcher.py --require-runner-version-preflight` antes do Command Gateway.
22. O modo `watchdog` não pode emitir `schtasks /S`; o bloqueio `Acesso negado` do RPC remoto não pode voltar a ser dependência dessa operação.
23. O workflow deve copiar o CPython 3.12.10 já validado para `%LOCALAPPDATA%\ReqSys\DesktopControlPlaneWatchdog\python\3.12.10` apenas quando ausente e revalidar sua versão; runtime íntegro existente não pode ser substituído.
24. A reparação deve instalar a release imutável no SHA da execução, apontar para o runner local fixo e aceitar sucesso somente com `headless_boot_ready=true`.
25. O modo explícito `watchdog-uac` pode chamar somente `desktop_control_plane_watchdog_uac_launcher.py`, com confirmação fixa, metadata governada e timeout limitado; a aprovação visual do Windows continua obrigatória e nenhum bypass de UAC é permitido.
26. Se a elevação não puder ser apresentada pela sessão do runner, o modo `watchdog-uac-stage` deve criar `Ativar-ReqSys-Watchdog.cmd`, seu launcher PowerShell e uma cópia do reparador nativo exclusivo do watchdog vinculada ao SHA imutável da execução no Desktop do perfil do runner, tentando as mesmas cópias no Desktop público; o reparo não pode depender do Desktop Admin Broker, deve elevar e aguardar o Task Scheduler COM, validar seu diagnóstico local e manter a aprovação UAC humana obrigatória. Caminhos criados, eventual recusa pública e o último diagnóstico nativo sanitizado, quando existente, devem constar da evidência.

## Critérios de aceite

- Python 3.12.10 embeddable oficial validado por SHA-256, sem instalar runtime no host;
- execução no Desktop após sessão válida, por Command Gateway risco 2;
- clone dedicado limpo do Desktop usado somente como fonte do bootstrap, com execução no worktree governado;
- consulta local encontra ou repara a tarefa exata e comprova `Enabled=true`, AtStartup + S4U;
- `/Run` local retorna sucesso sem tentar RPC remoto;
- o job comprova pickup no runner Desktop exato.

## Regras canônicas atuais

O workflow usa o SHA canônico `562fc4274aff24f7058cb135f27a509aa69031c1` nos modos `watchdog`, `runner-recover`, `runner-bootstrap` e `runner-canary`. Pin histórico de regras é bloqueio de execução física.

## Readback manual separado, sem recuperação — 2026-10-22

O modo adicional watchdog-readback não altera os modos anteriores e não é acionado por push, PR ou schedule.
Ele usa o mesmo workflow já allowlisted, o SHA exato da execução, CPython portátil validado, regras
canônicas fabaccc32abbbf6f95be443629ef2ebb1246dad5, Session Launcher com preflight de versão e Command Gateway.
A classificação Risk 2 cobre exclusivamente o recibo escrito no worktree isolado; o runtime observado não é alterado.

- Host e runner: DESKTOP-PDQK954; repositório: ericson-j-santos/reqsys-v2-enterprise-real.
- Consultar somente XML/CSV da tarefa fixa; observar separadamente Enabled, BootTrigger habilitado,
  LogonType e LastTaskResult numérico. Nunca assumir zero quando idioma/campo não for reconhecido.
- O serviço SCM é uma sonda do nome candidato fixo, não descoberta de todos os serviços nem prova
  da identidade executável. Usar somente CONNECT/QUERY_STATUS, sem ler configuração ou contas.
- Ler somente o state.json fixo do watchdog, com limite de tamanho, rejeição de reparse ancestral e
  allowlist de campos tipados. Não ler metadata.json, .runner, .service, .env ou credenciais.
- Não publicar XML/CSV/JSON bruto, caminhos, mensagens de exceção ou campos desconhecidos.
- Não executar /Run, repair, restart, install, recuperação RDC, atualização do runtime ou acesso externo.
- Registrar coleta parcial quando metadados estiverem indisponíveis. Probe concluído não significa
  watchdog saudável, serviço ausente globalmente, release instalada atual, boot validado ou ciclos contínuos.
- A identidade e os ciclos do produtor ReqSys permanecem não verificados por esta lane.
- CI deve executar testes positivos, negativos, idioma, dados malformados, identidade, ausência,
  reparse e ausência de efeitos mutantes. O teste físico só pode ocorrer por dispatch revisado separado.

Autorização de incremento: Agent Increment Gate 39843440443, hotfix com referência 3051,
allowed=true. Esta evidência não autoriza merge nem substitui READY_FOR_PR no novo HEAD.

## Reparo nativo da tarefa existente — 2026-10-28

A sonda física após a PR #3114 confirmou que a tarefa watchdog existe. O contrato de runtime
passou; no contrato da tarefa, somente `runlevel_limited` e `command_matches` falharam.
O modo normal continua restrito à reparação de tarefa ausente. Para esse drift específico,
o reparador nativo distribuído por `watchdog-uac-stage` é a rota de execução administrativa.

- O staging copia o reparador e os launchers; ele não registra tarefa nem apresenta UAC.
- O reparador exige host e nome da tarefa fixos, metadata local coerente e Python instalado
  dentro de `LOCALAPPDATA`. A tarefa deve existir, com S4U, trigger de boot, uma ação executável, argumentos,
  diretório de trabalho e habilitação já conformes. Exatamente runlevel e comando devem divergir.
- A atualização usa `TASK_UPDATE`, conserva `Principal.UserId`, senha nula, S4U e privilégio
  limitado. Se a tarefa desaparecer ou mudar entre sonda e execução, falha fechado.
- Antes da mutação, conserva a definição e o XML anteriores. Depois, relê todos os campos do
  contrato. Se registro, releitura ou início falhar, tenta restaurar a definição anterior e
  registra somente resultado sanitizado e se o rollback foi verificado.
- Merge, staging físico e execução UAC requerem suas autorizações específicas conforme as
  regras operacionais. Não há reinício, produção, credencial ou enfileiramento da ReqSys #3096.

Autorização de incremento: Agent Increment Gate 40618872254, gap_fix, permitido na main
`f92a60d944b2986121311b9a05071e6b587590d1`. A evidência não autoriza merge ou UAC.

### Ajuste do Python instalado após a primeira tentativa de staging

O run 40620510939 falhou em `WATCHDOG_PYTHON_PATH_MISMATCH` antes de copiar qualquer
launcher. O instalador aceita `python_executable` resolvido nos metadados locais; portanto,
o staging e o reparador devem usar esse mesmo caminho, limitado ao `LOCALAPPDATA` do host.
O staging ainda exige arquivo existente, release coerente e versão exata Python 3.12.10.
Se o caminho estiver fora de `LOCALAPPDATA`, falha fechado e publica recibo sanitizado;
nenhuma tarefa é modificada ou UAC iniciado. A execução elevada continua separada.

### Diagnóstico da pré-condição nativa

Após a tentativa local de 2026-10-28, o reparador retornou
`WATCHDOG_DRIFT_PROFILE_CHANGED` sem modificar a tarefa. O recibo privado deve
incluir os booleanos de `Get-TaskContract` observados antes da mutação, para
identificar a condição divergente. XML, caminhos, identidade e valores de
credenciais não podem ser serializados. O reparador deve continuar bloqueando
qualquer drift fora do perfil aprovado.

**Critérios de aceite:** a tentativa bloqueada registra `precheck_checks` apenas
com booleanos; `registration_attempted=false`; a tarefa permanece inalterada;
os testes de escopo e reversão continuam passando.

O staging de leitura deve transportar esses oito booleanos do diagnóstico local
para o artifact privado por lista fechada, rejeitando campos ausentes ou de tipo
inesperado. Se o diagnóstico for anterior à inclusão de `precheck_checks`, o
campo pode permanecer nulo. O staging não executa reparo ou UAC.

O recibo da tentativa local de 2026-10-28 às 17:40 UTC mostrou
`runlevel_limited=true` e `command_matches=false`, com os outros seis campos
verdadeiros. O reparador deve aceitar também esse perfil de divergência de um
único campo, preservando os mesmos bloqueios para argumentos, diretório,
gatilho, identidade S4U, ação e estado da tarefa. O pós-check completo e o
rollback permanecem obrigatórios.


