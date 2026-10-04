# Runtime Executive Deep Link no Estado Único

## Resumo

Integra a página pública `runtime-executive.html` como superfície oficial do Estado Único ReqSys.

## Alterações

- Adiciona `scripts/enrich_runtime_executive_deeplinks.py` para enriquecer contratos gerados.
- Adiciona `scripts/validate_runtime_executive_deeplink_state.py` para validar consistência dos deep links.
- Atualiza o workflow `Ops Dashboard` para enriquecer e validar os contratos antes de publicar o artifact.
- Atualiza os contratos estáticos atuais:
  - `runtime-executive-index.json`
  - `strategic-governance-index.json`
  - `executive-brief.json`

## Evidência governada

A página `docs/ops-dashboard/runtime-executive.html` passa a ser referenciada oficialmente por:

- `runtime_executive_index.links.runtime_executive_page`
- `strategic_governance_index.links.runtime_executive_page`
- `executive_brief.links.runtime_executive_page`
- `executive_brief.estado_unico.public_surfaces.runtime_executive_page`

## Guardrails

- Sem chamada GitHub/API em runtime.
- Validação offline/read-only.
- Links locais oficiais validados contra arquivos versionados.
- Contratos enriquecidos antes da publicação do artifact `ops-dashboard-static`.

## Próximo incremento seguro

Consolidar smoke público dedicado para verificar, no artifact publicado, que `runtime-executive.html` e `runtime-executive-index.json` são publicados juntos e carregáveis como par operacional.
