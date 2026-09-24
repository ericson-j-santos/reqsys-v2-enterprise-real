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

