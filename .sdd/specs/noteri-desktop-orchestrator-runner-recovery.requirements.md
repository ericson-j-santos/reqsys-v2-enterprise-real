# Noteri → Desktop Orchestrator Runner Recovery

## Objetivo

Recuperar o GitHub runner do `DESKTOP-PDQK954` usando o Engineering Orchestrator
já instalado no Desktop e o Noteri como origem física governada.

## Contrato fechado

- origem: `Noteri`;
- destino: `DESKTOP-PDQK954`;
- porta: `8787`;
- task: `host.github_runner.recover.v1`;
- papel: `builder`;
- risco: `2`;
- ambiente: DEV.

O cliente não recebe host, porta, URL, task type, executável ou comando arbitrário.

## Pré-condições

1. Noteri deve executar o job físico.
2. `DESKTOP-PDQK954:8787/readyz` deve responder `ready=true`.
3. O registry do Orchestrator deve conter exatamente um worker do Desktop.
4. Esse worker deve estar fresco, `NORMAL`, `controller_online=true`,
   `auth_valid=true` e anunciar `host.github_runner.recover.v1`.

## Fluxo

1. executar controle negativo de leitura para um work item inexistente;
2. publicar uma única entrada idempotente em `POST /v1/intake`;
3. exigir dispatch para o worker do `DESKTOP-PDQK954`;
4. acompanhar o mesmo work item até estado terminal com timeout;
5. exigir `CONCLUÍDO` e handler/host esperados;
6. repetir o intake e exigir replay sem segundo dispatch;
7. reler o work item independentemente;
8. reler o worker físico e registrar somente evidência sanitizada.

## Segurança

- sem shell remoto;
- sem WMI, C$, WinRM, SSH ou RDC;
- sem segredo/credencial no payload ou artifact;
- sem reboot;
- sem deploy ou produção;
- falha fechada diante de worker ausente, stale, fora de NORMAL ou sem capability.

## Critério de aceite

O workflow físico no Noteri deve terminar verde no SHA integrado e produzir artifact
com:

- `DESKTOP_GITHUB_RUNNER_RECOVERY_COMPLETED`;
- `replay_idempotent=true`;
- `negative_read_control=true`;
- `independent_readback=true`;
- `remote_shell_used=false`;
- `production_touched=false`;
- `reboot_performed=false`.

Depois dessa evidência, o runner do Desktop ainda deve ser validado por pickup
independente em GitHub Actions antes de ser considerado recuperado.
