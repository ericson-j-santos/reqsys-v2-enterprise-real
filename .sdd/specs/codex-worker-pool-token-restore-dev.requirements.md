# Codex Worker Pool — restauração governada do token DEV

## Escopo

Restaurar a autenticação local do Codex Worker Pool no PC24x7 quando o arquivo bindado estiver ausente ou vazio, sem expor o valor e sem tocar STG/HML/PROD.

## Requisitos

1. A operação deve executar somente no host `DESKTOP-PDQK954`, pelo runner `[self-hosted, Windows, X64, pc24x7, reqsys-dev]`.
2. O comando externo deve ser exato: `/reqsys run codex-worker-pool-token-restore-dev`.
3. O Authorized Actions Gateway deve mapear esse comando somente para `codex-worker-pool-smoke-dev.yml` com `mode=restore`.
4. O smoke normal deve permanecer em `mode=smoke` e não pode restaurar ou rotacionar credencial.
5. A execução de restauração deve usar `session_launcher.py` e exigir `SESSION_LAUNCH_OK`, `state_validated=true` e SHA igual ao `main` despachado.
6. Antes da mutação deve ser instalada somente a action exata `reqsys.worker-pool-auth-file-restore.dev`, com escopo `repo://reqsys/environment/dev/worker-pool`, validade máxima de 30 minutos e comando fixo sem valor sensível; a action deve ser removida automaticamente após a tentativa. A mutação do arquivo deve passar por `owner_risk3_gateway.py` usando essa allowlist exata, sem depender do modo DEV global.
7. Se o arquivo existir, for legível, não vazio e tiver comprimento mínimo válido, deve ser reutilizado sem rotação.
8. Se o arquivo estiver ausente ou vazio, um novo token deve ser gerado localmente por CSPRNG e gravado atomicamente apenas no caminho já comprovado pelo bind mount canônico do container ativo. Se o diretório pai desse caminho canônico não existir, ele deve ser criado localmente antes da escrita; nenhum diretório pode ser criado a partir de caminho não comprovado.
9. O caminho do arquivo deve ser derivado exclusivamente do único container ativo `codex-worker-pool` que prove `127.0.0.1:8097 -> 8097/tcp` e mount para `/run/secrets/codex_worker_pool_api_token`.
10. Caminho ambíguo, falha ao criar/validar o diretório pai canônico, acesso negado, arquivo inválido ou container não único devem falhar fechado.
11. O valor do token não pode aparecer em stdout, stderr, artifact, GitHub output, resumo ou evidência.
12. Após rotação, o container deve ser reiniciado e a validação deve exigir `/health=200`, `auth_configured=true` e leitura autenticada independente de `/v1/snapshot=200`.
13. A evidência pode informar somente se houve rotação/reuso, restart, HTTP status e readback; deve registrar `secret_value_exposed=false`.
14. Produção, deploy, permissões administrativas, firewall, outros serviços e outros segredos não podem ser alterados.
15. Após a restauração aprovada, deve ser executado o smoke normal no mesmo SHA vigente e exigido `WORKER_POOL_SMOKE_PASSED`.

## Critérios de aceite

- testes unitários positivos e negativos do restaurador, incluindo criação segura do diretório pai canônico, e da allowlist Risk3 temporária verdes;
- teste de contrato prova que restore e smoke possuem rotas distintas;
- runner policy continua allowlistando apenas o workflow já existente;
- restore real retorna `WORKER_POOL_TOKEN_RESTORE_PASSED`;
- smoke subsequente retorna `WORKER_POOL_SMOKE_PASSED`;
- nenhum valor sensível aparece nas evidências.
