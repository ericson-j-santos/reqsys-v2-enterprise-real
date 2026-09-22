# Runtime Executive Public Smoke

## Resumo

Adiciona smoke dedicado para validar que `runtime-executive.html` e `runtime-executive-index.json` são publicados juntos como par operacional estático.

## Alterações

- Cria `scripts/smoke_runtime_executive_static_publication.py`.
- Atualiza o workflow `Ops Dashboard` para executar o smoke após preparar o artifact estático.
- Publica o artifact `runtime-executive-public-smoke` com evidência JSON do smoke.

## Validações

O smoke verifica:

- existência de `runtime-executive.html` no root publicado;
- existência de `data/runtime-executive-index.json` no mesmo artifact;
- `CONTRACT_URL` da página apontando para `./data/runtime-executive-index.json`;
- presença de elementos executivos mínimos na página;
- presença dos links oficiais no contrato;
- presença dos guardrails `no_runtime_github_api_call` e `official_runtime_executive_deeplink`;
- ausência de chamadas proibidas a GitHub/API ou uso de token no HTML.

## Guardrails

- Smoke offline/read-only.
- Sem deploy.
- Sem chamada externa.
- Sem segredo.
- Compatível com artifact estático e runtime público.

## Próximo incremento seguro

Conectar este smoke ao ciclo de publicação pós-deploy para validar a mesma dupla `runtime-executive.html` + `runtime-executive-index.json` no endpoint público real.
