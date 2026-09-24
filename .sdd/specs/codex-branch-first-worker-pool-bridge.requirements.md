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
6. O workflow de handoff deve executar somente por `workflow_dispatch`, no runner allowlisted `[self-hosted, Windows, X64, pc24x7, reqsys-dev]`.
7. O workflow deve fazer checkout do `base_sha` imutável informado pelo orquestrador.
8. O bridge só pode acessar Worker Pool por HTTP em loopback (`127.0.0.1`, `localhost` ou `::1`).
9. O bearer token deve ser lido exclusivamente de arquivo já provisionado por `CODEX_WORKER_POOL_API_TOKEN_FILE` ou `CODEX_WORKER_POOL_API_TOKEN_FILE_HOST`; o valor não pode entrar em workflow, log ou evidência.
10. O primeiro `POST /v1/tasks` deve ser repetido com a mesma identidade e o replay deve retornar `created=false` e o mesmo `task_id`.
11. Um `GET /v1/tasks/{task_id}` separado deve confirmar `task_id`, repositório, issue, `request_id` e `base_sha`.
12. A evidência não pode conter `lease_token`.
13. O Worker Pool existente permanece responsável por Builder → `produced_sha` → Validator independente → `completed`; este incremento não duplica essa lógica.
14. Ausência de token, Worker Pool não saudável, URL não-loopback, SHA inválido ou readback divergente devem falhar fechado.
15. O incremento não executa merge, deploy, produção, mudança de segredo, permissão administrativa ou reboot.
16. Após health positivo, o bridge deve consultar `GET /v1/contract` antes de enfileirar trabalho.
17. Quando o endpoint existir, `contract_name` deve ser `engineering-worker-pool` e `contract_version` deve ser `v1`; divergência deve falhar fechado sem fallback.
18. Durante a janela de migração, somente HTTP 404 do endpoint de contrato pode ativar `legacy_fallback`; 401, 503, erro de transporte ou JSON inválido permanecem bloqueantes.
19. A evidência deve registrar `contract_mode`, versão esperada e se o fallback legado foi usado, sem registrar token.
20. O parâmetro `--require-contract-v1` deve desabilitar o fallback legado sem exigir nova alteração de código.

## Critérios de aceite

- testes do fallback provam dispatch antes do marcador, deduplicação e recuperação de marcador legado;
- testes do bridge provam positivo, replay, leitura independente, ausência de trabalho, URL não-loopback, SHA inválido, contrato v1, fallback exclusivo em 404 e bloqueio de versões incompatíveis;
- teste contratual do workflow prova gatilho manual, runner fixo, checkout por SHA e ausência de secret inline;
- `check_self_hosted_runner_governance.py` aceita apenas o workflow explicitamente allowlisted;
- Pre-PR Readiness deve retornar `READY_FOR_PR=passed` no HEAD exato;
- a conclusão física de #1766 permanece parcial até uma task real produzir branch/SHA, passar por Validator independente e chegar a `READY_FOR_PR`/PR sem duplicidade.

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
