# Desktop PC24x7 — canal administrativo governado

## Objetivo

Criar um canal administrativo persistente e de menor privilégio para o `DESKTOP-PDQK954` que continue operacional quando o Remote Desktop Commander e o GitHub Actions runner do Desktop estiverem simultaneamente indisponíveis.

O canal não é um bypass de UAC. A criação inicial da tarefa elevada continua exigindo uma única autorização administrativa local. Após essa ativação, novas operações administrativas ficam restritas a handlers versionados e allowlisted.

## Classificação

`gap_fix`.

## Arquitetura

- executor local: tarefa `\\Automation\\ReqSysDesktopAdminBroker`;
- trigger: `AtStartup`;
- identidade: usuário atual via `S4U`, sem senha;
- run level: `highest`;
- transporte: somente saída HTTPS para a API pública do GitHub;
- fonte de autorização: issue operacional `#1705`;
- ator autorizado: owner `ericson-j-santos`;
- nenhum listener TCP/HTTP local é aberto.

## Requisitos

1. Executar somente em `DESKTOP-PDQK954`.
2. Operar somente em local/DEV.
3. Não aceitar shell, comando, caminho, host, executável, segredo ou argumento arbitrário vindo do GitHub.
4. Aceitar somente os comandos exatos definidos em `ALLOWED_COMMANDS`.
5. Exigir simultaneamente `user.login=ericson-j-santos` e `author_association=OWNER`.
6. Rejeitar comentários editados.
7. Rejeitar comentários anteriores à ativação do broker.
8. Rejeitar comentários com idade superior a 300 segundos e timestamps futuros fora da tolerância.
9. Usar o `comment_id` como idempotency key e persistir o último comentário observado antes de executar o handler.
10. Não reexecutar automaticamente um comentário após falha; uma nova tentativa exige um novo comentário.
11. Não abrir WinRM, SSH, SMB, WMI remoto ou listener de rede.
12. Não armazenar token GitHub, senha ou segredo; o transporte usa leitura HTTPS pública da issue.
13. O broker deve executar apenas: status, recuperação do runner, recuperação RDC, ativação do watchdog e recuperação do plano de controle.
14. A recuperação RDC deve reutilizar `pc24x7_rdc_recovery.py`.
15. A recuperação do runner deve reutilizar `activate_desktop_free_control_plane.py` da mesma release imutável, com `source_sha` fixo e autenticação não interativa; runner ausente deve ser provisionado, e autenticação/escopo insuficiente deve falhar fechado sem abrir navegador.
16. A recuperação do plano de controle deve reutilizar `desktop_control_plane_watchdog.py`; a ativação do watchdog deve reutilizar `desktop_control_plane_watchdog_uac_launcher.py` e, quando chamada pelo broker já elevado, nenhuma nova aprovação UAC deve ser necessária.
17. O broker deve ser instalado em release imutável vinculada ao SHA fonte completo.
18. A tarefa do broker deve ser `AtStartup + S4U + highest`, com instância única e restart automático.
19. Se a criação da tarefa elevada for negada, persistir `activation_pending=true` e `requires_uac_activation=true`.
20. A elevação inicial deve usar somente `desktop_admin_broker_uac_launcher.py` e o subcomando fixo `register-task-com --metadata`.
21. O canal não autoriza reboot, shutdown, deploy, produção, segredo, RBAC amplo, force-push ou exclusão destrutiva.
22. Toda evidência deve declarar `production_touched=false`, `secrets_read=false` e `reboot_performed=false`.

## Comandos allowlisted

- `/reqsys admin desktop status`
- `/reqsys admin desktop recover-control-plane`
- `/reqsys admin desktop recover-rdc`
- `/reqsys admin desktop recover-runner`
- `/reqsys admin desktop activate-watchdog`

## Critérios de aceite de código

- testes positivos e negativos verdes;
- lint/compilação verdes;
- nenhum shell arbitrário;
- anti-replay comprovado;
- comentário de ator incorreto, associação incorreta, editado, antigo ou fora da allowlist deve ser ignorado;
- UAC launcher deve elevar somente a release imutável e somente com metadata governada;
- `recover-runner` deve usar apenas o bootstrap fixo da release, sem login/refresh interativo do GitHub;
- Pre-PR Readiness no HEAD exato deve produzir `READY_FOR_PR=passed`.

## Critérios de aceite runtime

Após integração e autorização explícita de instalação administrativa:
1. broker instalado e verificado como `AtStartup + S4U + highest`;
2. comentário `status` novo é consumido exatamente uma vez;
3. controle negativo com comando não allowlisted não produz efeito;
4. `recover-runner` recupera `Runner.Listener.exe` e um workflow self-hosted faz pickup;
5. `recover-rdc` produz leitura independente do RDC;
6. repetição do mesmo comentário não produz segundo efeito;
7. nenhum reboot, segredo ou produção é tocado.
