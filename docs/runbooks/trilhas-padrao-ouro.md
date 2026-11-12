# Trilhas A–E — Padrão Ouro Consolidado

**Data:** 2026-06-27  
**ADR:** [`docs/adr/ADR-040-trilhas-padrao-ouro.md`](../adr/ADR-040-trilhas-padrao-ouro.md)

## Objetivo

Consolidar maturidade padrão ouro das cinco trilhas operacionais do ReqSys em um único relatório auditável.

## Trilhas

| ID | Nome | Foco |
|---|---|---|
| A | Runtime Público DEV | GitHub Pages, localizador assinado, Cloudflare, PC24x7; validação física separada |
| B | Observabilidade Enterprise | correlation_id, métricas, telemetria |
| C | UX Operacional | semáforo, drill-down, responsividade |
| D | Qualidade e Governança | matrix paralelizável de qualidade |
| E | Arquitetura Viva | architecture-as-code completo |

## Artefatos canônicos

| Item | Caminho |
|---|---|
| Registry | [`docs/architecture/trilhas/trilhas-registry.json`](../architecture/trilhas/trilhas-registry.json) |
| Hub HTML | [`docs/architecture/trilhas/index.html`](../architecture/trilhas/index.html) |
| Consolidador | [`scripts/trilhas_padrao_ouro.py`](../../scripts/trilhas_padrao_ouro.py) |
| Schema | [`docs/contracts/trilhas-padrao-ouro.schema.json`](../contracts/trilhas-padrao-ouro.schema.json) |
| Relatório | `audit/trilhas/trilhas-padrao-ouro-report.json` |
| Workflow | [`.github/workflows/trilhas-padrao-ouro.yml`](../../.github/workflows/trilhas-padrao-ouro.yml) |

## Critérios padrão ouro (por trilha)

1. ADR dedicado
2. Runbook operacional
3. Workflow CI report-only
4. Script validador
5. Schema JSON de contrato
6. `architecture-as-code.json`
7. Relatório em `audit/` ou `artifacts/`
8. Testes unitários do validador

## Validação local

```bash
# Consolidador (executa validadores A–E e agrega)
python scripts/trilhas_padrao_ouro.py

# Hub navegável
# Abrir docs/architecture/trilhas/index.html no browser

# Trilha individual
python scripts/trilha_a_runtime_publico.py
python scripts/trilha_b_observabilidade_enterprise.py
python scripts/trilha_c_ux_operacional.py
python scripts/trilha_d_qualidade_governanca.py --dimension ci-watch
python scripts/trilha_e_arquitetura_viva.py
```

## Semáforo consolidado

| Estado | Condição | Decisão |
|---|---|---|
| `passed` | Todas as trilhas `passed` | Continuar incremento |
| `passed_with_warnings` | Warnings sem erro duro | Revisar pendências antes de merge sensível |
| `failed` | Qualquer trilha `failed` | Corrigir trilha com gap antes de declarar padrão ouro |

## Guardrails

- Modo padrão: `report_only`.
- Não substitui CI obrigatório ReqSys v2 Enterprise.
- Não executa deploy, merge ou alteração de produção.

## Integração

- Mapa de rastreabilidade: [`docs/traceability/living-architecture-map.json`](../traceability/living-architecture-map.json)
- Coordenador: [`docs/runbooks/coordenador-principal-menu-operacional.md`](coordenador-principal-menu-operacional.md)


## Migração sem Fly.io — 12/11/2026

A Trilha A e a consolidação A–E passam a validar o **manifesto DEV vigente** em `infra/public-access-urls.json`, sem chamar o validador aposentado de Fly.io ou executar Docker. Os workflows report-only verificam documentação, contratos, regressões e estado declarado da infraestrutura; **não** acessam PC24x7, não verificam assinatura viva nem certificam saúde, disponibilidade ou E2E físico. `passed_with_warnings` significa somente configuração válida com evidência operacional pendente; `failed` permanece bloqueante.

Próxima evolução por prioridade: 1) PR report-only desta issue #3145; 2) prova externa autenticada do PC24x7/locator/health; 3) integração governada do reparo Windows da PR #3143 e teste Noteri; 4) recibos e failover físico da PR #3141. Responsáveis Engineering Control Plane, Runtime Platform e E2E Platform respectivamente. Toda passagem exige SHA, fonte e evidência de ação efetiva, não só registro ou monitor.
