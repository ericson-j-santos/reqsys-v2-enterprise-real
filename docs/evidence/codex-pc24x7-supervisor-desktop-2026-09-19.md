# Evidência — Codex PC24x7 Supervisor — Desktop — 2026-09-19

## Escopo
Validação local/DEV no host `DESKTOP-PDQK954`. Nenhum deploy ou promoção de ambiente foi executado.

## Versão avaliada
Branch: `feat/codex-pc24x7-supervisor`

## Evidência física positiva
- Ollama `127.0.0.1:11434`: saudável, versão `0.34.2`.
- Gateway `127.0.0.1:8008`: saudável, serviço `reqsys-ollama-local-gateway`.
- Backend `127.0.0.1:8000`: saudável, banco local isolado OK.
- Primeiro ciclo recuperou fisicamente gateway e backend: `restart_counts.gateway=1`, `restart_counts.backend=1`.
- Smoke ReqSys → `ollama_gateway` → Ollama:
  - modelo solicitado: `gemma4:31b-cloud`;
  - modelo efetivo: `gemma4:31b-cloud`;
  - `fallback_used=false`;
  - `provider=ollama_gateway`;
  - `published_to_reqsys=false`;
  - latência observada: ~5,84 s.
- Perfil persistente mantém `gemma4:26b-q8-code` como fallback local.

## Persistência Windows
Tentativas governadas:
1. `schtasks /Create` com ação longa: recusado por limite de 261 caracteres.
2. Launcher curto `%LOCALAPPDATA%\ReqSys\CodexSupervisor\run.py`: removeu o limite de tamanho.
3. Registro `AtStartup` via Task Scheduler COM/S4U: recusado pelo Windows com HRESULT `0x80070005` (`Access Denied`).

Estado seguro aplicado:
- `HKCU Run` configurado;
- `persistence_mode=hkcu_run_at_logon`;
- `requires_user_logon=true`;
- não é classificado como headless 24x7.

## Controle independente do runner GitHub
- nenhum serviço Windows GitHub Actions Runner com start automático foi encontrado;
- nenhuma tarefa de boot do GitHub Actions Runner foi encontrada;
- portanto o runner atual não pode ser usado como prova de bootstrap pós-reboot independente de login.

## Estado do critério pós-reboot
`postboot-check --require-reboot` permanece **não executado**, pois:
- nenhum reboot foi realizado nesta validação;
- a persistência `AtStartup` está bloqueada por ACL administrativa.

O incremento não pode ser declarado 24x7 headless até existir autorização administrativa específica para criar a persistência de boot e uma validação pós-reboot real.

## Segurança
- produção tocada: não;
- deploy realizado: não;
- segredo lido ou gravado: não;
- endpoint de serviços: loopback;
- identidade do smoke: demo sintética;
- publicação no ReqSys durante smoke: não.
