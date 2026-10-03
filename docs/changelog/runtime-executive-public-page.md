# Runtime Executive Public Page

## Resumo

Adiciona uma página pública dedicada para a visão executiva de runtime do ReqSys, consumindo o contrato estático `docs/ops-dashboard/data/runtime-executive-index.json`.

## Alterações

- Cria `docs/ops-dashboard/runtime-executive.html`.
- Adiciona validação offline/read-only em `scripts/validate_runtime_executive_public_page.py`.
- Inclui a página no artifact `ops-dashboard-static`.
- Integra a validação ao workflow `Ops Dashboard`.

## Guardrails

- Sem chamada para GitHub API em runtime.
- Sem uso de token ou segredo no frontend estático.
- Consumo exclusivo do contrato público local `./data/runtime-executive-index.json`.
- Fallback visual seguro em caso de indisponibilidade do contrato.

## Próximo incremento seguro

Publicar deep link governado para a página Runtime Executive nos contratos executivos e no painel principal após estabilização do PR anterior relacionado ao Runtime Executive Panel.
