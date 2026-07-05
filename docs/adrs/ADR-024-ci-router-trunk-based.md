---
status: ReqSys / Plataforma Corporativa
date: 2026-06-22
deciders: Arquitetura / Engenharia
context: ReqSys / Plataforma Corporativa
version: 1.0.0
---

# ADR-024 — CI Router e Trunk-Based Development


## Status

Aprovado.

## Contexto

O repositório ReqSys vinha executando esteiras completas para mudanças pequenas, aumentando tempo de espera, custo de execução, retrabalho e risco de branches longas ficarem defasadas.

## Decisão

Adotar uma estratégia operacional baseada em:

- Trunk-Based Development;
- PRs pequenos e verticais;
- feature flags para funcionalidades ainda não liberadas;
- CI Router por paths;
- jobs condicionais por área alterada;
- gate consolidado final para manter sinal único de qualidade.

## Modelo de branch

| Tipo | Padrão | Objetivo |
|---|---|---|
| Produção | `main` | fonte da verdade sempre estável |
| Incremento | `feat/<area>-<objetivo>-p0` | PR pequeno e rápido |
| Correção | `fix/<area>-<falha>` | correção objetiva |
| Experimento | `exp/<tema>` | validação descartável |
| Release | `release/YYYY.MM.N` | congelamento excepcional |

## Regras operacionais

1. PR deve ter menor mudança útil possível.
2. Alterações de documentação não devem acionar backend/frontend completos.
3. Alterações de backend acionam lint, segurança e testes backend.
4. Alterações de frontend acionam build, audit e E2E responsivo.
5. Alterações em workflows acionam CI completo.
6. Funcionalidades de maior risco devem entrar desligadas por feature flag.
7. O resultado consolidado deve indicar claramente o que rodou e o que foi ignorado.

## Consequências positivas

- Menor tempo médio de PR.
- Menor fila de CI.
- Menos conflitos por branches longas.
- Feedback mais rápido por área alterada.
- Redução de retrabalho operacional.

## Riscos

| Risco | Mitigação |
|---|---|
| Mudança cruzada não detectada | `full_ci=true` para arquivos fora dos padrões conhecidos |
| Workflow alterado sem validação ampla | mudanças em `.github/workflows/**` acionam CI completo |
| PR pequeno mascarar impacto indireto | exigir revisão arquitetural em mudanças transversais |
| Jobs ignorados confundirem status | job `CI Router Result` publica resumo consolidado |

## Decisão final

A partir desta ADR, a estratégia canônica para evolução contínua do ReqSys passa a ser:

```text
main estável + PR pequeno + CI por paths + feature flag + deploy contínuo
```
