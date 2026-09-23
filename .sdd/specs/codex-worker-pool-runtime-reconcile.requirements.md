# Requisitos — Reconciliação do runtime Codex Worker Pool no PC24x7

## Problema evidenciado

O runner `DESKTOP-PDQK954` voltou a adquirir jobs, porém o smoke real no SHA `e41076b611450f2e49d5e9988045e65cb91a17fe` falhou com `worker_pool_service_container_missing`. O serviço Docker do Worker Pool não se auto-reconciliava quando deixava de existir um container ativo.

## Requisitos

1. Executar somente em `DESKTOP-PDQK954`, Windows e ambiente DEV.
2. Reconciliar apenas o service Compose fixo `codex-worker-pool`.
3. Não aceitar comando, host, porta, serviço ou arquivo de segredo arbitrário.
4. Reusar o token já provisionado sem ler seu conteúdo; quando nenhuma fonte acessível existir, criar uma única vez um token interno local/DEV criptograficamente aleatório em `%LOCALAPPDATA%\\ReqSys\\CodexWorkerPool`, sem expor o valor e sem rotacionar arquivo existente.
5. Na ausência da variável host do token, selecionar deterministicamente o mount existente do container histórico mais recente do mesmo service, priorizando identidade do compose e binding canônico quando preservados.
6. Falhar fechado quando não houver candidato válido ou quando o candidato mais recente permanecer ambíguo.
7. Obter o SHA canônico atual de `ericson-j-santos/chatgpt-operational-rules@main` e passá-lo ao runtime.
8. Executar `docker compose up -d --build --remove-orphans` apenas para o service fixo.
9. Validar `/health` em `127.0.0.1:8097`.
10. Exigir exatamente um container ativo com binding `127.0.0.1:8097 -> 8097/tcp`.
11. Publicar evidência sanitizada sem token, valor de segredo ou caminho do arquivo de token.
12. Não tocar produção, HML/STG, permissões ou segredos.
13. Não criar novo workflow: a reconciliação deve ocorrer dentro do workflow canônico `Codex Worker Pool Smoke DEV`.
14. O smoke deve permanecer inputless e usar o runner allowlisted PC24x7.
15. A conclusão exige `WORKER_POOL_RUNTIME_RECONCILED` seguido de `WORKER_POOL_SMOKE_PASSED` no mesmo workflow/SHA.

## Critérios de aceite

- descoberta histórica escolhe de forma determinística o mount válido mais recente;
- ambiguidade no candidato mais recente falha fechado;
- endpoint não canônico não é aceito como runtime ativo;
- bootstrap local do token é idempotente: cria apenas quando ausente e nunca sobrescreve um arquivo existente válido;
- evidência não contém caminho do token nem conteúdo do segredo;
- o smoke canônico reconcilia o runtime antes da validação funcional;
- replay idempotente, leitura independente, lane sintética desabilitada e task sem lease permanecem obrigatórios;
- a alteração não aumenta a quantidade de workflows do repositório.
