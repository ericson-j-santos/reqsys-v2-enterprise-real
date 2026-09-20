# Desktop PC24x7 — watchdog autônomo do plano de controle

## Objetivo

Eliminar a dependência circular em que o Remote Desktop Commander (RDC) depende do GitHub Actions self-hosted runner para ser recuperado e o runner, quando indisponível junto com o RDC, impede qualquer recuperação remota.

O estado alvo é um supervisor Windows local que inicia no boot e recupera de forma independente:
- o RDC governado;
- o GitHub Actions runner PC24x7.

## Classificação do incremento

\`gap_fix\`.

Esta mudança corrige uma lacuna comprovada da recuperação integrada pela PR #1818. O workflow \`desktop-rdc-recovery.yml\` permanece como rota secundária e evidência externa, não como mecanismo primário de disponibilidade.

## Requisitos

1. Executar somente no host exato \`DESKTOP-PDQK954\`.
2. Operar somente em local/DEV; produção, HML e STG ficam fora do escopo.
3. Não depender do RDC, GitHub Actions runner, GitHub API, \`workflow_dispatch\`, WMI, SMB ou reboot para manter o watchdog ativo.
4. Instalar uma tarefa Windows \`\\Automation\\ReqSysDesktopControlPlaneWatchdog\` com trigger \`AtStartup\`, \`StartWhenAvailable\`, instância única e reinício automático em falha.
5. Usar logon S4U sem armazenar senha e nível de execução limitado.
6. Manter lock local de instância única para impedir dois watchdogs concorrentes.
7. Descobrir ou receber uma única vez o diretório do GitHub Actions runner e validar apenas a presença de \`.runner\`, \`run.cmd\` e \`bin\\Runner.Listener.exe\`; o conteúdo de \`.runner\` não pode ser lido nem registrado.
8. Considerar o runner local saudável quando \`Runner.Listener.exe\` estiver ativo.
9. Quando o runner estiver inativo, iniciá-lo pelo \`run.cmd\` local já configurado, sem token, segredo ou nova configuração.
10. Considerar RDC headless saudável somente com claim V4 \`ready=true\` fresco.
11. Quando o claim RDC estiver ausente/stale/inválido, chamar o \`pc24x7_rdc_recovery.py\` versionado com a confirmação fixa \`RECOVER-GOVERNED-RDC\`.
12. Não aceitar task name, host, executável RDC, comando arbitrário ou segredo como entrada do ciclo de recuperação.
13. Persistir somente estado sanitizado em \`%LOCALAPPDATA%\\ReqSys\\DesktopControlPlaneWatchdog\`.
14. Toda evidência deve declarar \`production_touched=false\`, \`secrets_read=false\` e \`reboot_performed=false\`.
15. A instalação exige confirmação exata \`INSTALL-DESKTOP-CONTROL-PLANE-WATCHDOG\` e SHA fonte completo.
16. A release local deve copiar somente os scripts versionados necessários; não deve depender do checkout permanecer presente.
17. O workflow \`desktop-rdc-recovery.yml\` continua válido como fallback externo, mas sua indisponibilidade não pode interromper o watchdog local.

## Controles negativos

- host diferente de \`DESKTOP-PDQK954\` deve falhar fechado;
- diretório de runner incompleto deve ser recusado;
- confirmação de instalação incorreta deve ser recusada;
- claim RDC stale não pode ser interpretado como saudável;
- ausência/falha da recuperação RDC deve deixar \`ok=false\`;
- nenhuma leitura do conteúdo de \`.runner\` é permitida;
- nenhuma chamada a \`github.com\`/GitHub API pode existir no watchdog;
- nenhum reboot ou shutdown pode ser disparado.

## Critérios de aceite de código

- testes unitários positivos e negativos verdes;
- \`desktop_control_plane_watchdog.py\` compilável;
- \`pc24x7_rdc_recovery.py\` reutilizado, sem duplicar sua allowlist RDC;
- CI do PR verde no SHA atual.

## Critérios de aceite runtime

A correção só pode ser classificada como totalmente ativada no Desktop quando houver evidência nova, no mesmo ciclo, de:

1. tarefa \`ReqSysDesktopControlPlaneWatchdog\` existente com \`AtStartup\`;
2. estado local do watchdog \`ok=true\`;
3. \`Runner.Listener.exe\` recuperável após ausência controlada;
4. RDC recuperável após claim stale/ausente controlado;
5. leitura independente do RDC indicando \`DESKTOP-PDQK954\` online com \`transport_broadcast_v1=true\`;
6. um workflow self-hosted novo sair de \`pending/queued\` e ser executado no runner PC24x7;
7. nenhum reboot, segredo ou produção tocados.

Enquanto a instalação física no Desktop não for evidenciada, o código pode estar integrado/validado, mas o runtime permanece \`activation_pending\`.
