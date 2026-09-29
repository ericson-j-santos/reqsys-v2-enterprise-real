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
8. Em `workflow_dispatch` na `main`, a sonda HTTP DEV também DEVE executar no mesmo SHA; o diagnóstico legado pode executar em paralelo para preservar evidência independente de reachability.
9. A evidência aceita os estados `name_resolution_failed`, `dev_gateway_tcp_closed`, `dev_gateway_http_reachable` e `dev_gateway_tcp_reachable_http_unresponsive`.
10. Status HTTP válido comprova somente transporte/aplicação alcançável; não comprova capacidade de recuperação até existir endpoint fixo, autenticado e allowlisted para esse fim.
11. Erros persistidos devem ser sanitizados e nunca conter texto bruto de exceção.

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


## P0 Pareto — acionamento direto do recovery permanente

Para evitar ciclos de bootstrap quando o runner já está registrado, a rota governada
principal passa a expor o recovery permanente já existente.

1. O workflow `.github/workflows/noteri-desktop-watchdog-recovery.yml` aceita somente
   o novo modo enumerado `runner-recover`, sem input livre.
2. Esse modo reutiliza exclusivamente
   `scripts/noteri_desktop_orchestrator_runner_recovery.py` e a capability fixa
   `host.github_runner.recover.v1`.
3. O Authorized Actions Gateway aceita somente o comando exato
   `/reqsys run desktop-runner-recover-via-orchestrator`, mapeado para
   `noteri-desktop-watchdog-recovery.yml` com `mode=runner-recover`.
4. O fluxo continua exigindo Session Launcher, Command Gateway, SHA exato,
   replay idempotente, controle negativo 404 e leitura independente.
5. Bootstrap permanece contingência apenas quando o recovery retornar alvo de runner
   inexistente; ele não é pré-requisito do recovery.
6. Sucesso terminal exige recovery local válido seguido de pickup físico independente
   no Desktop; sucesso de transporte isolado não conclui a recuperação.

## P0 29/09/2026 — readback somente leitura do Orchestrator `:8787`

Para separar indisponibilidade de rede de ausência de listener/capability sem repetir
recovery cego, o diagnóstico passa a incluir um readback fixo do Engineering
Orchestrator já instalado no Desktop.

1. A execução física DEVE ocorrer somente no `Noteri`, no SHA exato, por
   `Session Launcher → Command Gateway`.
2. O destino é fixo em `http://DESKTOP-PDQK954:8787`; não há input de host,
   porta, URL, worker ou task type.
3. A sonda usa somente `GET /readyz` e `GET /v1/status`, sem corpo mutante,
   credenciais fornecidas, shell remoto ou leitura de segredos.
4. O worker alvo é exatamente `desktop-pdqk954`; zero ou múltiplas
   correspondências não podem ser tratadas como identidade válida.
5. A evidência registra `ready`, status HTTP, identidade do worker,
   `fresh`, `eligible`, versão do controller, perfil, capabilities,
   `runtime_source_sha` e `worker_instance_id`, sem persistir payload bruto.
6. O SHA esperado do runtime do Orchestrator é fixado no SHA corrente
   `313f5da4bb0ee9dd70937c238c7cfdf4e3514602`.
7. O workflow usa Python portátil 3.12.10 fixado por SHA-256 para evitar
   dependência do Python global do runner e deve chamar Session Launcher e
   Command Gateway explicitamente por esse interpretador.
8. A execução no Command Gateway usa risco 2 exclusivamente porque a sonda grava
   o artifact sanitizado no worktree; a operação remota permanece somente leitura.
9. A sonda é somente diagnóstico: `ready=true` ou presença de capability não
   conclui recovery; pickup físico independente do Desktop continua obrigatório.
10. Falha de conexão/status deve produzir evidência sanitizada e nunca autorizar
   fallback por WMI, SCM, schtasks, C$, Admin Broker, RDC, SSH, WinRM ou GUI.
11. O teste `tests/test_noteri_desktop_orchestrator_status_probe.py` deve
    cobrir identidade fixa, leitura positiva, worker duplicado e contrato do
    workflow com o Python portátil.
12. O job genérico de network probe DEVE ser ignorado nas branches
    `fix/noteri-desktop-orchestrator-status-*` para impedir contenção do mesmo
    runner Noteri e falso `SELF_HOSTED_RUNNER_PICKUP_TIMEOUT_OR_BUSY`.

### Critério para avançar

Somente readback atual e inequívoco do `:8787`, no SHA corrente, permite escolher
entre recovery e bootstrap. Depois da ação escolhida, o critério terminal permanece
pickup físico independente do runner Desktop, versão/registro/listener comprovados
e replay idempotente sem nova mutação.
