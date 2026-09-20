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
18. Se o Windows recusar o registro `AtStartup + S4U` com `Access Denied`, a instalação deve preservar a release imutável e a metadata e retornar explicitamente `activation_pending=true` e `requires_uac_activation=true`; esse estado não é runtime ativo.
19. A elevação deve usar somente `desktop_control_plane_watchdog_uac_launcher.py`, restrito ao host exato, Windows e confirmação `LAUNCH-DESKTOP-CONTROL-PLANE-WATCHDOG-UAC`.
20. O launcher UAC só pode elevar o subcomando fixo `register-task-com --metadata <metadata governada>` da release imutável instalada. Não pode aceitar task name, comando arbitrário, executável arbitrário, senha, token ou segredo.
21. O subcomando elevado deve revalidar que `metadata.json` pertence ao runtime, que a release está sob `runtime_root/releases/<source_sha>` e que o próprio script executado é o watchdog daquela release.
22. `headless_boot_ready=true` só pode ser persistido após leitura independente da tarefa comprovar `AtStartup + S4U`; somente então o watchdog pode ser iniciado.
23. A ativação UAC não pode executar reboot, deploy/promoção, produção, leitura de segredo nem alteração ampla de RBAC.
24. A recuperação remota a partir do Noteri deve preferir o control plane já instalado em `http://DESKTOP-PDQK954:18787`, sem WMI, SMB, shell remoto ou automação de interface gráfica.
25. O cliente de manutenção deve aceitar somente o host `DESKTOP-PDQK954`, porta `18787`, esquema HTTP local e endpoint base sem credenciais, path, query ou fragment.
26. As únicas ações remotas permitidas pelo cliente são `host.rdc.recover.v1`, `host.github_runner.recover.v1` e `host.orchestrator.refresh.v1`; reboot e comando arbitrário ficam explicitamente fora da allowlist.
27. Antes de submeter manutenção, o cliente deve exigir worker único do Desktop com heartbeat fresco, `eligible=true` e capability explícita para o task type solicitado.
28. Toda submissão deve preservar `correlation_id` e gerar `event_id`/ `idempotency_key` determinísticos; replay deve reutilizar o mesmo item sem segundo dispatch.
29. Estado terminal `CONCLUÍDO` da fila não comprova efeito funcional. Para RDC, o cliente só pode retornar `ok=true` quando houver testemunho `controller_semantic_ok=true`; ausência desse testemunho deve falhar fechado como `controller_semantic_evidence_missing`.
30. A evidência do cliente deve separar `queue_completed` de `semantic_ok` e declarar `production_touched=false`, `secrets_read=false` e `reboot_performed=false`.

## Controles negativos

- host diferente de \`DESKTOP-PDQK954\` deve falhar fechado;
- diretório de runner incompleto deve ser recusado;
- confirmação de instalação incorreta deve ser recusada;
- claim RDC stale não pode ser interpretado como saudável;
- ausência/falha da recuperação RDC deve deixar \`ok=false\`;
- nenhuma leitura do conteúdo de \`.runner\` é permitida;
- nenhuma chamada a \`github.com\`/GitHub API pode existir no watchdog;
- nenhum reboot ou shutdown pode ser disparado;
- endpoint com host, porta, credencial ou path divergente deve ser recusado antes da chamada;
- ação fora da allowlist deve ser recusada;
- worker stale, inelegível ou sem capability deve bloquear antes da mutação;
- `CONCLUÍDO` sem testemunho semântico do RDC deve permanecer `ok=false`.

## Critérios de aceite de código

- testes unitários positivos e negativos verdes;
- \`desktop_control_plane_watchdog.py\` compilável;
- \`pc24x7_rdc_recovery.py\` reutilizado, sem duplicar sua allowlist RDC;
- CI do PR verde no SHA atual;
- `desktop_control_plane_maintenance_client.py` compilável;
- testes positivos, negativos, replay e falso-verde do cliente de manutenção verdes.

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
