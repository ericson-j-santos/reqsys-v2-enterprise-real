# Requisitos — diagnóstico Noteri → Desktop sem RDC/runner

Issue: #1899  
Tipo: `gap_fix`

## Objetivo

Permitir que o Noteri produza evidência independente e sanitizada sobre a disponibilidade de rede do `DESKTOP-PDQK954` quando o runner e o RDC do Desktop não puderem ser usados.

## Requisitos funcionais

1. A execução física DEVE ocorrer somente no host `Noteri`, Windows X64, ambiente `reqsys-dev`.
2. O destino DEVE ser constante `DESKTOP-PDQK954`; nenhum input externo pode alterar o host.
3. A sonda DEVE resolver o nome do Desktop sem persistir endereços IP brutos.
4. A sonda DEVE executar ICMP com `PING.EXE` por argv fixo, `shell=False`, limite de tempo finito e sem imprimir a saída do comando.
5. A sonda DEVE testar a porta DEV fixa `8081` por socket TCP com limite de tempo finito.
6. O resultado DEVE distinguir pelo menos:
   - `name_resolution_failed`;
   - `resolved_not_reachable`;
   - `host_reachable_runtime_port_closed`;
   - `runtime_port_reachable`.
7. Indisponibilidade do destino é um resultado diagnóstico terminal; erro de contrato/host de origem deve falhar fechado.
8. A evidência DEVE registrar `correlation_id`, origem, destino, estado de rede, sinais booleanos, timestamp e os marcadores `rdc_required=false`, `production_touched=false`, `secrets_read=false`.
9. A sonda NÃO DEVE usar GUI, teclado, clipboard, coordenadas, credenciais, alteração de firewall, reboot ou shutdown.
10. O workflow DEVE ser inputless por `workflow_dispatch` e também executar na branch dedicada quando os arquivos desta capacidade forem alterados, permitindo E2E antes da PR.
11. O Authorized Actions Gateway DEVE expor somente o comando exato `/reqsys run noteri-desktop-network-probe`, fixo em `main`.
12. Wake-on-LAN NÃO faz parte deste incremento.

## Controles contra falso positivo

- DNS resolvido sem ICMP/TCP não pode ser reportado como host alcançável.
- Porta 8081 aberta comprova reachability mesmo se ICMP estiver bloqueado.
- ICMP positivo com porta fechada deve permanecer distinguível.
- O artifact não deve conter endereços IP resolvidos nem stdout/stderr de `PING.EXE`.
- Host diferente de Noteri ou confirmação divergente deve retornar erro.

## Validação

- Testes: `tests/test_noteri_desktop_network_probe.py`, `tests/test_reqsys_authorized_actions_gateway.py`, `tests/test_self_hosted_runner_governance.py`.
- Pre-PR Readiness deve retornar `READY_FOR_PR=passed` no HEAD exato.
- E2E físico deve produzir artifact no Noteri e ser lido independentemente.
- Nenhuma evidência de outro SHA pode liberar a PR.
