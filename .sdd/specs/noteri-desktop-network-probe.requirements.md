# Requisitos — diagnóstico Noteri → Desktop sem RDC/runner

Issue: #1899  
Tipo: \`gap_fix\`

## Objetivo

Produzir no Noteri evidência independente, sanitizada e somente leitura sobre a disponibilidade do \`DESKTOP-PDQK954\`, incluindo uma sonda WMI/DCOM nativa que determine se a identidade atual possui acesso remoto de leitura sem recorrer a shell remoto, credenciais fornecidas, GUI ou RDC.

## Requisitos funcionais

1. A execução física DEVE ocorrer somente no host \`Noteri\`, Windows X64, ambiente \`reqsys-dev\`.
2. O destino DEVE permanecer constante \`DESKTOP-PDQK954\`; nenhum input externo pode alterar o host.
3. DNS deve ser resolvido sem persistir endereços IP brutos.
4. ICMP deve usar \`PING.EXE\` por argv fixo, \`shell=False\`, timeout finito e sem persistir stdout/stderr.
5. A porta DEV fixa \`8081\` deve ser testada por socket TCP com timeout finito.
6. O caminho administrativo fixo \`C:\\Users\\Public\\Desktop\` pode ser sondado apenas por leitura via \`C$\`, sem persistir listagem nem gravar conteúdo.
7. A sonda WMI/DCOM deve usar a identidade Windows corrente do Noteri, sem usuário/senha/token; conectar somente a \`DESKTOP-PDQK954/root\\cimv2\`; executar somente \`SELECT Caption FROM Win32_OperatingSystem\`; e não persistir nenhum dado retornado.
8. Resultados WMI permitidos: \`accessible\`, \`empty_result\`, \`access_denied\`, \`rpc_server_unavailable\`, \`namespace_unavailable\`, \`dependency_unavailable\` ou \`wmi_error\`.
9. A sonda NÃO DEVE usar \`Win32_Process.Create\`, método WMI de mutação, PowerShell Remoting, WinRM, SSH, RDP, GUI, clipboard, alteração de firewall, reboot ou shutdown.
10. \`desktop_reachable=true\` pode ser comprovado por TCP 8081, ICMP ou WMI acessível.
11. O workflow deve executar a sonda por \`Session Launcher → Command Gateway\`, com SHA exato e sessão validada.
12. Testes são risco 1. A sonda é risco 2 somente porque grava o artifact local dentro do worktree; a operação remota WMI permanece estritamente somente leitura.
13. O workflow deve ser inputless por \`workflow_dispatch\` e executar na branch dedicada \`fix/noteri-desktop-network-probe-*\`.
14. O Authorized Actions Gateway continua expondo somente o comando exato \`/reqsys run noteri-desktop-network-probe\`.
15. A evidência deve registrar \`correlation_id\`, origem, destino, sinais booleanos, classes sanitizadas e \`rdc_required=false\`, \`remote_shell_used=false\`, \`credentials_supplied=false\`, \`production_touched=false\`, \`secrets_read=false\`.

## Controles contra falso positivo

- DNS isolado não comprova reachability.
- WMI só comprova reachability quando uma consulta read-only retorna ao menos uma instância.
- \`access_denied\` comprova que a rota WMI/DCOM alcançou a camada de autorização, mas NÃO autoriza execução remota.
- O artifact não contém endereços IP brutos, conteúdo retornado da consulta WMI, listagem SMB, stdout/stderr do ping ou credenciais.
- Host de origem divergente, confirmação divergente ou sessão não validada falham fechado.
- A implementação contém teste negativo que prova sanitização de \`access_denied\`.
- Nenhum resultado desta sonda permite executar comando remoto; transporte posterior continua sujeito a \`Session Launcher → Command Gateway\`.

## Validação

- Testes: \`tests/test_noteri_desktop_network_probe.py\`, \`tests/test_reqsys_authorized_actions_gateway.py\`, \`tests/test_self_hosted_runner_governance.py\`.
- Pre-PR Readiness deve retornar \`READY_FOR_PR=passed\` no HEAD exato.
- E2E físico deve produzir artifact no Noteri no mesmo SHA.
- O resultado físico deve ser lido independentemente após o workflow.
- Nenhuma evidência de SHA anterior pode liberar a próxima etapa.

## Critérios de aceite e condição para avançar

Somente se \`wmi_result=accessible\` será permitido estudar um adaptador WMI fixo e allowlisted que transporte exclusivamente o bootstrap governado. Qualquer \`access_denied\`, indisponibilidade RPC/DCOM ou dependência ausente encerra a rota WMI sem retry até mudança objetiva da precondição.

## Incremento atual — rota HTTP DEV `:8083`

Após o checkpoint terminal da rota WMI/DCOM, este incremento testa somente uma rota tecnicamente nova e de custo adicional zero: o gateway HTTP DEV já previsto no `DESKTOP-PDQK954:8083`.

1. A execução física ocorre somente no `Noteri` allowlisted e no SHA exato, por `Session Launcher → Command Gateway`.
2. O alvo é fixo em `DESKTOP-PDQK954:8083`; host, porta e paths não aceitam input externo.
3. São permitidos apenas `GET /api/health` e `GET /api/runtime/health`; nenhum corpo de resposta é persistido.
4. A sonda não envia requisição mutante, não fornece credenciais, não lê segredos e não altera UAC, ACL, firewall ou configuração do Desktop.
5. WMI, SCM, Task Scheduler/`schtasks`, `C$` e Admin Broker ficam explicitamente fora desta execução.
6. O job legado permanece preservado para compatibilidade, mas DEVE ser ignorado quando `github.ref_name` iniciar por `fix/noteri-desktop-network-probe-http-8083-`.
7. A branch HTTP executa somente `scripts/noteri_desktop_dev_http_probe.py` e `tests/test_noteri_desktop_dev_http_probe.py`.
8. A evidência aceita os estados `name_resolution_failed`, `dev_gateway_tcp_closed`, `dev_gateway_http_reachable` e `dev_gateway_tcp_reachable_http_unresponsive`.
9. Status HTTP válido comprova somente transporte/aplicação alcançável; não comprova capacidade de recuperação até existir endpoint fixo, autenticado e allowlisted para esse fim.
10. Erros persistidos devem ser sanitizados e nunca conter texto bruto de exceção.

### Critério para avançar

Somente `candidate_transport_reachable=true`, acompanhado de evidência de um endpoint fixo e governado capaz de recuperar o plano de controle sem shell remoto irrestrito, permite avançar esta rota. Caso a porta esteja fechada ou nenhum endpoint de recuperação exista, a rota HTTP é terminal e não deve ser repetida sem mudança objetiva de precondição.

## Hotfix #2088 — recuperação do runner via Engineering Orchestrator `:8787`

O Desktop está ligado e alcançável, porém as rotas WMI/C$, Task Scheduler remoto e
registro GitHub não produziram um canal de recuperação utilizável. O próximo caminho
control-plane-first reutiliza o Engineering Orchestrator já existente.

### Requisitos

1. A origem permanece fixa em `Noteri` e o destino em `DESKTOP-PDQK954:8787`.
2. A única ação mutante permitida é `host.github_runner.recover.v1`.
3. O cliente não aceita host, porta, URL, task type, executável ou shell como input.
4. O Orchestrator deve responder `ready=true` antes do intake.
5. Deve existir exatamente um worker Desktop `fresh`, `NORMAL`,
   `controller_online=true`, `auth_valid=true` e com a capability explícita.
6. O intake usa `event_id`, `correlation_id`, `idempotency_key`, risco 2,
   `max_attempts=1` e lease finito.
7. O dispatch deve apontar ao worker do `DESKTOP-PDQK954`.
8. O work item deve atingir estado terminal dentro do timeout e somente
   `CONCLUÍDO` é sucesso.
9. O resultado deve conter handler `host.github_runner.recover.v1`, host exato e
   resultado `recovered` ou `already_running`.
10. O mesmo intake deve ser repetido e retornar replay sem segundo dispatch.
11. Uma leitura independente do work item deve confirmar o resultado terminal.
12. Um GET deliberadamente inexistente deve retornar 404 como controle negativo.
13. Não usar WMI, C$, RPC Task Scheduler, WinRM, SSH, RDC, GUI ou shell remoto.

### Critérios de aceite

- O teste `tests/test_noteri_desktop_orchestrator_runner_recovery.py` deve passar.
- A execução física deve ocorrer no Noteri, por `Session Launcher → Command Gateway`,
  no SHA exato do hotfix.
- O artifact deve registrar `DESKTOP_GITHUB_RUNNER_RECOVERY_COMPLETED`,
  `replay_idempotent=true`, `negative_read_control=true` e
  `independent_readback=true`.
- `remote_shell_used`, `credentials_supplied`, `secrets_read`,
  `production_touched` e `reboot_performed` devem permanecer `false`.
- Após a recuperação, um pickup GitHub Actions independente do Desktop deve ser
  observado antes de declarar o runner recuperado.


## Hotfix — isolamento do checkout das regras no recovery

Durante a revalidação física do runner Desktop, o job de recovery ficou bloqueado
antes do bootstrap na etapa `actions/checkout` das regras canônicas usando o
diretório estático `_rules` do runner self-hosted persistente.

### Requisitos

1. O job `orchestrator_runner_recovery` deve materializar apenas os arquivos
   canônicos necessários de `chatgpt-operational-rules`, presos ao SHA exato,
   em diretório único por `github.run_id` + `github.run_attempt`.
2. `session_launcher.py`, `command_gateway.py` e a policy devem ser resolvidos
   exclusivamente a partir desse diretório isolado.
3. O SHA das regras continua fixado e deve corresponder à `main` canônica
   revalidada antes da execução.
4. Não é permitido depender de `actions/checkout` cross-repo para essa
   materialização; cada arquivo deve ter seu Git blob SHA esperado validado antes
   do uso, e qualquer divergência deve falhar fechado.
5. A mudança não amplia alvo, task type, risco, permissões, shell ou escopo do
   recovery; permanece somente `DESKTOP-PDQK954:8787` e
   `host.github_runner.recover.v1`.

### Critério de aceite

- o teste de contrato deve exigir materialização por blobs pinados e rejeitar
  regressão para checkout cross-repo no job de recovery;
- o run físico deve ultrapassar a etapa de checkout das regras e alcançar o
  bootstrap governado;
- sucesso final continua exigindo artifact sanitizado do recovery e pickup
  GitHub Actions independente no Desktop.


## Hotfix — bootstrap governado do runner após recovery bloqueado

Após o Desktop voltar a expor o Engineering Orchestrator em `:8787`, a
capability `host.github_runner.recover.v1` atingiu estado terminal
`BLOQUEADO`. O handler de recovery só aceita serviço automático ou tarefa de
boot existente; portanto o próximo incremento usa a capability permanente
`host.github_runner.bootstrap.v1`, já prevista no contrato do Orchestrator.

### Requisitos

1. Origem fixa: `Noteri`; destino fixo: `DESKTOP-PDQK954:8787`.
2. A execução deve usar `Session Launcher -> Command Gateway`, risco 2 e SHA
   exato do hotfix.
3. As regras canônicas devem ser materializadas por blobs pinados, sem checkout
   cross-repo persistente.
4. O script autorizado é somente
   `scripts/desktop_runner_bootstrap_via_orchestrator.py`.
5. Se `bootstrap.v1` ainda não estiver anunciado, o próprio contrato pode usar
   somente `host.orchestrator.refresh.v1` com SHA fixo
   `d44c9f0e64705fa50f7798cb7ff41afbea668784`.
6. Evidência deve ficar em `RUNNER_TEMP`, fora do worktree governado.
7. Sucesso local exige `DESKTOP_GITHUB_RUNNER_LOCAL_BOOTSTRAP_VERIFIED`,
   `local_listener_verified=true`, replay idempotente e
   `pickup_required=true`.
8. O bootstrap local não comprova conectividade GitHub; conclusão terminal exige
   pickup físico independente no runner `DESKTOP-PDQK954`.

### Critério de aceite

Depois do bootstrap local, repetir somente o benchmark físico 64K do PR
`desktop-pc24x7-runtime#27` no HEAD corrente e exigir aquisição pelo runner
Desktop antes de considerar a recuperação concluída.
