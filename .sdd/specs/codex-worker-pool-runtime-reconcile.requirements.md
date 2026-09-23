# Requisitos — Reconciliação do runtime Codex Worker Pool no PC24x7

## Problema evidenciado

O runner `DESKTOP-PDQK954` voltou a adquirir jobs no SHA `e41076b611450f2e49d5e9988045e65cb91a17fe`, porém o smoke real falhou com `worker_pool_service_container_missing`. O serviço Docker do Worker Pool não se auto-reconcilia quando todos os containers do service deixam de estar ativos.

## Requisitos

1. Executar somente em `DESKTOP-PDQK954`, Windows e ambiente DEV.
2. Reconciliar apenas o service Compose fixo `codex-worker-pool`.
3. Não aceitar comando, host, porta, serviço ou arquivo de segredo arbitrário.
4. Reusar o token já provisionado sem ler seu conteúdo.
5. Quando a variável host do token não estiver disponível, recuperar somente o caminho de bind mount já registrado no histórico de containers do mesmo service.
6. Falhar fechado se houver zero ou mais de uma origem distinta para o bind mount canônico.
7. Obter o SHA canônico atual de `ericson-j-santos/chatgpt-operational-rules@main` e passá-lo ao runtime.
8. Executar `docker compose up -d --build --remove-orphans` apenas para o service fixo.
9. Validar `/health` em `127.0.0.1:8097`.
10. Exigir exatamente um container ativo do service com binding `127.0.0.1:8097 -> 8097/tcp`.
11. Publicar evidência sanitizada sem token, valor de segredo ou caminho do arquivo de token.
12. Não tocar produção, HML/STG, permissões ou segredos.
13. O workflow deve ser inputless e usar o runner allowlisted PC24x7.
14. A correção só é terminal quando o reconciliador passar e o smoke `Codex Worker Pool Smoke DEV` retornar `WORKER_POOL_SMOKE_PASSED` no SHA vigente da main.

## Critérios de aceite

- descoberta por histórico de mount funciona mesmo com containers parados;
- origens de token ambíguas falham fechado;
- endpoint não canônico não é aceito;
- evidência não contém caminho do token nem conteúdo do segredo;
- workflow de reconciliação conclui no PC24x7;
- smoke subsequente comprova replay idempotente, leitura independente, lane sintética desabilitada e task sem lease.
