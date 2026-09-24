# Codex PC24x7 Supervisor — requisitos

## Objetivo
Manter os caminhos locais `ReqSys → ollama_gateway → Ollama` e `GitHub Copilot → bridge MCP → ollama_gateway → Ollama` disponíveis no Desktop PC24x7 sem depender de preparação manual do processo MCP.

## Requisitos
1. O supervisor opera somente em `DESKTOP-PDQK954`, Windows e ambiente local/DEV.
2. Ollama, gateway, bridge MCP e backend devem escutar somente em loopback nas portas `11434`, `8008`, `8010` e `8000`.
3. O provider deve ser lido de `HKCU\Environment`; o bearer MCP pré-provisionado pode ser consumido somente de `OLLAMA_MCP_BEARER_TOKEN` no ambiente do processo e nunca pode ser copiado para Git, logs, metadata ou evidência.
4. O bridge MCP deve falhar fechado com `mcp_bearer_token_not_configured` quando o bearer não estiver disponível e deve chamar exclusivamente o gateway `http://127.0.0.1:8008`.
5. O modelo primário é o já configurado no perfil e o fallback local permanece explícito; ambos formam a allowlist do bridge MCP.
6. O supervisor só pode encerrar/reiniciar processos iniciados pela própria instância; porta ocupada por processo não reconhecido ou sem health esperado falha fechada.
7. O smoke ReqSys deve autenticar com identidade demo sintética apenas no backend local, chamar `/v1/codex/analyze` com `publicar_no_reqsys=false` e provar resposta real.
8. O gateway deve registrar `requested_model`, modelo efetivo e `fallback_used`.
9. A release imutável do supervisor deve incluir `services/ollama-mcp-bridge`; o processo MCP deve ser supervisionado e recuperado junto com Ollama, gateway e backend.
10. A instalação deve preferir Task Scheduler `ONSTART` sem senha. Falha de permissão pode cair para `HKCU Run`, mas esse estado deve ser explicitamente `requires_user_logon=true` e não pode ser chamado de headless 24x7.
11. O launcher UAC governado deve elevar somente a ação exata `register-task-com` da release imutável instalada, exigir confirmação explícita, permanecer restrito ao Desktop e verificar `AtStartup + S4U` antes de remover o fallback `HKCU Run`.
12. Estado, logs e evidência ficam em `%LOCALAPPDATA%\ReqSys\CodexSupervisor`.
13. O release instalado é imutável e identificado pelo SHA de origem.
14. O pós-reboot deve comparar boot epoch e só aprovar quando houver reboot real, os quatro componentes estiverem saudáveis, persistência AtStartup e smoke posterior.
15. Nenhum deploy, produção, criação/rotação de segredo ou promoção de ambiente integra este incremento.

## Critérios de aceite
- testes unitários do supervisor e do launcher UAC verdes;
- contrato prova que ausência de bearer MCP falha fechada e que o bridge usa somente gateway loopback `:8008`;
- release imutável inclui o bridge MCP e runtime health exige `11434/8008/8010/8000`;
- ciclo físico no Desktop comprova os quatro componentes + smoke ReqSys→IA;
- recuperação de componentes é observável por health/restart count, incluindo `mcp_bridge`;
- persistência instalada e classificada corretamente;
- o fallback `HKCU Run` só é removido depois de a tarefa `AtStartup/S4U` ser lida independentemente;
- `READY_FOR_PR=passed` no HEAD exato;
- E2E GitHub.com → HTTPS MCP → PC24x7 → Ollama permanece obrigatório para conclusão funcional do agente;
- E2E pós-reboot só é concluído após reboot real e `postboot-check --require-reboot` verde.
