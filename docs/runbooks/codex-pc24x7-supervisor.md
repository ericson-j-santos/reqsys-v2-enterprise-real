# Codex PC24x7 Supervisor

## Escopo
Runtime local/DEV do Codex no Desktop PC24x7. Não substitui HML/PROD e não promove ambiente.

## Componentes
- Ollama: `127.0.0.1:11434`
- ReqSys Ollama Gateway: `127.0.0.1:8008`
- ReqSys backend local: `127.0.0.1:8000`

O supervisor usa o modelo primário/fallback já persistido no perfil Windows. O backend gerenciado usa SQLite local isolado e login demo apenas em loopback para o smoke sintético.

## Persistência
A instalação tenta criar `\Automation\ReqSysCodexPC24x7Supervisor` com gatilho `ONSTART`, usuário atual, sem senha e privilégio limitado. Se isso for negado, configura `HKCU Run`; o status então informa `requires_user_logon=true` e o critério headless continua aberto.

## Evidência
Arquivos sob `%LOCALAPPDATA%\ReqSys\CodexSupervisor`:
- `metadata.json`
- `state.json`
- `last-smoke.json`
- `postboot-evidence.json`
- `logs/*.log`

O smoke nunca publica no ReqSys.

## Pós-reboot
Após um reboot real, executar `postboot-check --require-reboot`. A prova só é válida quando o boot epoch mudou, a persistência é `AtStartup`, os três componentes estão saudáveis e existe smoke posterior.
