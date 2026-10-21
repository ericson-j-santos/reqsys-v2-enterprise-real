# Requisitos — Handoff branch-first para Codex Worker Pool

## Escopo

Fechar o elo operacional das issues #1766 e #1770 sem criar fila ou executor paralelo.

O `Pending Development Orchestrator` continua sendo a fonte de seleção de trabalho. Quando GitHub Agent Tasks estiver indisponível ou sem quota, o fallback `local_codex_branch_first` deve despachar uma única execução do workflow PC24x7, que enfileira a mesma identidade lógica no `codex-worker-pool` já existente.

## Requisitos funcionais

1. O `request_id` deve continuar determinístico por repositório, issue e branch base.
2. O handoff deve registrar o SHA exato da base e recusá-lo se não possuir 40 caracteres hexadecimais.
3. O dispatch para o Worker Pool deve ocorrer antes do marcador de sucesso na issue; falha no dispatch não pode produzir falso `already_dispatched`.
4. Marcador local legado sem marcador do Worker Pool deve ser recuperado automaticamente uma única vez.
5. Marcador local + marcador do Worker Pool deve impedir novo dispatch.
6. O job físico `enqueue` do workflow de handoff deve executar somente por `workflow_dispatch`, no runner allowlisted `[self-hosted, Windows, X64, pc24x7, reqsys-dev]`; jobs GitHub-hosted de validação contratual podem reutilizar o mesmo workflow em eventos explicitamente restritos.
7. O workflow deve fazer checkout do `base_sha` imutável informado pelo orquestrador.
8. O bridge só pode acessar Worker Pool por HTTP em loopback (`127.0.0.1`, `localhost` ou `::1`).
9. O bearer token deve ser lido exclusivamente de arquivo já provisionado por `CODEX_WORKER_POOL_API_TOKEN_FILE` ou `CODEX_WORKER_POOL_API_TOKEN_FILE_HOST`; o valor não pode entrar em workflow, log ou evidência.
10. Em contrato v1, o bridge deve preferir `POST /v1/work`, repetir a mesma identidade e exigir replay `created=false` no mesmo `work_id` e `task_id`.
11. Um `GET /v1/work/{work_id}` separado deve confirmar `work_id`, `task_id`, repositório, issue, `request_id` e `base_sha`; somente HTTP 404 de `/v1/work` pode ativar o fallback temporário para `/v1/tasks`.
12. A evidência não pode conter `lease_token`.
13. O Worker Pool existente permanece responsável por Builder → `produced_sha` → Validator independente → `completed`; este incremento não duplica essa lógica.
14. Ausência de token, Worker Pool não saudável, URL não-loopback, SHA inválido ou readback divergente devem falhar fechado.
15. O incremento não executa merge, deploy, produção, mudança de segredo, permissão administrativa ou reboot.
16. Após health positivo, o bridge deve consultar `GET /v1/contract` antes de enfileirar trabalho.
17. Quando o endpoint existir, `contract_name` deve ser `engineering-worker-pool` e `contract_version` deve ser `v1`; divergência deve falhar fechado sem fallback.
18. Durante a janela de migração, somente HTTP 404 do endpoint de contrato pode ativar `legacy_fallback`; 401, 503, erro de transporte ou JSON inválido permanecem bloqueantes.
19. A evidência deve registrar `contract_mode`, versão esperada e se o fallback legado foi usado, sem registrar token.
20. O parâmetro `--require-contract-v1` deve desabilitar o fallback legado sem exigir nova alteração de código.
21. O Authorized Actions Gateway deve aceitar o comando exato `/reqsys run codex-worker-pool-handoff-e2e-dev` somente na issue operacional #1705 e pelo owner.
22. O comando deve mapear exclusivamente para `codex-worker-pool-handoff.yml`, em `main`, fixando `issue_number=2020`, `base_branch=main`, `base_sha` no SHA corrente capturado pelo próprio gateway, `request_id` determinístico de `repo:2020:main` e `execution_mode=hosted_dev_proof`; nenhum input arbitrário pode vir do comentário.
23. A rota hospedada não deve usar o watchdog de pickup self-hosted; a evidência do gateway deve vincular o run despachado ao SHA corrente, e o próprio job hospedado deve falhar fechado se OIDC, broker, autoridade DEV ou gates não forem satisfeitos.

