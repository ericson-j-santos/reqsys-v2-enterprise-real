# ADR-034 — Consolidação do Runtime Operacional Autônomo Governado

## Status

Aceito incrementalmente em 2026-06-26.

## Contexto

O ReqSys já possuía workflows e scripts separados para validação de runtime, remediação governada, analytics, promoção e evidências. O próximo incremento seguro é evitar duplicidade arquitetural e consolidar essas capacidades no `Runtime Health Validator`, sem executar ações destrutivas nem alterar ambientes.

## Decisão

Evoluir `scripts/runtime_health_validator.py` como ponto de consolidação operacional para produzir um artifact navegável com:

- status executivo;
- classificação de maturidade operacional;
- backlog automático de gaps e remediações seguras;
- detecção inicial de regressão baseada em workflows vermelhos;
- política de rollback governado com ações destrutivas bloqueadas;
- matriz de sincronização Fly.io para dev, homolog e prod;
- mapa de consolidação de evidências para dashboards e auditoria.

O workflow existente `.github/workflows/runtime-health-validator.yml` permanece como orquestrador, publicando o artifact `runtime-health-validator-evidence`.

## Regras de governança

| Tema | Decisão |
|---|---|
| Autocorreção | Restrita a rerun de jobs allowlisted e não destrutivos. |
| Produção | Sem alteração automática; exige promoção governada e aprovação explícita. |
| Rollback | Política gerada como evidência; execução manual/aprovada. |
| Backlog | Gaps não autocorrigíveis viram itens `OPS-GAP-*`. |
| Evidência | JSON canônico e `summary.md` navegável no artifact. |
| Duplicidade | Reuso do validador existente em vez de criar novo runtime paralelo. |

## Consequências

### Benefícios

- Aumenta rastreabilidade ponta a ponta sem acionar infraestrutura real.
- Cria base auditável para dashboards, status executivo e decisões de operação.
- Mantém default deny para ações destrutivas.
- Reduz dispersão entre analytics, remediação e evidências.

### Limitações

- Health checks externos continuam declarados como matriz de sincronização, não como probe de rede neste incremento.
- Abertura automática de issues/backlog ainda não é executada; o backlog é gerado como artifact.
- Rollback real permanece bloqueado até existir aprovação e metadata validada.

## Rollback

Reverter as alterações em:

- `scripts/runtime_health_validator.py`;
- `tests/test_runtime_health_validator.py`;
- `docs/adr/ADR-034-autonomous-operational-runtime-consolidation.md`;
- `docs/ci/AUTONOMOUS_OPERATIONAL_RUNTIME.md`;
- `CHANGELOG.md`.
