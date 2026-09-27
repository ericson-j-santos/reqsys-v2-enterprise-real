# Noteri → Desktop Orchestrator capabilities probe

## Objetivo

Usar o Noteri como executor físico governado independente do runner Desktop para
observar, sem mutação, as capabilities reais do Engineering Orchestrator em
`DESKTOP-PDQK954:8787`.

## Contrato fechado

- origem: `Noteri`;
- destino: `DESKTOP-PDQK954:8787`;
- métodos HTTP: somente `GET`;
- paths: somente `/readyz` e `/v1/status`;
- worker esperado: `desktop-pdqk954` / `DESKTOP-PDQK954`;
- sem WMI, C$, RPC Task Scheduler, RDC, GUI, shell remoto, reboot ou segredo;
- execução física passa por Session Launcher → Command Gateway;
- evidence inclui `runtime_source_sha`, `worker_instance_id`,
  `recovery_contract_version` e `safe_task_types` sanitizados.

## Aceite

1. testes positivos e negativos passam no SHA exato;
2. Noteri faz pickup do workflow;
3. Session Launcher retorna `SESSION_LAUNCH_OK` com estado validado;
4. Command Gateway executa testes e probe;
5. `/readyz` retorna ready;
6. `/v1/status` retorna exatamente um worker Desktop;
7. artifact sanitizado é publicado no mesmo SHA;
8. nenhuma mutação é executada.

O probe não declara recuperação funcional; ele apenas decide qual capability
existente pode ser usada como próximo incremento.
