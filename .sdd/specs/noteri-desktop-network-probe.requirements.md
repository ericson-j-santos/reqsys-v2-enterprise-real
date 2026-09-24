# Requisitos — diagnóstico Noteri → Desktop sem RDC/runner

Issue: #1899  
Tipo: `gap_fix`

## Objetivo

Produzir evidência independente e sanitizada, a partir do `Noteri`, sobre a
disponibilidade do `DESKTOP-PDQK954` quando os runners e o RDC do Desktop não
estiverem utilizáveis.

## Requisitos funcionais

1. A execução física ocorre somente no host `Noteri`, Windows X64,
   `reqsys-dev`.
2. O destino é fixo `DESKTOP-PDQK954`; nenhum input externo altera host,
   portas ou paths.
3. A sonda resolve DNS sem persistir endereços IP brutos.
4. ICMP usa `PING.EXE` por argv fixo, sem shell, com timeout e sem persistir
   stdout/stderr.
5. A sonda testa por TCP, com timeout finito, somente:
   - runtime DEV: porta `8081`;
   - Engineering Orchestrator/control-plane: porta `8787`.
6. Se `8787` estiver aberta, a única requisição HTTP permitida é
   `GET http://DESKTOP-PDQK954:8787/readyz`; a evidência registra apenas
   alcance, status HTTP inteiro/nulo e booleano `ready`, nunca o corpo bruto.
7. O resultado principal distingue `name_resolution_failed`,
   `resolved_not_reachable`, `host_reachable_runtime_port_closed` e
   `runtime_port_reachable`.
8. Indisponibilidade do destino é resultado diagnóstico terminal; erro de
   contrato ou host de origem falha fechado.
9. A evidência registra `correlation_id`, origem, destino, estado de rede,
   sinais booleanos, timestamp e `rdc_required=false`,
   `production_touched=false`, `secrets_read=false`.
10. A sonda não usa GUI, clipboard, credenciais, alteração de firewall, reboot,
    shutdown, comando remoto ou escrita no Desktop.
11. O caminho administrativo fixo
    `C:\Users\Public\Desktop` via `C$` é testado somente para leitura,
    sem enumerar ou persistir nomes de arquivos.
12. O resultado administrativo distingue `accessible`, `access_denied`,
    `not_found` e erro de sistema sanitizado.
13. O workflow de recuperação governado deve executar a sonda pelo Session
    Launcher + Command Gateway antes da prova do runner físico, para que o
    watchdog não cancele a evidência de rede.
14. Wake-on-LAN não faz parte deste incremento.

## Controles contra falso positivo

- DNS resolvido isoladamente não comprova host alcançável.
- Porta 8081 aberta comprova reachability mesmo se ICMP estiver bloqueado.
- ICMP positivo com 8081 fechada permanece distinguível.
- Porta 8787 aberta não implica readiness; `control_plane_ready=true` exige
  HTTP 200 e JSON com `ready=true`.
- O artefato não contém IP bruto, corpo HTTP do control-plane, listagem SMB nem
  stdout/stderr do ping.
- Host diferente de Noteri ou confirmação divergente falham fechado.
- O probe SMB não cria, altera ou exclui arquivos.

## Validação

- Testes: `tests/test_noteri_desktop_network_probe.py`,
  `tests/test_reqsys_authorized_actions_gateway.py` e
  `tests/test_self_hosted_runner_governance.py`.
- Pre-PR Readiness deve retornar `READY_FOR_PR=passed` no HEAD exato.
- E2E físico deve produzir artefato no Noteri, vinculado ao mesmo SHA e
  `correlation_id`.
- Nenhuma evidência de outro SHA libera o incremento.

## Critérios de aceite

1. Host de origem diferente de `Noteri` falha fechado.
2. Destino permanece exatamente `DESKTOP-PDQK954`.
3. DNS indisponível produz `name_resolution_failed` sem IP bruto.
4. ICMP positivo e 8081 fechada produzem
   `host_reachable_runtime_port_closed`.
5. 8081 aberta produz `runtime_port_reachable`.
6. A evidência informa separadamente alcance/readiness do control-plane 8787.
7. A evidência informa somente a classe de acesso a
   `C:\Users\Public\Desktop`, sem listagem remota.
8. Nenhuma operação toca produção, segredos ou estado remoto.
