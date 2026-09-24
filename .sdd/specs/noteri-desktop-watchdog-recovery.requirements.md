# Requisitos — recuperação do plano de controle Desktop via Noteri

## Objetivo

Quando o DESKTOP-PDQK954 estiver com runner GitHub e/ou RDC indisponíveis, usar o runner Noteri como produtor governado para solicitar ao Engineering Orchestrator já residente no Desktop uma manutenção local allowlisted.

## Restrições

1. O executor produtor é exclusivamente o runner self-hosted do host `Noteri`.
2. O destino é fixo: `DESKTOP-PDQK954`.
3. O transporte preferencial é o Engineering Orchestrator fixo `http://DESKTOP-PDQK954:8787`.
4. Antes de qualquer mutação, `/readyz` deve responder saudável e `/v1/workers` deve conter exatamente um worker Desktop fresco, controller online, auth válido e elegível.
5. O produtor nunca aceita task type, host, comando, porta ou endpoint fornecido pelo usuário.
6. Se o worker anunciar `host.github_runner.recover.v1`, essa tarefa deve ser preferida.
7. Se a recuperação do runner não estiver disponível e o worker anunciar `host.rdc.recover.v1`, a única alternativa permitida é reiniciar o RDC governado com `force_restart=true`.
8. Nenhum comando arbitrário, shell remoto, WinRM, PsExec, WMI, SMB administrativo, deploy, produção, reboot, RBAC, segredo ou credencial faz parte deste fluxo.
9. O enqueue usa `POST /v1/intake`, risco 1, `max_attempts=1`, lease limitado e idempotency key derivada do `github.run_id`; rerun do mesmo run não duplica o efeito lógico.
10. A conclusão exige `GET /v1/work-items/{id}` independente, status `CONCLUÍDO`, handler idêntico ao task type selecionado e host igual ao Desktop.
11. Evidência persistida deve ser sanitizada: não pode conter worker_id, token, corpo bruto do registry ou capabilities arbitrárias.
12. O Authorized Actions Gateway continua expondo somente o comando exato `/reqsys run noteri-desktop-watchdog-recovery`.
13. Sem pickup do Noteri, o gateway deve falhar fechado.
14. O workflow deve materializar sessão governada por `session_launcher.py` no SHA exato e exigir `SESSION_LAUNCH_OK` + `state_validated=true`.
15. O produtor deve executar exclusivamente por `command_gateway.py`, risco 2, dentro do `target_path` isolado e com `expected-head` igual ao SHA da execução.
16. As regras operacionais usadas no E2E devem ser fixadas por SHA imutável e o checkout não pode persistir credenciais.
17. No Noteri, `github.workspace` é somente fonte transitória do Session Launcher; a execução ocorre em worktree governado sob `C:\\dev\\chatgpt-workers`.
18. O script de recuperação deve ser resolvido a partir do `target_path` retornado pelo Session Launcher.
19. Após recuperação do runner, um workflow self-hosted Desktop deve fazer pickup antes de declarar o runner restaurado.
20. Após recuperação do RDC, o controller deve ser observado online de forma independente antes de usá-lo como transporte.

## Critérios de aceite

- Session Launcher e Command Gateway aprovam o SHA exato;
- o Orchestrator residente está saudável;
- worker Desktop único e elegível é lido de forma sanitizada;
- somente handler allowlisted é despachado;
- replay do mesmo run é idempotente;
- resultado é lido de volta pelo item exato;
- nenhuma produção, segredo ou comando arbitrário é tocado;
- efeito terminal é comprovado por pickup do runner ou controller RDC online, conforme o handler executado.
