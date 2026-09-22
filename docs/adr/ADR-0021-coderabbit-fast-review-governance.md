# ADR-0021 — Governança de revisão IA/CodeRabbit com fast path

## Status

Aceito.

## Data

2026-06-22

## Contexto

O ReqSys passou a utilizar revisão assistida por IA, incluindo CodeRabbit, como camada complementar de qualidade, rastreabilidade e revisão técnica. Em PRs grandes, agregadores ou com muitos artefatos documentais, o tempo de análise aumenta e passa a impactar o ciclo principal de entrega.

O objetivo é manter qualidade enterprise sem transformar revisão IA em gargalo operacional para PRs pequenos e objetivos.

## Problema

Quando CodeRabbit/revisões IA analisam todo o escopo indiscriminadamente, ocorrem riscos de:

- tempo alto de espera em PRs pequenos;
- maior consumo de contexto/tokens;
- comentários de baixo valor em arquivos documentais, gerados ou artefatos autocontidos;
- atraso na validação de correções simples;
- incentivo a PRs grandes, porque o custo de espera passa a ser percebido como inevitável.

## Decisão

Adotar política de **Fast Review Governance** para revisões IA/CodeRabbit:

1. PR pequeno e focado deve passar primeiro pelo **CI Fast**.
2. CodeRabbit deve ser usado como revisão complementar e preferencialmente assíncrona, sem substituir gates determinísticos.
3. Revisões profundas devem ser condicionais por label, escopo, criticidade ou execução pós-merge/nightly.
4. PRs devem ser pequenos, rastreáveis e especializados por domínio.
5. Arquivos gerados, artefatos, HTML autocontido, coverage, lockfiles e documentação massiva não devem inflar análise IA quando não forem o alvo da mudança.

## Guardrails obrigatórios

### Tamanho e escopo do PR

- Preferir PRs com até 10 arquivos alterados.
- Preferir PRs com até 400 linhas alteradas.
- Separar mudanças por domínio:
  - `fix(actions)` para workflows;
  - `docs(governance)` para documentação;
  - `feat(runtime)` para runtime;
  - `fix(security)` para segurança;
  - `feat(frontend)` para UI.
- Evitar PRs agregadores para correções operacionais urgentes.

### CI Fast antes de deep review

O fast path deve validar rapidamente:

- YAML/workflows quando `.github/workflows/**` mudar;
- lint/testes mínimos afetados;
- guardrails de governança;
- segurança básica;
- ausência de mudanças incompatíveis com produção.

### Deep review condicional

Deep review deve ser acionado por pelo menos uma condição:

- label `deep-review`;
- label `full-ci`;
- alteração em autenticação, autorização, segurança ou produção;
- alteração ampla de arquitetura;
- execução em `main` após merge;
- execução agendada/nightly.

### Arquivos que não devem inflar revisão IA

Quando tecnicamente possível, excluir ou reduzir peso de:

- `docs/**/*.html` autocontidos;
- `coverage/**`;
- `dist/**`;
- `artifacts/**`;
- arquivos `.lock` quando não forem o objetivo do PR;
- imagens, snapshots e outputs gerados;
- documentação massiva sem alteração de decisão arquitetural.

## Consequências positivas

- Menor tempo de espera no ciclo principal de PR.
- Maior previsibilidade para correções pequenas.
- Redução de ruído em comentários automatizados.
- Melhor alinhamento com trunk-based development e micro PRs.
- Preservação de revisão profunda para mudanças realmente críticas.

## Trade-offs

- Algumas análises profundas podem ocorrer após o fast path ou pós-merge.
- Exige disciplina de labels e escopo de PR.
- Exige manter gates determinísticos para que revisão IA não seja tratada como único controle de qualidade.

## Critérios de aceite

Uma entrega segue esta ADR quando:

- o PR é pequeno ou justifica explicitamente seu tamanho;
- CI Fast é executável antes das validações profundas;
- labels controlam validações pesadas quando aplicável;
- revisões IA não analisam artefatos irrelevantes de forma indiscriminada;
- documentação e changelog registram decisões operacionais relevantes.

## Relação com decisões existentes

- Complementa `docs/adr/ADR-0004-ci-cd-qualidade.md`.
- Complementa `docs/ci/CI_ACCELERATION_STRATEGY.md`.
- Complementa a governança da Operational Runtime Governance Platform.
