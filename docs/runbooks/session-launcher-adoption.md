# Adoção do Session Launcher no ReqSys

Este runbook define o ponto de entrada obrigatório para sessões técnicas governadas que executem comandos locais ou remotos no ReqSys.

## Pré-requisitos

- Command Gateway instalado com regras `>= 1.6.0`.
- Repositório local limpo no SHA que será usado como base.
- SHA esperado obtido por leitura independente da `main` remota.

## Fluxo obrigatório

1. Executar `session_launcher.py` com `--expected-head <SHA-completo>`.
2. Exigir `SESSION_LAUNCH_OK` e `state_validated=true`.
3. Registrar `session_id`, `target_path`, `head` e `snapshot_sha256`.
4. Executar risco 2 somente em `target_path` pelo Command Gateway.
5. Tratar divergência de HEAD ou preflight inválido como bloqueio fail-closed.
6. Não usar fetch oculto, shell irrestrito ou fallback direto de terminal.

## Evidência mínima

```text
SESSION_LAUNCH_OK
state_validated=true
session_id=<id>
target_path=<worktree isolado>
head=<sha completo>
snapshot_sha256=<sha256>
```

## Controles contra falso positivo

- `--expected-head` divergente deve bloquear a sessão.
- risco 2 na base deve ser bloqueado.
- risco 2 no worktree materializado deve ser permitido.
- a base deve permanecer sem alterações após o trabalho isolado.

## Critério de conclusão

A sessão é válida somente quando o SHA esperado coincide com o HEAD materializado, o snapshot tem integridade confirmada e a alteração ocorre exclusivamente no worktree reservado.
