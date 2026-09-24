# Desktop RDC — recuperação automática via runner PC24x7

## Objetivo

Recuperar o Remote Desktop Commander do DESKTOP-PDQK954 sem depender do próprio RDC, WMI, SMB ou privilégios administrativos remotos, usando o GitHub Actions self-hosted runner já autorizado no PC24x7.

## Papel após a correção estrutural

Este fluxo permanece como **fallback externo e evidência independente**, não como mecanismo primário de disponibilidade. A disponibilidade local passa a ser responsabilidade do watchdog autônomo definido em \`.sdd/specs/desktop-control-plane-watchdog.requirements.md\` e implementado em \`scripts/desktop_control_plane_watchdog.py\`.

Assim, indisponibilidade simultânea de RDC + self-hosted runner não deve mais formar dependência circular depois que o watchdog estiver ativado no Desktop.

## Requisitos

1. Executar somente no host exato DESKTOP-PDQK954.
2. Usar somente o runner com labels self-hosted, Windows, X64, pc24x7 e reqsys-dev.
3. Preferir a tarefa existente \Automation\RemoteDesktopCommanderHeadless.
4. Usar \Automation\RemoteDesktopCommander apenas como fallback.
5. Não criar, editar, habilitar, desabilitar ou excluir tarefas.
6. Validar o marcador governado do runner/launcher antes de executar uma tarefa.
7. Não aceitar host, task name, executável ou comando fornecido como input do workflow.
8. Não ler segredos.
9. Não tocar produção.
10. Publicar evidência sanitizada como artifact.
11. O Authorized Actions Gateway deve aceitar somente o comando exato /reqsys run desktop-rdc-recovery, restrito à issue #1705 e ao ator ericson-j-santos.
12. O gateway deve fixar ref=main; nenhuma branch, ref ou workflow arbitrário pode vir do comentário.
13. O runner headless deve reconhecer somente os marcadores governados \`RDC_HEADLESS_V2_PRIMARY_OWNER\`, \`RDC_HEADLESS_V3_READY_CLAIM\` e \`RDC_HEADLESS_V4_TRANSPORT_GUARD\`. V2/V3 são legados sem prova de transporte: a recuperação deve encerrá-los, limpar claim residual e usar o fallback interativo; somente V4 pode permanecer owner headless após claim fresco de transporte.
14. O launcher interativo deve aceitar somente os marcadores governados \`RDC_LAUNCHER_V3_RESILIENT\`, \`RDC_LAUNCHER_V4_ARBITRATED\` e \`RDC_LAUNCHER_V5_READY_CLAIM\`; qualquer marcador desconhecido deve permanecer fail-closed.
15. Após iniciar V4, a recuperação deve aguardar claim \`ready=true\` fresco por janela limitada; claim ausente, inválido ou stale não comprova saúde e deve cair para o launcher interativo.
16. O fluxo deve armar o fallback interativo mesmo quando V4 estiver saudável, permitindo takeover automático se o claim V4 desaparecer.
17. O Authorized Actions Gateway deve vincular a evidência ao \`run_id\` retornado pelo próprio \`gh workflow run\`; é proibido selecionar um run apenas por \`head_sha\`, pois múltiplas execuções podem compartilhar o mesmo SHA.
18. Para recuperação Desktop, estados \`pending\`, \`queued\`, \`requested\` ou \`waiting\` após no máximo 60 segundos de pickup devem produzir \`SELF_HOSTED_RUNNER_UNAVAILABLE\` e falhar fechado.
19. Antes da falha terminal por ausência de pickup, o gateway deve solicitar o cancelamento do run self-hosted abandonado, aguardar confirmação `completed/cancelled` por janela limitada e registrar `target_cleanup_status`/`target_cleanup_error` na evidência. Falha na limpeza não autoriza redispatch nem retry automático.

## Critérios de aceite

- testes positivos comprovam V4 com claim fresco e fallback interativo armado;
- controle negativo comprova que Headless V3 não é aceito como owner saudável e é suprimido antes do fallback;
- testes negativos recusam host ou task não allowlisted, claim stale e claim inválido;
- marcadores não allowlisted permanecem recusados antes da execução de qualquer tarefa;
- workflow usa exclusivamente o runner PC24x7;
- gateway mantém a allowlist estática;
- gateway comprova \`run_id\`, URL, SHA e evento do run exato disparado e recusa evidência de execução histórica;
- recuperação permanece bloqueada quando o run exato não sai de \`pending/queued/requested/waiting\`;
- run self-hosted sem pickup é cancelado e o estado terminal é registrado; se o cancelamento não puder ser confirmado, a evidência registra o erro e o gateway continua falhando fechado, sem criar nova tentativa;
- após integração, comentário exato em #1705 cria um novo workflow_dispatch no SHA atual da main;
- recuperação só é considerada concluída após leitura independente mostrar \`DESKTOP-PDQK954\` online com \`transport_broadcast_v1=true\` e uma chamada MCP real de leitura concluir com sucesso;
- o fluxo não pode voltar a ser a única dependência de recuperação do Desktop; o watchdog autônomo é o mecanismo primário.
