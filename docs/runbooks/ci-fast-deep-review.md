# Runbook — CI Fast + Deep Review + CodeRabbit Otimizado

## Objetivo

Reduzir o tempo de espera em PRs do ReqSys sem reduzir governança, segurança ou rastreabilidade.

## Decisão operacional

O fluxo padrão passa a ser:

```text
Micro PR → PR Fast Classifier → CI rápido → revisão sob demanda → merge seguro
                                      ↓
                         Deep Governance Review sob demanda/nightly
                                      ↓
                         Codex gratuito governado como apoio opcional
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

- `auto_review.enabled=false` para evitar consumo automático de quota;
- CodeRabbit não é gate obrigatório de merge;
- revisão CodeRabbit deve ser acionada manualmente apenas quando houver real valor de revisão;
- revisar primeiro código, scripts, workflows e testes;
- ignorar por padrão artefatos pesados de baixa utilidade para revisão rápida;
- reduzir diagramas automáticos e walkthrough expandido;
- manter regras de segurança como alerta/erro.

#### Quando o CodeRabbit atingir limite

Se o CodeRabbit retornar `Review limit reached`, a decisão operacional é:

1. não bloquear o PR apenas por limite de quota;
2. validar CI obrigatório;
3. validar `PR Fast Classifier`;
4. acionar `Deep Governance Review` quando o PR alterar workflow, segurança, arquitetura, deploy ou runtime crítico;
5. aplicar revisão humana focada nos arquivos alterados;
6. acionar `@coderabbitai review` apenas após recarga de quota e somente se ainda houver necessidade.

### 4. Codex gratuito governado

O Codex gratuito do ecossistema ReqSys pode ser usado como **revisor complementar**, mas não deve ser tratado como gate de produção enquanto não publicar evidência versionada.

Uso recomendado:

- revisão local ou assistida do diff;
- checklist de riscos por arquivo alterado;
- análise de workflow GitHub Actions;
- sugestão de correções pequenas;
- geração de comentário de revisão para anexar ao PR.

Condições mínimas para virar gate futuro:

- execução via workflow governado ou comando manual auditável;
- allowlist de comandos;
- sem acesso irrestrito a secrets;
- artifact obrigatório com relatório;
- `correlation_id` ou `review_id`;
- falha determinística apenas para violações objetivas;
- runbook versionado.

Até essa integração existir, a ordem de confiança é:

```text
CI obrigatório + checks determinísticos > Deep Governance Review > revisão humana > Codex gratuito > CodeRabbit sob demanda
```

### 5. Deep Governance Review

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
| `codex-review` | Solicitar revisão complementar pelo Codex gratuito |

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
- revisão profunda tiver sido usada quando o risco exigir;
- ausência de review CodeRabbit por limite de quota estiver registrada como risco operacional não bloqueante.

## Operação prática

### Para PR rápido

1. Abrir PR pequeno.
2. Aguardar `PR Fast Classifier`.
3. Corrigir riscos apontados.
4. Aguardar CI obrigatório.
5. Se CodeRabbit estiver limitado, registrar como não bloqueante.
6. Fazer merge.

### Para PR crítico

1. Adicionar label `deep-review` ou `security`.
2. Aguardar `Deep Governance Review`.
3. Revisar artifact.
4. Corrigir riscos reais.
5. Usar Codex gratuito como apoio complementar quando houver diff relevante.
6. Prosseguir apenas com evidência verde.

### Para reativar CodeRabbit manualmente

Após recarga de quota, comentar no PR:

```text
@coderabbitai review
```

Usar esse comando apenas quando:

- o PR estiver pronto para revisão;
- houver mudança em workflow, segurança, runtime ou arquitetura;
- a revisão humana/CI ainda não tiver coberto o risco principal.

## Observação

Esta estratégia não substitui branch protection, rulesets ou revisão humana em áreas críticas. Ela reduz tempo no caminho comum, evita dependência de quota do CodeRabbit e desloca análise profunda para os casos que realmente justificam custo operacional maior.
