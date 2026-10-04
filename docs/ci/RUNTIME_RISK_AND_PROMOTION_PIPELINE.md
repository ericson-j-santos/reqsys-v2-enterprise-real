# Runtime Risk Scoring + Governed Promotion Pipeline

## Objetivo

Adicionar duas capacidades operacionais ao ReqSys:

1. **Runtime Risk Scoring por PR**: classifica risco de alterações com base em diff, escopo, área sensível, tamanho e estado do PR.
2. **Governed Promotion Pipeline**: simula e governa promoção entre ambientes, começando por `dev → homolog`, mantendo produção bloqueada para aprovação explícita.

## Workflows

| Workflow | Arquivo | Uso |
|---|---|---|
| Runtime Risk Scoring | `.github/workflows/runtime-risk-scoring.yml` | Executa em PR e manualmente |
| Governed Promotion Pipeline | `.github/workflows/governed-promotion-pipeline.yml` | Executa manualmente via `workflow_dispatch` |

## Runtime Risk Scoring

O score varia de `0` a `100`.

| Faixa | Classificação |
|---:|---|
| 0–24 | low |
| 25–49 | medium |
| 50–74 | high |
| 75–100 | critical |

### Fatores considerados

- quantidade de arquivos alterados;
- linhas adicionadas/removidas;
- PR em draft;
- mergeabilidade;
- review com mudanças solicitadas;
- base do PR;
- alterações em autenticação/autorização;
- alterações em segurança/segredos/cofre/PII;
- alterações em infraestrutura/deploy/ambiente;
- alterações em banco/schema/migration;
- alterações em workflows;
- alteração full-stack;
- redução de risco para PR somente documental.

### Artifact

O workflow publica:

```text
runtime-risk-scoring-evidence
```

Conteúdo principal:

```text
risk-score.json
pr.json
changed-files.txt
reasons.txt
blockers.txt
```

## Governed Promotion Pipeline

### Ambientes suportados

| Ambiente alvo | Estratégia |
|---|---|
| homolog | Simulação ou criação de PR draft de promoção |
| prod | Somente simulação neste incremento inicial |

### Inputs

| Input | Descrição |
|---|---|
| `source_ref` | Branch/tag/SHA origem da promoção |
| `target_environment` | `homolog` ou `prod` |
| `dry_run` | `true` por padrão; não altera estado |
| `change_ticket` | Obrigatório para produção |
| `approve_prod_promotion` | Deve ser `APROVO-PROD` para simulação de produção |

## Regras de produção

Produção permanece bloqueada para promoção real neste incremento. Mesmo com confirmação textual, o workflow inicial não executa mudança real em produção.

### Pré-condição Release Validation Layer

Antes de aprovar promoção, o pipeline:

1. Baixa `release-validation-layer-evidence` (ou regenera via script quando ausente).
2. Executa `scripts/evaluate_promotion_release_gate.py`.
3. Incorpora o resultado em `promotion-policy.json` (`release_validation_gate`, `release_readiness_score`).

| Ambiente | Score mínimo | Readiness |
|---|---:|---|
| homolog | 70% | ready, ready_with_observation, needs_review |
| prod | 85% | ready, ready_with_observation |

Promoção real (`dry_run=false`) é bloqueada quando o artifact está ausente ou a release validation reprova.

## Evidência

O promotion pipeline publica:

```text
governed-promotion-evidence
```

Conteúdo principal:

```text
promotion-policy.json
release-validation-gate.json
changed-files.txt
```

## Decisão operacional

- Auto-merge governado fica restrito ao ambiente `dev`.
- Promoção para homologação ocorre via PR draft criado por workflow, quando aprovado pela política.
- Promoção para produção exige aprovação humana e segue bloqueada para execução real neste incremento.
- Todo fluxo deve produzir artifact de evidência.

## Próximos incrementos

1. Expor score de risco no Runtime/Actions Center.
2. Integrar DORA metrics e Change Failure Rate.
3. Criar rollback metadata por promoção.
4. Adicionar aprovação por environment para homolog/prod.
5. Implementar release notes automáticas por promoção.