24. Deve existir um E2E portátil em runner GitHub-hosted que suba o repositório real `engineering-worker-pool` em SHA completo fixado e valide o consumidor ReqSys sem depender do runner físico.
25. O E2E portátil deve usar banco SQLite e bearer token efêmeros no filesystem temporário do runner, sem GitHub Secret, sem persistência e sem exposição em log/evidência.
26. Antes do handoff, o E2E portátil deve configurar a lane do ReqSys com `enabled=false`, não registrar workers e exigir `GET /v1/contract` v1 + `POST /v1/work` com `allow_legacy_fallback=false` e `allow_work_fallback=false`.
27. O caso positivo deve provar criação, replay `created=false`, mesmo `work_id/task_id`, leitura independente, task `queued` sem lease e ausência de `lease_token`; o caso negativo deve provar HTTP 401 com token inválido.
28. A evidência deve vincular SHA do ReqSys, SHA do Engineering Worker Pool, SHA canônico das regras e `correlation_id`, declarar `physical_runtime_validated=false`; o E2E portátil não substitui o smoke/E2E PC24x7.
29. O E2E portátil deve reutilizar `codex-worker-pool-handoff.yml`, executar somente em `push` dos arquivos do contrato com `contents: read`, timeout finito, sem deploy, produção ou mutação de segredo; o `workflow_dispatch` permanece reservado ao job físico.
30. A evidência portátil só é válida quando `reqsys_sha` corresponde ao HEAD final já sincronizado com a `main` corrente (`behind_by=0`); qualquer novo commit ou avanço da base exige nova execução no novo SHA.
31. O resumo PowerShell do handoff deve transportar issue, base SHA e request ID por variáveis de ambiente, sem interpolar expressões do Actions dentro de strings PowerShell com crases; deve registrar executor, modo branch-first e ausência de PR automática, merge, deploy e exposição de token.
32. O `workflow_dispatch` deve manter `legacy_pc24x7` como modo padrão e expor `hosted_dev_proof` como escolha explícita, sem alterar silenciosamente o Authorized Actions Gateway existente.
33. O job hospedado deve executar em `ubuntu-24.04`, conceder `id-token: write` apenas ao próprio job e usar o perfil OIDC compilado `reqsys-handoff-v1` no workflow canônico em `main`.
34. A prova hospedada deve fixar o Engineering Worker Pool no merge SHA `5d8de580fea571404607aa80c7bd7637b4652db6`, hidratar exclusivamente a configuração privada do broker e usar a autoridade PostgreSQL DEV; SQLite não constitui evidência real.
35. A execução deve passar pelo Session Launcher, Command Gateway e uma autorização Owner Risk3 efêmera e específica, com o modo DEV amplo desabilitado.
36. O Work v1 deve criar uma task com `fencing_required=true`, provar replay `created=false`, rejeitar claim exato legado, aceitar apenas claim exato fenced e registrar Builder e Validator distintos.
37. A menor tarefa real deve ler fontes versionadas do ReqSys, produzir recibo não simulado, passar por validação em processo independente, concluir a task e obter readback PostgreSQL em processo independente.
38. A evidência pública deve registrar SHAs, IDs de work/task/run, controles de autorização, fencing, replay e readback, declarando explicitamente ausência de merge, deploy e produção e custo adicional de R$ 0,00; tokens, DSN e credenciais não podem ser emitidos.
39. A prova hospedada só é autorizável depois que seu código estiver na `main` verificada; execução em branch deve falhar fechada no broker e não deve ser tratada como evidência.
40. Se a fachada hospedada encerrar antes do health, a prova deve falhar imediatamente, manter o log bruto apenas no diretório privado efêmero e publicar somente um código de causa explicitamente allowlisted; saída desconhecida deve resultar em `worker_pool_process_exited`, sem DSN, token, host ou texto arbitrário.
41. No runner hospedado, após validar o perfil privado `sslrootcert=system`, a prova deve materializar uma cópia efêmera owner-only da DSN apontando explicitamente para `/etc/ssl/certs/ca-certificates.crt`; perfil divergente ou bundle ausente deve falhar fechado e a DSN nunca pode entrar na evidência.
42. A criação do Work v1 hospedado não pode enviar branch protegida como destino; deve omitir `target_branch` e delegar ao Worker Pool a derivação branch-first determinística.
43. A evidência do Work não pode declarar readback independente antes da conclusão bem-sucedida do subprocesso PostgreSQL separado; esse subprocesso deve receber o perfil privado com CA explícita. Em replay, evidência já verificada só pode ser reutilizada depois de novo readback e da coincidência de SHA, controles e merge state.

