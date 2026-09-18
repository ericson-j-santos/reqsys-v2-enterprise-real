# Persistência do agente NORMAL/ESTUDO do Noteri — Requisitos

## Requisito 1 — persistência sem senha
A instalação deve operar somente no host Noteri em Windows, não deve armazenar senha e deve tentar primeiro Task Scheduler com gatilho `AtStartup`, logon `S4U` e nível limitado.

## Requisito 2 — fallback seguro
Quando o registro da tarefa falhar especificamente por `Access Denied`, a implementação pode usar `HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run`. Nesse modo, a evidência deve declarar `requires_user_logon=true` e não pode afirmar operação headless.

## Requisito 3 — runtime local restrito
O agente restaurado deve permanecer acessível somente por loopback e o health check deve validar serviço, host Noteri e `loopback_only=true`.

## Requisito 4 — evidência pós-reboot e idempotência
A validação pós-reboot deve comparar o `boot_epoch` atual com a baseline, recusar falso positivo antes de um novo boot e registrar no máximo uma nova validação para o mesmo boot.

## Critérios de aceite (Acceptance Criteria)
1. A detecção de reboot respeita a tolerância definida e não marca como reinício variações dentro dessa janela.
2. Os arquivos e metadados persistentes ficam sob `LOCALAPPDATA/ReqSys/TodoGlobal24x7`.
3. O contrato da tarefa usa `AtStartup + S4U + RunLevel Limited`.
4. `Access Denied` do Task Scheduler é reconhecido de forma determinística para acionar somente o fallback previsto.
5. A PR possui teste automatizado mapeado em `tests/test_noteri_host_profile_agent_persistence.py`.
6. CI verde no SHA final não substitui a evidência real pós-reboot; a PR permanece parcial até o ciclo real `NORMAL → ESTUDO → NORMAL` ser comprovado após novo boot e logon quando o fallback estiver ativo.
