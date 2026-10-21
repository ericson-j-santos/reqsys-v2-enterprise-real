# Requisitos — Supervisor autônomo do runtime DEV

## Objetivo

Eliminar ações humanas repetitivas da operação pública do ReqSys DEV no PC24x7.

## Requisitos funcionais

1. Recuperar containers DEV conhecidos quando estiverem parados.
2. Validar `/task-console` e `/api/health` antes e depois da reconciliação.
3. Reconciliar automaticamente os dois Cloudflare Quick Tunnels.
4. Detectar a capability do Tailscale Funnel sem abrir navegador repetidamente.
5. Ativar/reconciliar o Funnel automaticamente quando a capability já tiver sido concedida.
6. Enquanto o consentimento único não existir, manter Cloudflare operacional e registrar
   `TAILSCALE_FUNNEL_CONSENT_REQUIRED`.
7. Persistir estado e log fora do Git.
8. Executar periodicamente por Task Scheduler do usuário, sem privilégio elevado.
9. Não alterar HML ou PROD.

## Critérios de aceite

1. Testes comprovam escopo somente DEV e containers esperados.
2. Instalação cria tarefa recorrente `ReqSys-Dev-Runtime-Supervisor`.
3. Supervisor local conclui com gateway DEV saudável.
4. Cloudflare continua respondendo HTTP 200.
5. Ausência da capability Funnel não derruba DEV nem abre consentimento em loop.
6. Após concessão da capability, o Funnel passa a ser reconciliado automaticamente.

## Contrato preventivo do instalador (21/10/2026)

Esta atualização corrige somente o contrato de evidência do instalador existente em DEV; não modifica o agendamento instalado, a identidade Windows, a chave Ed25519 protegida por DPAPI nem o runtime físico. A leitura do instalador na branch e sua validação isolada não comprovam recuperação do PC24x7.

### Critérios de aceite adicionais

1. Se `schtasks /Create` falhar, não executar `schtasks /Run` nem retornar sucesso.
2. Se `schtasks /Run` retornar código diferente de zero, o instalador retorna exit code 2 e `status=trigger_failed`, preservando o código de retorno; jamais `status=installed` ou `0`.
3. Se o disparo for aceito, retornar somente `status=registered_pending_runtime_verification`, `trigger_accepted=true` e `runtime_verified=false`. O aceite do comando não comprova execução da tarefa, publicação ou entrega.
4. Após registro da tarefa, reler `Principal.LogonType` pela API do Task Scheduler. A versão atual usa `TASK_LOGON_INTERACTIVE_TOKEN=3` e deve declarar `requires_interactive_session=true` e `independent_of_user_logon=false`; divergência no readback bloqueia o disparo.
5. Cobrir cenários positivo, negativo, divergência de logon, erro de criação e replay em testes de regressão sem acessar Windows/DPAPI reais. Integrar esses testes ao Pre-PR Readiness no SHA final.
6. A execução realmente independente do login e a causa física da interrupção permanecem **não comprovadas**. Qualquer mudança de tipo de logon, chave DPAPI, permissões ou instalação exige projeto reversível, verificação de rede/identidade e E2E no host autorizado. Proibido inferir compatibilidade do modo S4U.

### Evidências esperadas

- Testes: `tests/test_pc24x7_dev_runtime_supervisor.py`.
- Fonte: `scripts/pc24x7_dev_runtime_supervisor_install.py`.
- Issue do piloto: #1596; incidente correlato: #3002.
- Runtime real: `LastRunResult`, `LogonType`, identidade do produtor, histórico do agendador, SHA do runtime e dois ciclos independentes de locator assinado no mesmo host.
