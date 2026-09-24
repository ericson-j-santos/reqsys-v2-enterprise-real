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
12. Após criação atômica de um token ou quando um `401` comprovar mismatch e a comparação em memória provar que o conteúdo do bind mount no container diverge do arquivo host canônico, o serviço `codex-worker-pool` deve ser recriado pelo mesmo projeto Docker Compose (`--force-recreate --no-deps --no-build --pull never`) para remontar o arquivo. A recriação deve reutilizar o `Image` SHA-256 imutável do container corrente por override temporário, sem build, pull ou resolução de uma tag mutável. Os paths de `working_dir/config_files` dos labels podem ser reutilizados somente enquanto ainda existirem; se apontarem para worktree efêmero removido, o fallback é permitido exclusivamente para o arquivo compose canônico versionado da sessão atual, com basename esperado e contrato mínimo validado. Imagem corrente ausente/inválida deve falhar fechado como `worker_pool_running_image_invalid`. Um simples `docker restart` não é evidência suficiente para bind mount de arquivo. Se host e container já contiverem o mesmo token e a API ainda responder `401`, falhar fechado como `worker_pool_auth_process_mismatch`, sem rotação.
13. A evidência pode informar somente rotação/reuso, recriação do serviço, ressincronização do bind mount, HTTP status, readback, `reason` sanitizado de readiness e, em falha de recriação Compose, apenas `compose_cli_version`, `compose_creator_version` e `compose_error_fingerprint` SHA-256. O stderr bruto nunca pode ser persistido. Respostas HTTP 503 podem ser lidas apenas para classificar, sem registrar token, caminho sensível ou valor de variável. Devem existir reason codes distintos para endpoint indisponível, arquivo de auth não visível no container, `EXPECTED_RULES_SHA` ausente, mismatch de token, referência de imagem inválida e incompatibilidade de CLI Compose; `secret_value_exposed=false` é obrigatório.
14. Produção, deploy, permissões administrativas, firewall, outros serviços e outros segredos não podem ser alterados.
15. Após a restauração aprovada, deve ser executado o smoke normal no mesmo SHA vigente e exigido `WORKER_POOL_SMOKE_PASSED`.

## Critérios de aceite

- testes unitários positivos e negativos do restaurador, incluindo criação segura do diretório pai canônico, detecção de bind mount stale após troca atômica, recuperação controlada de compose source quando labels apontam para worktree removido, reutilização obrigatória da imagem SHA-256 imutável do container corrente sem build/pull, rejeição de imagem/basename/contrato inesperados, classificação sanitizada de falhas Compose com versões/fingerprint sem stderr bruto, recriação fail-closed do serviço, controle que impede recriação quando host/container já coincidem, preservação sanitizada do payload 503 e reason codes específicos de readiness, e da allowlist Risk3 temporária verdes;
- teste de contrato prova que restore e smoke possuem rotas distintas;
- runner policy continua allowlistando apenas o workflow já existente;
- restore real retorna `WORKER_POOL_TOKEN_RESTORE_PASSED`;
- smoke subsequente retorna `WORKER_POOL_SMOKE_PASSED`;
- nenhum valor sensível aparece nas evidências.
