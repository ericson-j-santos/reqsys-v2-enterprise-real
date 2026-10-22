# Desktop PC24x7 — watchdog autônomo do plano de controle

## Objetivo

Manter o GitHub Actions self-hosted runner recuperável no boot sem reativar o Remote Desktop Commander externo, aposentado em modo fail-closed.

O estado alvo é um supervisor Windows local que inicia no boot, recupera o GitHub Actions runner PC24x7 e registra explicitamente o RDC externo como \`retired_fail_closed\`, sem sondagem ou tentativa de recuperação.

## Classificação do incremento

\`gap_fix\`.

Esta mudança corrige a lacuna comprovada da recuperação integrada pela PR #1818 e alinha o watchdog ao marcador canônico \`EXTERNAL_RDC_RETIRED_FAIL_CLOSED_20261003\`. Fluxos legados de recuperação RDC ficam fora do ciclo ativo.

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
10. Registrar o RDC externo como \`status=retired_fail_closed\`, \`enabled=false\`, \`recovered=false\` e marcador \`EXTERNAL_RDC_RETIRED_FAIL_CLOSED_20261003\`.
11. Não ler claim RDC, copiar ou executar \`pc24x7_rdc_recovery.py\`, nem iniciar tarefa ou processo do RDC aposentado.
12. Não aceitar task name, host, executável RDC, comando arbitrário ou segredo como entrada do ciclo de recuperação.
13. Persistir somente estado sanitizado em \`%LOCALAPPDATA%\\ReqSys\\DesktopControlPlaneWatchdog\`.
14. Toda evidência deve declarar \`production_touched=false\`, \`secrets_read=false\` e \`reboot_performed=false\`.
15. A instalação exige confirmação exata \`INSTALL-DESKTOP-CONTROL-PLANE-WATCHDOG\` e SHA fonte completo.
16. A release local deve copiar somente o watchdog e o launcher UAC necessários; não deve copiar recuperadores RDC nem depender do checkout permanecer presente.
17. Workflows legados de RDC não podem ser chamados pelo watchdog local e não participam da disponibilidade do runner.
18. Se o registro COM `AtStartup + S4U` não estiver disponível ou retornar `Access Denied`, a instalação deve tentar uma única alternativa nativa e local, restrita à tarefa exata, com `schtasks /Create /SC ONSTART /RL LIMITED /NP`; o resultado só é aceito após leitura XML independente comprovar tarefa habilitada, `AtStartup` e `S4U`.
19. A elevação deve usar somente `desktop_control_plane_watchdog_uac_launcher.py`, restrito ao host exato, Windows e confirmação `LAUNCH-DESKTOP-CONTROL-PLANE-WATCHDOG-UAC`.
20. O launcher UAC só pode elevar o subcomando fixo `register-task-com --metadata <metadata governada>` da release imutável instalada. Não pode aceitar task name, comando arbitrário, executável arbitrário, senha, token ou segredo.
21. O subcomando elevado deve revalidar que `metadata.json` pertence ao runtime, que a release está sob `runtime_root/releases/<source_sha>` e que o próprio script executado é o watchdog daquela release.
22. `headless_boot_ready=true` só pode ser persistido após leitura independente da tarefa comprovar `AtStartup + S4U`; somente então o watchdog pode ser iniciado.
23. A ativação UAC não pode executar reboot, deploy/promoção, produção, leitura de segredo nem alteração ampla de RBAC.
24. Se também houver recusa no registro nativo local sem senha, a instalação deve preservar a release imutável e a metadata e retornar explicitamente `activation_pending=true` e `requires_uac_activation=true`; esse estado não é runtime ativo.

## Controles negativos

- host diferente de \`DESKTOP-PDQK954\` deve falhar fechado;
- diretório de runner incompleto deve ser recusado;
- confirmação de instalação incorreta deve ser recusada;
- claim, tarefa ou processo RDC não pode ser consultado ou reativado pelo watchdog;
- a aposentadoria RDC só é aceita quando o marcador canônico está presente no estado sanitizado;
- nenhuma leitura do conteúdo de \`.runner\` é permitida;
- nenhuma chamada a \`github.com\`/GitHub API pode existir no watchdog;
- nenhum reboot ou shutdown pode ser disparado.

## Critérios de aceite de código

- testes unitários positivos e negativos verdes;
- \`desktop_control_plane_watchdog.py\` compilável;
- ausência de dependência ou chamada a \`pc24x7_rdc_recovery.py\` comprovada por teste;
- CI do PR verde no SHA atual.

## Critérios de aceite runtime

A correção só pode ser classificada como totalmente ativada no Desktop quando houver evidência nova, no mesmo ciclo, de:

1. tarefa \`ReqSysDesktopControlPlaneWatchdog\` existente com \`AtStartup\`;
2. estado local do watchdog \`ok=true\`;
3. \`Runner.Listener.exe\` recuperável após ausência controlada;
4. RDC externo registrado como \`retired_fail_closed\` com o marcador canônico e sem tentativa de recuperação;
5. controle negativo comprovando que claim, tarefa e processo RDC não são acionados;
6. um workflow self-hosted novo sair de \`pending/queued\` e ser executado no runner PC24x7;
7. nenhum reboot, segredo ou produção tocados.

Enquanto a instalação física no Desktop não for evidenciada, o código pode estar integrado/validado, mas o runtime permanece \`activation_pending\`.


## Correção da dependência RDC → runner (PR #2544, 12/10/2026)

A leitura física do Desktop em 12/10/2026 identificou a tarefa legada
AtStartup/S4U instalada, mas o código físico recupera o RDC antes do runner.
Se a recuperação RDC falhar, o ciclo falha e nem tenta o runner.

Requisitos adicionais de recuperação sem login:

25. A tentativa de iniciar ou observar `Runner.Listener.exe` deve ocorrer **antes e independentemente** de recuperar o RDC, sem depender de GUI, sessão interativa ou acesso remoto.
26. A ausência do script RDC é o estado esperado e não deve suprimir a tentativa de recuperação do runner. Uma falha do runner não autoriza sondagem, diagnóstico ou recuperação do RDC aposentado.
27. A evidência local deve publicar separadamente `runner_recovery_ok`, `rdc_recovery_ok`, `partial` e `github_pickup_required`; `rdc_recovery_ok=true` significa conformidade com a aposentadoria fail-closed, e `ok=true` continua condicionado ao runner local saudável.
28. Erros devem ser categorizados por tipo e não podem publicar a mensagem original de exceção, argumentos, tokens ou caminhos sensíveis no artefato.
29. A validação em runner hospedado deve testar controles positivos e negativos: runner saudável, runner falho, script RDC ausente e marcador fail-closed, sem qualquer chamada ao recuperador aposentado.
30. A correção em GitHub, isoladamente, não comprova a instalação física. O reboot só pode ocorrer após atualização imutável e reversível do watchdog instalado e readback independente de recuperação do runner sem RDC, preservando capacidade de rollback e o login humano desnecessário para o runtime.

### Critérios de aceite adicionais
- Executar testes da função `cycle` na versão atual e comprovar flags corretas e ausência de texto sensível.
- Manter a tarefa S4U/AtStartup do Desktop e não promover alteração de serviço ou UAC sem autorização e preflight.
- Concluir teste físico no mesmo SHA, respeitando a indisponibilidade atual do RDC e sem afirmar autoinício visual do ChatGPT antes de uma sessão Windows autenticada.

