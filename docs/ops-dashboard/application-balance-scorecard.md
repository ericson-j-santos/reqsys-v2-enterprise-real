# Application Balance Scorecard v0.1.0

> Atualização: 2026-06-30 13:00 BRT  
> Escopo: equilíbrio incremental da aplicação ReqSys  
> Tipo de incremento: `consolidate`  
> Produção: sem alteração direta

## Objetivo

Este scorecard orienta os próximos incrementos do ReqSys para reduzir desequilíbrios entre frontend, backend, runtime operacional, CI/CD, governança, segurança e documentação viva.

O objetivo não é abrir nova frente funcional. O objetivo é deixar a aplicação mais equilibrada, previsível, rastreável e fácil de validar antes de expandir novas capacidades.

## Artefato canônico

O artefato machine-readable está em:

```text
docs/ops-dashboard/data/application-balance-scorecard-v0.1.0.json
```

Ele define:

- domínios de equilíbrio;
- pesos relativos;
- estado atual por semáforo;
- próximo incremento recomendado por domínio;
- evidência esperada;
- guardrails de governança;
- índice executivo de equilíbrio.

## Leitura executiva atual

| Domínio | Peso | Estado | Interpretação |
| --- | ---: | --- | --- |
| Frontend, UX e responsividade | 20 | yellow | Boa base responsiva, mas ainda exige evidência por jornada crítica. |
| Runtime operacional e observabilidade | 20 | yellow | Malha avançada, porém ainda precisa de contrato único de score/readiness/risco. |
| Backend e contratos de API | 15 | yellow | FastAPI, OpenAPI e .NET evoluindo; falta matriz explícita de paridade. |
| CI/CD e quality gates | 15 | yellow | Gates existem; risco residual em PRs draft/advisory ou divergentes da main. |
| Governança e evidências | 15 | yellow | Governança forte, mas evidências ainda dispersas. |
| Documentação e rastreabilidade | 10 | green | Boa maturidade documental e rastreável. |
| Segurança, LGPD e operação assistida | 5 | yellow | Diretrizes existentes; reforçar validação automática de secrets/PII em artifacts. |

## Índice inicial de equilíbrio

| Métrica | Valor |
| --- | ---: |
| Verde ponderado | 10% |
| Amarelo ponderado | 90% |
| Vermelho ponderado | 0% |
| Balance index inicial | 64% |
| Confiança | Média |

## Caminho Pareto recomendado

1. Normalizar contrato único para `runtime_score`, `maturity_percent`, `operational_risk` e `readiness_status`.
2. Criar matriz de paridade API entre FastAPI e .NET para módulos críticos.
3. Vincular jornadas críticas do frontend a evidências E2E ou testes unitários.
4. Reduzir PRs draft/advisory divergentes da `main`, com incremento menor e tipo permitido.

## Critérios para considerar um domínio equilibrado

Um domínio só deve ser promovido para `green` quando possuir:

- contrato ou documentação objetiva;
- evidência executável ou artifact versionado;
- rollback conhecido;
- impacto em segurança avaliado;
- impacto em analytics/observabilidade avaliado;
- próxima ação documentada ou explicitamente encerrada.

## Guardrails

- Não abrir nova superfície funcional sem contrato, teste ou evidência mínima.
- Não misturar frontend, backend, workflow e documentação ampla no mesmo PR sem necessidade arquitetural.
- Não publicar link como estável antes de CI verde ou bloqueio documentado.
- Não registrar PII bruta, secrets ou tokens em artifacts de dashboard.

## Próximo incremento objetivo

O próximo incremento recomendado é **normalizar o contrato operacional único de score/readiness/risco** para reduzir ambiguidade entre dashboard, runtime health, evidence gate e documentação viva.

Saída esperada:

- artifact JSON de contrato operacional;
- runbook curto de interpretação;
- validação estática simples;
- referência no changelog.