## Critérios de aceite

- testes do fallback provam dispatch antes do marcador, deduplicação e recuperação de marcador legado;
- testes do bridge provam positivo, replay, leitura independente, ausência de trabalho, URL não-loopback, SHA inválido, contrato v1, fallback exclusivo em 404 e bloqueio de versões incompatíveis;
- teste contratual do workflow prova isolamento por evento: `workflow_dispatch` executa apenas o job físico no runner fixo e `push` executa apenas o job portátil GitHub-hosted, ambos sem secret inline;
- teste do Authorized Actions Gateway prova comando exato, target fixo, inputs derivados/fixos, `main` e pickup fail-closed para o handoff E2E;
- `check_self_hosted_runner_governance.py` aceita apenas o workflow explicitamente allowlisted;
- E2E portátil GitHub-hosted deve validar o repositório real `engineering-worker-pool` no SHA fixado, contrato v1/work_v1 estrito, replay, leitura independente, controle negativo 401 e lane desabilitada, sem substituir a prova física;
- Pre-PR Readiness deve retornar `READY_FOR_PR=passed` no HEAD exato;
- a conclusão física de #1766 permanece parcial até uma task real produzir branch/SHA, passar por Validator independente e chegar a `READY_FOR_PR`/PR sem duplicidade;
- a prova hospedada mínima só é aceita com `result=REQSYS_HOSTED_WORKER_POOL_PROOF_PASSED`, `simulated=false`, task `completed`, fencing ativo, claim legado rejeitado, Validator separado e readback PostgreSQL independente;
- testes portáteis/SQLite continuam sendo regressão contratual e não substituem a prova hospedada real.
- o diagnóstico de startup deve provar causa allowlisted, redação de saída desconhecida e interrupção imediata quando o processo já encerrou;
- o trust TLS hospedado deve preservar `verify-full`, usar arquivo privado `0600`, fixar somente o bundle CA do host e rejeitar perfil inesperado sem expor credenciais;
- o payload Work v1 hospedado deve exigir fencing/governed e não conter `target_branch` protegido;
- falha do subprocesso de readback deve impedir a gravação de evidência positiva; replay exige novo readback e validação estrita da evidência existente.

## Evidência E2E

Registrar, no maior escopo executável:

- ambiente/host;
- branch e SHA;
- issue e `request_id`;
- `correlation_id`;
- `task_id`;
- `base_sha` e posteriormente `produced_sha`;
- resultado do replay;
- leitura independente;
- Builder e Validator distintos;
- bloqueio explícito quando o Desktop/Worker Pool não estiver disponível.
## Compatibilidade do gate após avanço da main

- referência dinâmica de segredo por variável de ambiente (`${VAR}` ou `${VAR:?mensagem}`/`${VAR?mensagem}`) não deve ser classificada como segredo hardcoded;
- fallback literal (`${VAR:-valor}`) continua bloqueado como possível segredo hardcoded;
- a correção deve possuir testes positivo e negativos e não adicionar allowlist por arquivo.
