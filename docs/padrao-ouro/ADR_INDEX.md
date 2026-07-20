# ADR Index — Decision Records

Data de referência: 2026-07-20

Catálogo de Architecture Decision Records (ADRs) do ReqSys. Cada ADR segue o formato: **problema → decisão → impacto → tradeoff → evidência**.

## Como usar

| Situação | Ação |
| --- | --- |
| Nova decisão transversal | Criar ADR em `docs/adr/ADR-NNN-titulo.md` |
| Entender decisão existente | Consultar tabela abaixo por domínio |
| Evitar refactor errado | Ler ADR do domínio antes de alterar |
| Onboarding agente/IA | Ler ADRs fundacionais (0001–0006) primeiro |
| Coordenar geração ou revisão de código | Consultar ADRs e o catálogo em `docs/prompts/` |

## Formato padrão

```markdown
# ADR-NNN — Título
Status: aceito | proposto | substituído
Data: YYYY-MM-DD
## Contexto (problema)
## Decisão
## Consequências (impacto)
## Critérios de aceite
```

---

## Fundacionais (obrigatórios)

| ADR | Título | Status | Impacto |
| --- | --- | --- | --- |
| [ADR-0001](../adr/ADR-0001-arquitetura-padrao-ouro.md) | Arquitetura Padrão Ouro | aceito | Modular, hexagonal quando necessário; ADR obrigatório para decisões transversais |
| [ADR-0002](../adr/ADR-0002-seguranca-gates-producao.md) | Segurança e Gates de Produção | aceito | Bloqueio produtivo: JWT, CORS, PII, correlation_id |
| [ADR-0003](../adr/ADR-0003-ambientes-dev-hml-prod.md) | Ambientes dev/hml/prod | aceito | Separação explícita de ambientes |
| [ADR-0004](../adr/ADR-0004-ci-cd-qualidade.md) | CI/CD e Qualidade | aceito | CI verde obrigatório; quality gates |
| [ADR-0005](../adr/ADR-0005-observabilidade-auditoria.md) | Observabilidade e Auditoria | aceito | correlation_id, logs sem PII |
| [ADR-0006](../adr/ADR-0006-analytics-drilldown-schema-driven-ui.md) | Analytics Drill-down Schema-driven | aceito | Indicador → gráfico → analítico → ação |

---

## Governança, Prompts e CI

| ADR | Título | Status | Impacto |
| --- | --- | --- | --- |
| [ADR-0021](../adr/ADR-0021-coderabbit-fast-review-governance.md) | CodeRabbit Fast Review Governance | aceito | Fast path + deep review condicional |
| [ADR-0024](../adr/ADR-0024-substituicao-coderabbit-pr-quality-review.md) | Substituição CodeRabbit → PR Quality Review | aceito | Migração de revisão IA |
| [ADR-030](../adr/ADR-030-governed-dev-automerge.md) | Governed Dev Automerge | aceito | Merge controlado em dev |
| [ADR-031](../adr/ADR-031-runtime-risk-and-promotion-pipeline.md) | Runtime Risk and Promotion Pipeline | aceito | Risco runtime + promoção |
| [ADR-045](../adr/ADR-045-governanca-coordenacao-prompts-desenvolvimento.md) | Governança e Coordenação de Prompts de Desenvolvimento | proposto | Separa ADR de PDR e coordena geração, revisão, testes e evidências de código |
| [ADR-PR-AUTO-RECOVERY-V2](../adr/ADR-PR-AUTO-RECOVERY-V2.md) | PR Auto Recovery V2 | aceito | Recuperação automática de PR |
| [ADR-PR-AUTO-RECOVERY-V3](../adr/ADR-PR-AUTO-RECOVERY-V3.md) | PR Auto Recovery V3 | aceito | Recuperação controlada V3 |
| [ADR-044](../adr/ADR-044-gitlab-edition-pipeline-paralela.md) | GitLab Edition: Pipeline Paralela Fortalecida, Não-Ativa | aceito | CI ativa continua sendo só GitHub Actions; GitLab Edition é scaffolding local com jobs reais, sem projeto GitLab provisionado |

Catálogo operacional relacionado: [`docs/prompts/README.md`](../prompts/README.md).

---

## Operações e Runtime

| ADR | Título | Status | Impacto |
| --- | --- | --- | --- |
| [ADR-022](../adr/ADR-022-autonomous-operations-platform-p0-1.md) | Autonomous Operations Platform P0.1 | aceito | Operação autônoma |
| [ADR-023](../adr/ADR-023-aop-runtime-health-validator-remediation-executor.md) | Runtime Health Validator + Remediation | aceito | Validação e remediação runtime |
| [ADR-032](../adr/ADR-032-operational-health-dashboard-governance.md) | Operational Health Dashboard Governance | aceito | Dashboard de saúde operacional |
| [ADR-034](../adr/ADR-034-autonomous-operational-runtime-consolidation.md) | Autonomous Operational Runtime Consolidation | aceito | Consolidação runtime autônomo |
| [ADR-REQSYS-OPER-005](../adr/ADR-REQSYS-OPER-005-monitoramento-operacional.md) | Monitoramento Operacional | aceito | Monitoramento REQSYS#002 |

