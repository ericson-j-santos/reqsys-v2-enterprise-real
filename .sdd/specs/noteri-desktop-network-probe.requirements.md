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
13. A sonda DEVE testar somente leitura no caminho administrativo fixo `C:\\Users\\Public\\Desktop` via `C# Requisitos — diagnóstico Noteri → Desktop sem RDC/runner

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
, sem enumerar/persistir nomes de arquivos e sem gravar qualquer conteúdo.
14. O resultado DEVE distinguir `accessible`, `access_denied`, `not_found` e erro de sistema sanitizado para esse caminho.

## Controles contra falso positivo

- DNS resolvido sem ICMP/TCP não pode ser reportado como host alcançável.
- Porta 8081 aberta comprova reachability mesmo se ICMP estiver bloqueado.
- ICMP positivo com porta fechada deve permanecer distinguível.
- O artifact não deve conter endereços IP resolvidos nem stdout/stderr de `PING.EXE`.
- Host diferente de Noteri ou confirmação divergente deve retornar erro.
- O probe SMB não pode criar, alterar ou excluir arquivos; a evidência registra apenas acessibilidade e classe de erro.

## Validação

- Testes: `tests/test_noteri_desktop_network_probe.py`, `tests/test_reqsys_authorized_actions_gateway.py`, `tests/test_self_hosted_runner_governance.py`.
- Pre-PR Readiness deve retornar `READY_FOR_PR=passed` no HEAD exato.
- E2E físico deve produzir artifact no Noteri e ser lido independentemente.
- Nenhuma evidência de outro SHA pode liberar a PR.

## Critérios de aceite

1. Execução em host diferente de `Noteri` deve falhar fechado.
2. O destino deve permanecer exatamente `DESKTOP-PDQK954`, sem parâmetro externo para substituição.
3. DNS indisponível deve produzir `name_resolution_failed` sem expor endereço IP bruto.
4. ICMP positivo e porta 8081 fechada devem produzir `host_reachable_runtime_port_closed`.
5. Porta 8081 aberta deve produzir `runtime_port_reachable`, mesmo quando ICMP não responder.
6. O workflow deve produzir artifact sanitizado no E2E físico do Noteri.
7. O HEAD exato deve obter `READY_FOR_PR=passed` antes de qualquer PR.
8. A evidência deve informar se `C:\\Users\\Public\\Desktop` é alcançável via `C# Requisitos — diagnóstico Noteri → Desktop sem RDC/runner

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
13. A sonda DEVE testar somente leitura no caminho administrativo fixo `C:\\Users\\Public\\Desktop` via `C# Requisitos — diagnóstico Noteri → Desktop sem RDC/runner

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
, sem enumerar/persistir nomes de arquivos e sem gravar qualquer conteúdo.
14. O resultado DEVE distinguir `accessible`, `access_denied`, `not_found` e erro de sistema sanitizado para esse caminho.

## Controles contra falso positivo

- DNS resolvido sem ICMP/TCP não pode ser reportado como host alcançável.
- Porta 8081 aberta comprova reachability mesmo se ICMP estiver bloqueado.
- ICMP positivo com porta fechada deve permanecer distinguível.
- O artifact não deve conter endereços IP resolvidos nem stdout/stderr de `PING.EXE`.
- Host diferente de Noteri ou confirmação divergente deve retornar erro.
- O probe SMB não pode criar, alterar ou excluir arquivos; a evidência registra apenas acessibilidade e classe de erro.

## Validação

- Testes: `tests/test_noteri_desktop_network_probe.py`, `tests/test_reqsys_authorized_actions_gateway.py`, `tests/test_self_hosted_runner_governance.py`.
- Pre-PR Readiness deve retornar `READY_FOR_PR=passed` no HEAD exato.
- E2E físico deve produzir artifact no Noteri e ser lido independentemente.
- Nenhuma evidência de outro SHA pode liberar a PR.

## Critérios de aceite

1. Execução em host diferente de `Noteri` deve falhar fechado.
2. O destino deve permanecer exatamente `DESKTOP-PDQK954`, sem parâmetro externo para substituição.
3. DNS indisponível deve produzir `name_resolution_failed` sem expor endereço IP bruto.
4. ICMP positivo e porta 8081 fechada devem produzir `host_reachable_runtime_port_closed`.
5. Porta 8081 aberta deve produzir `runtime_port_reachable`, mesmo quando ICMP não responder.
6. O workflow deve produzir artifact sanitizado no E2E físico do Noteri.
 a partir do Noteri, sem persistir listagem remota.


## Incremento 2026-09-24 — descoberta de canal de execução remoto

15. A sonda DEVE testar, somente por conexão TCP sem autenticação e sem escrita, as portas fixas: SSH 22, RPC Endpoint Mapper 135, SMB 445, RDP 3389, WinRM HTTP 5985, WinRM HTTPS 5986 e Engineering Orchestrator 8787.
16. Nenhum host, porta ou protocolo pode vir de input externo.
17. A evidência DEVE persistir somente booleanos de alcançabilidade por nome lógico; não deve persistir IP bruto, banner, credencial ou conteúdo remoto.
18. Porta aberta é somente evidência de transporte disponível; não comprova autenticação nem autorização para executar comandos.


19. Quando a porta fixa 8787 estiver acessível, a sonda DEVE ler somente `/readyz` e `/v1/workers` do Engineering Orchestrator.
20. O readback DEVE persistir apenas status HTTP, readiness, quantidade de workers Desktop e booleanos sanitizados `fresh/controller_online/auth_valid/eligible/runner_recovery_capable/rdc_recovery_capable/orchestrator_refresh_capable/reboot_once_capable` mais o perfil; IDs, tokens, corpo bruto, capabilities arbitrárias e segredos são proibidos.
21. `runner_recovery_capable=true` somente quando o worker Desktop único anunciar explicitamente `host.github_runner.recover.v1`.
