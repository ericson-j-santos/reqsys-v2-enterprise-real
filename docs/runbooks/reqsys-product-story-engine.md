# ReqSys Product Story Engine

## Objetivo

Converter entregas consolidadas e evidenciadas do ReqSys em drafts de apresentação pública do produto, com rastreabilidade por PR/SHA e aprovação humana obrigatória antes de qualquer publicação externa.

## Fonte de verdade

O incremento consome o artifact `reqsys-weekly-accomplishment-log`, produzido por `.github/workflows/reqsys-weekly-accomplishment-log.yml`.

Um item só pode ficar `READY_FOR_HUMAN_REVIEW` quando as quatro dimensões abaixo forem verdadeiras:

- `implemented`
- `validated`
- `evidenced`
- `consolidated`

Lacunas de evidência, ausência de PR/SHA ou sinais de conteúdo sensível bloqueiam o candidato.

## Fluxo

```text
ReqSys/GitHub
  -> ReqSys Weekly Accomplishment Log
  -> Product Story Engine
  -> JSON/Markdown review-only
  -> revisão humana
  -> publicação externa futura
```

O workflow é acionado após conclusão verde do log semanal. Também pode ser executado manualmente para reconstruir drafts a partir do último run semanal verde.

## Saídas

Artifact: `reqsys-product-story-engine`

Arquivos:

- `product-story-candidates.json`
- `product-story-candidates.md`

Cada candidato contém:

- PR e URL;
- SHA da entrega;
- checks coletados pelo log semanal;
- estado das cinco dimensões;
- blockers;
- score operacional de ordenação;
- `content_hash` SHA-256 para idempotência;
- texto draft para LinkedIn;
- `visual_brief` para geração posterior de imagem/carrossel;
- estado de aprovação.

## Estados

- `READY_FOR_HUMAN_REVIEW`: evidência mínima atendida e nenhum sinal sensível detectado.
- `BLOCKED`: falta evidência ou há sinal que exige tratamento antes da divulgação.

O score não representa qualidade do produto nem percentual de conclusão. Serve somente para ordenar candidatos prontos.

## Segurança e governança

- modo fixo `review_only`;
- nenhuma permissão de escrita no repositório;
- nenhuma chamada à API do LinkedIn;
- nenhuma publicação automática;
- conteúdo sensível falha fechado;
- aprovação humana permanece obrigatória.

## Validação

```bash
python -m unittest -v tests/test_reqsys_product_story_engine.py
python -m unittest -v tests/test_reqsys_product_story_workflow.py
```

Antes de abrir PR, o `Pre-PR Readiness Gate` deve retornar `READY_FOR_PR=passed` no HEAD exato e comprovar `behind_by=0`.

## Próximo incremento

Depois que esta fatia estiver consolidada, o próximo passo é adicionar um adaptador de aprovação/publicação separado, com autenticação oficial do LinkedIn e idempotência baseada no `content_hash`. Esse adaptador não deve publicar sem aprovação explícita registrada.
