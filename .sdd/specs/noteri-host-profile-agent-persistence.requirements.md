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

## Requisito 5 — operação headless antes do login
Deve existir uma instalação administrativa explícita que registre a mesma tarefa `AtStartup + S4U + RunLevel Limited` sem fallback silencioso. A operação headless deve exigir elevação administrativa e confirmação exata, continuar sem senha e reutilizar o mesmo agente local.

## Requisito 6 — caminhos determinísticos
A tarefa headless deve fornecer explicitamente ao controlador os caminhos de `host-profile.json`, auditoria e estado do agente sob `LOCALAPPDATA/ReqSys/TodoGlobal24x7`, para não depender da resolução de ambiente durante o boot.

## Requisito 7 — experiência do usuário
No Task Console, o usuário deve receber instrução direta: clicar em `Quero estudar agora` libera o Noteri para estudo enquanto o Desktop continua recebendo desenvolvimento; `Voltar ao desenvolvimento` recoloca o Noteri no pool.

## Critérios adicionais do incremento headless
7. A instalação headless falha fechada com `admin_elevation_required` quando o processo não está elevado.
8. Confirmação diferente de `ENABLE-NOTERI-HEADLESS-S4U` é recusada.
9. A tarefa headless usa o mesmo usuário, `S4U`, gatilho de boot e nível limitado; nenhuma senha é persistida.
10. O status só declara `headless_ready=true` após leitura independente do contrato real da tarefa.
11. A conclusão headless exige evidência após reboot **antes do login** ou outra evidência inequívoca de execução pré-login; o E2E funcional após login continua obrigatório e deve terminar em `NORMAL`.
