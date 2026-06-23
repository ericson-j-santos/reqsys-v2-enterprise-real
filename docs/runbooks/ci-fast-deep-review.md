# Runbook — CI Fast + Deep Review + CodeRabbit Otimizado

## Objetivo

Reduzir o tempo de espera em PRs do ReqSys sem reduzir governança, segurança ou rastreabilidade.

## Decisão operacional

O fluxo padrão passa a ser:

```text
Micro PR → PR Fast Classifier → CI rápido → CodeRabbit com escopo reduzido → merge seguro
                                      ↓
                         Deep Governance Review sob demanda/nightly
```

## Estratégia

### 1. Micro PR como padrão

Usar PRs pequenos, focados e rastreáveis.

Faixa recomendada:

| Critério | Alvo |
|---|---:|
| Arquivos alterados | até 12 |
| Linhas adicionadas | até 400 |
| Escopo | uma decisão técnica por PR |
| Documentação | proporcional ao risco |

### 2. PR Fast Classifier

Workflow: `.github/workflows/pr-fast-classifier.yml`.

Responsabilidades:

- contar arquivos alterados;
- estimar linhas adicionadas;
- classificar risco inicial;
- recomendar modo `fast` ou `deep`;
- publicar artifact de evidência.

Sinais que elevam para revisão profunda:

- alteração em `.github/workflows/**`;
- auth/security/secrets/JWT/CORS/deploy/Fly/Docker;
- PR com mais de 12 arquivos alterados.

### 3. CodeRabbit otimizado

Arquivo: `.coderabbit.yaml`.

Decisão:

- revisar primeiro código, scripts, workflows e testes;
- ignorar por padrão artefatos pesados de baixa utilidade para revisão rápida;
- reduzir diagramas automáticos e walkthrough expandido;
- manter regras de segurança como alerta/erro.

### 4. Deep Governance Review

Workflow: `.github/workflows/deep-governance-review.yml`.

Dispara em:

- execução manual;
- agenda nightly em dias úteis;
- label `deep-review`;
- label `security`;
- label `architecture`.

Responsabilidades:

- gerar `review_id`;
- mapear workflows, docs e scripts;
- procurar sinais simples de risco;
- publicar artifact de evidência.

## Labels operacionais recomendadas

| Label | Uso |
|---|---|
| `deep-review` | Forçar revisão profunda |
| `security` | Alterações com impacto de segurança |
| `architecture` | Decisão arquitetural ou ADR |
| `fast-path` | PR pequeno de baixo risco |
| `docs-only` | Documentação sem impacto de runtime |

## Política de merge recomendada

| Tipo de PR | Gate mínimo | Gate profundo |
|---|---|---|
| Docs-only | CI fast | opcional |
| Workflow | CI fast + revisão humana | recomendado |
| Segurança/Auth | CI fast + Deep Review | obrigatório |
| Runtime/API | CI fast + testes | recomendado |
| Produção/Deploy | CI fast + Deep Review | obrigatório |

## Critério de aceite

Um PR pode seguir para merge quando:

- CI obrigatório estiver verde;
- não houver bloqueador de segurança;
- risco estiver classificado e entendido;
- artifacts de classificação forem gerados;
- revisão profunda tiver sido usada quando o risco exigir.

## Operação prática

### Para PR rápido

1. Abrir PR pequeno.
2. Aguardar `PR Fast Classifier`.
3. Corrigir riscos apontados.
4. Aguardar CI obrigatório.
5. Fazer merge.

### Para PR crítico

1. Adicionar label `deep-review` ou `security`.
2. Aguardar `Deep Governance Review`.
3. Revisar artifact.
4. Corrigir riscos reais.
5. Prosseguir apenas com evidência verde.

## Observação

Esta estratégia não substitui branch protection, rulesets ou revisão humana em áreas críticas. Ela reduz tempo no caminho comum e desloca análise profunda para os casos que realmente justificam custo operacional maior.
