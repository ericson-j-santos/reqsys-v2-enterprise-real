# Runtime Executive Post-Deploy Smoke

## Resumo

Adiciona validação pós-deploy do endpoint público do Runtime Executive, verificando a página HTML e o contrato JSON servidos por HTTP.

## Alterações

- Cria `scripts/smoke_runtime_executive_public_endpoint.py`.
- Cria workflow `.github/workflows/runtime-executive-post-deploy-smoke.yml`.
- Publica artifact `runtime-executive-post-deploy-smoke` com evidência JSON e resumo Markdown.

## Validações

O smoke pós-deploy verifica:

- disponibilidade pública de `runtime-executive.html`;
- disponibilidade pública de `runtime-executive-index.json`;
- `CONTRACT_URL` compatível com `./data/runtime-executive-index.json`;
- presença dos elementos mínimos do painel executivo;
- integridade mínima do contrato do Estado Único;
- presença dos guardrails obrigatórios;
- ausência de chamadas GitHub/API e tokens no HTML.

## Ambientes

O workflow é parametrizável por:

- `base_url`;
- `page_path`;
- `contract_path`;
- `strict`.

Isso permite uso em DEV/STG/PROD sem hardcode no código Python.

## Guardrails

- Read-only.
- Sem secrets.
- Sem deploy.
- Sem mutação remota.
- Strict gate habilitado em execução manual.
- Schedule em modo não bloqueante para evitar falso negativo por instabilidade transitória.

## Próximo incremento seguro

Conectar a evidência pós-deploy ao Runtime Validation Consolidator e ao Executive Brief para que o Estado Único reflita a validação pública real.