---

## Integrações e Produto

| ADR | Título | Status | Impacto |
| --- | --- | --- | --- |
| [ADR-020](../adr/ADR-020-connection-broker-permission-on-demand.md) | Connection Broker Permission on Demand | aceito | Permissões de conector sob demanda |
| [ADR-021](../adr/ADR-021-figma-github-retorno-em-tela.md) | Figma-GitHub Retorno em Tela | aceito | Integração visual Figma |
| [ADR-041](../adr/ADR-041-cofre-segredos-locais.md) | Cofre de Segredos Locais | aceito | AES-GCM + keyring, API REST, diagnóstico |
| [ADR-042](../adr/ADR-042-postgres-local-dev-alembic.md) | Postgres Local para Dev + Migrations Alembic | parcialmente superado | Schema versionado com Alembic; opção de Compose superada pelo ADR-043 |
| [ADR-043](../adr/ADR-043-backup-rotacao-retencao.md) | Backup, Rotação de Logs, Retenção de Auditoria e Centralização de Banco | aceito | Postgres padrão em dev/test/prod-local/CI; backup + purge + log rotation |
| [ADR-033](../adr/ADR-033-product-intelligence-final-evidence-index.md) | Product Intelligence Final Evidence Index | aceito | Índice final de evidências PI |
| [ADR-ESTATISTICAS](../adr/ADR-ESTATISTICAS-INTERNAS-EXTERNAS.md) | Estatísticas Internas/Externas | aceito | Abas de estatísticas |
| [ADR-USER-FINAL-SHELL](../adr/ADR-USER-FINAL-SHELL-001.md) | User Final Shell | aceito | Shell visual final do usuário |

---

## Trilhas Padrão Ouro (Arquitetura Viva)

| ADR | Trilha | Status | Impacto |
| --- | --- | --- | --- |
| [ADR-035](../adr/ADR-035-trilha-e-arquitetura-viva.md) | E — Arquitetura Viva | aceito | Diagramas vivos, navegáveis, versionados |
| [ADR-036](../adr/ADR-036-trilha-a-runtime-publico.md) | A — Runtime Público | aceito | Boot resiliente, healthcheck Fly.io |
| [ADR-037](../adr/ADR-037-trilha-b-observabilidade-enterprise.md) | B — Observabilidade Enterprise | aceito | correlation_id, métricas, telemetria |
| [ADR-038](../adr/ADR-038-trilha-c-ux-operacional.md) | C — UX Operacional | aceito | Semáforo, drill-down, UX operacional |
| [ADR-039](../adr/ADR-039-trilha-d-qualidade-governanca.md) | D — Qualidade e Governança | aceito | Matrix paralelizável de qualidade |
| [ADR-040](../adr/ADR-040-trilhas-padrao-ouro.md) | Trilhas Consolidadas | aceito | Consolidação maturidade A–E |

---

## Mapa de dependência entre ADRs

```text
ADR-0001 (arquitetura)
  ├── ADR-0002 (segurança)
  ├── ADR-0003 (ambientes)
  │     ├── ADR-042 (postgres local dev + alembic)
  │     └── ADR-043 (backup/rotacao/retencao + centralizacao de banco)
  ├── ADR-0004 (CI/CD)
  │     ├── ADR-0021/0024 (revisão IA)
  │     ├── ADR-030 (automerge)
  │     ├── ADR-045 (coordenação de prompts de desenvolvimento)
  │     └── ADR-PR-AUTO-RECOVERY-V2/V3
  ├── ADR-0005 (observabilidade)
  │     ├── ADR-037 (trilha B)
  │     └── ADR-032 (health dashboard)
  ├── ADR-0006 (analytics)
  │     └── ADR-038 (trilha C)
  └── ADR-035 (arquitetura viva)
        ├── ADR-036 (trilha A)
        ├── ADR-039 (trilha D)
        └── ADR-040 (consolidação)
```

---

## Política de criação

1. Decisões transversais (afetam >1 módulo ou ambiente) **exigem** ADR.
2. Numeração sequencial: `ADR-NNN-titulo-kebab-case.md` em `docs/adr/`.
3. Status: `proposto` → `aceito` → `substituído` (com link para sucessor).
4. Atualizar este índice ao criar ou substituir ADR.
5. Referenciar ADR no PR quando a decisão for implementada.
6. Instruções operacionais reutilizáveis para geração, revisão ou correção de código devem ser registradas como PDR em `docs/prompts/`, sem duplicar decisões arquiteturais.

## Referências

- Hub Tier 1: [`docs/padrao-ouro/README.md`](README.md)
- Governança de prompts: [`docs/prompts/README.md`](../prompts/README.md)
- Trilhas hub: [`docs/architecture/trilhas/`](../architecture/trilhas/)
- Runbook trilhas: [`docs/runbooks/trilhas-padrao-ouro.md`](../runbooks/trilhas-padrao-ouro.md)
