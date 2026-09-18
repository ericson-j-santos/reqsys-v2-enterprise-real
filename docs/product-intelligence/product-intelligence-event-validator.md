# Product Intelligence Event Validator

## Objetivo

Validar eventos da camada `ReqSys Product Intelligence Layer` contra o contrato funcional inicial.

## Capacidades implementadas

- Validador Python sem dependências externas.
- Validação do schema versionado.
- Validação do exemplo funcional.
- Checagem de campos obrigatórios.
- Checagem de enums funcionais.
- Checagem de scores de qualidade entre 0 e 100.
- Checagem de rastreabilidade.
- Checagem de governança funcional.
- Workflow CI dedicado.
- Artifact de validação.

## Arquivos

| Arquivo | Finalidade |
|---|---|
| `tools/product_intelligence/validate_product_intelligence_event.py` | Validador local/CI |
| `.github/workflows/product-intelligence-event-validator.yml` | Gate CI do modelo funcional |
| `docs/product-intelligence/product-intelligence-event-validator.md` | Documentação do incremento |

## Limites

- Não altera runtime produtivo.
- Não adiciona dependências externas.
- Não executa agentes automaticamente.
- Não integra bases corporativas reais.
- Não altera gates operacionais existentes.

## Próximo incremento recomendado

Requirement Quality Scoring Engine.
