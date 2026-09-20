# Desktop RDC — recuperação automática via runner PC24x7

## Objetivo

Recuperar o Remote Desktop Commander do DESKTOP-PDQK954 sem depender do próprio RDC, WMI, SMB ou privilégios administrativos remotos, usando o GitHub Actions self-hosted runner já autorizado no PC24x7.

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
13. O runner headless deve reconhecer somente os marcadores governados `RDC_HEADLESS_V2_PRIMARY_OWNER`, `RDC_HEADLESS_V3_READY_CLAIM` e `RDC_HEADLESS_V4_TRANSPORT_GUARD`. V2/V3 são legados sem prova de transporte: a recuperação deve encerrá-los, limpar claim residual e usar o fallback interativo; somente V4 pode permanecer owner headless após claim fresco de transporte.
14. O launcher interativo deve aceitar somente os marcadores governados `RDC_LAUNCHER_V3_RESILIENT`, `RDC_LAUNCHER_V4_ARBITRATED` e `RDC_LAUNCHER_V5_READY_CLAIM`; qualquer marcador desconhecido deve permanecer fail-closed.
15. Após iniciar V4, a recuperação deve aguardar claim `ready=true` fresco por janela limitada; claim ausente, inválido ou stale não comprova saúde e deve cair para o launcher interativo.
16. O fluxo deve armar o fallback interativo mesmo quando V4 estiver saudável, permitindo takeover automático se o claim V4 desaparecer.

## Critérios de aceite

- testes positivos comprovam V4 com claim fresco e fallback interativo armado;
- controle negativo comprova que Headless V3 não é aceito como owner saudável e é suprimido antes do fallback;
- testes negativos recusam host ou task não allowlisted, claim stale e claim inválido;
- marcadores não allowlisted permanecem recusados antes da execução de qualquer tarefa;
- workflow usa exclusivamente o runner PC24x7;
- gateway mantém a allowlist estática;
- após integração, comentário exato em #1705 cria um novo workflow_dispatch no SHA atual da main;
- recuperação só é considerada concluída após leitura independente mostrar `DESKTOP-PDQK954` online com `transport_broadcast_v1=true` e uma chamada MCP real de leitura concluir com sucesso.
