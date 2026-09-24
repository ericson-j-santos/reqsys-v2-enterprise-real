# Codex PC24x7 Supervisor

## Escopo
Runtime local/DEV do Codex e do bridge MCP do Ollama no Desktop PC24x7. Não substitui HML/PROD e não promove ambiente.

## Componentes
- Ollama: `127.0.0.1:11434`
- ReqSys Ollama Gateway: `127.0.0.1:8008`
- GitHub Copilot Ollama MCP Bridge: `127.0.0.1:8010/mcp`
- ReqSys backend local: `127.0.0.1:8000`

O supervisor usa o modelo primário/fallback já persistido no perfil Windows. O backend gerenciado usa SQLite local isolado e login demo apenas em loopback para o smoke sintético.

O bridge MCP herda somente o bearer pré-provisionado em `OLLAMA_MCP_BEARER_TOKEN`; o valor não é gravado em metadata, estado, log ou evidência. Se o bearer estiver ausente, o supervisor falha fechado com `mcp_bearer_token_not_configured`. O bridge continua chamando exclusivamente o gateway loopback `:8008`.

## Persistência
A instalação tenta criar `\Automation\ReqSysCodexPC24x7Supervisor` com gatilho `ONSTART`, usuário atual, sem senha e privilégio limitado. Se isso for negado, configura `HKCU Run`; o status então informa `requires_user_logon=true` e o critério headless continua aberto.

A release imutável identificada pelo SHA inclui backend, gateway, bridge MCP e o próprio supervisor. A recuperação periódica cobre os quatro componentes e registra `mcp_bridge` nos contadores de reinício.

## Evidência
Arquivos sob `%LOCALAPPDATA%\ReqSys\CodexSupervisor`:
- `metadata.json`
- `state.json`
- `last-smoke.json`
- `postboot-evidence.json`
- `logs/*.log`

O smoke nunca publica no ReqSys. Nenhuma evidência deve conter o bearer MCP.

## Pós-reboot
Após um reboot real, executar `postboot-check --require-reboot`. A prova só é válida quando o boot epoch mudou, a persistência é `AtStartup`, Ollama/gateway/bridge MCP/backend estão saudáveis e existe smoke posterior.

A conclusão funcional do agente continua exigindo evidência separada do fluxo real `GitHub.com → HTTPS MCP → PC24x7 → Ollama`, com o mesmo SHA/ambiente e controle negativo de bearer inválido.
