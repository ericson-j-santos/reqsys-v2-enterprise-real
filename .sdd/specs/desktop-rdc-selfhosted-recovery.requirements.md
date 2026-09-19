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

## Critérios de aceite

- testes positivos comprovam preferência por headless e fallback interativo;
- testes negativos recusam host ou task não allowlisted;
- workflow usa exclusivamente o runner PC24x7;
- gateway mantém a allowlist estática;
- após integração, comentário exato em #1705 cria um novo workflow_dispatch no SHA atual da main;
- recuperação só é considerada concluída após leitura independente do Remote Desktop Commander mostrar o Desktop online.
