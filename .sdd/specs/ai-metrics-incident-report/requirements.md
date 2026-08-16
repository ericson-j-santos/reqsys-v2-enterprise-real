# Requirements — ai-metrics-incident-report

> **STATUS: RASCUNHO / EM REVISAO** — nao aprovado. Fase atual real do spec (bate com o card
> do dashboard: `spec.json` feito, `requirements.md` em elaboracao). Escrito em 2026-08-16.

## Contexto (por que este spec existe)

O ReqSys ja tem 4 pedacos de "AI metrics/incidentes" espalhados, sem chave comum entre eles:

| Fonte | Onde | O que tem |
|---|---|---|
| Qualidade IA | `models/ai_quality.py`, `services/ai_quality.py` | snapshots de score/acuracia/relevancia/consistencia/seguranca, `incidentes_criticos` (so contador, sem detalhe) |
| Incidentes IA | `api/incidentes.py` → `services/recomendacoes_ia.py` | lista/detalhe de incidentes vinculados a requisitos |
| Telemetria LLM | `services/llm_telemetry.py` | eventos por provider (status, tipo_erro, timestamp), retencao configuravel |
| Correlacao de runtime | `core/runtime_analytics.py` | `build_incident_event`, MTTR, lead time, correlacao deploy↔incidente — generico, nao especifico de IA |

Hoje nenhum endpoint consolida essas 4 fontes em um relatorio unico de "incidente de IA". Esse
e o problema concreto que motiva o feature.

## Requirement 1 (rascunho) — Relatorio consolidado de incidentes de IA

**User story:** Como responsavel por governanca de IA, quero um relatorio unico que junte
qualidade, incidentes, telemetria de provider e correlacao de runtime, para nao precisar
consultar 4 telas/endpoints separados para entender um incidente de IA.

**Acceptance criteria (draft, sujeito a revisao):**
1. QUANDO consultado por periodo ENTAO o relatorio DEVE combinar `QualidadeIASnapshot`,
   incidentes de `recomendacoes_ia`, eventos de `llm_telemetry` e eventos de
   `runtime_analytics` correlatos.
2. **[EM ABERTO]** Qual e a chave de correlacao entre essas 4 fontes? Nenhuma delas tem hoje
   um `incident_id` compartilhado — precisa ser definido (candidatos: janela de tempo +
   provider, ou um novo campo de correlacao a ser adicionado).

## Requirement 2 (rascunho) — Contrato desacoplado (estrategia hibrida)

**User story:** Como arquiteto, quero que o formato de saida do relatorio seja um contrato
estavel e independente da implementacao interna do ReqSys, para que este subsistema possa ser
extraido depois para um servico `AI Metrics Backend` separado sem quebrar consumidores.

**Acceptance criteria (draft):**
1. O relatorio DEVE ser exposto como schema/DTO versionado (ex.: Pydantic model dedicado),
   nao como serializacao direta dos models internos (`QualidadeIASnapshot` etc.).
2. **[EM ABERTO]** Definir se a extracao futura sera um novo processo Python separado
   consumindo o mesmo Postgres, ou um servico com storage proprio replicado via evento/ETL —
   decisao de arquitetura que precisa do usuario antes da fase de design.

## Requirement 3 (rascunho) — Mascaramento LGPD nos dados agregados

**User story:** Como responsavel por compliance, quero que o relatorio consolidado nunca
exponha PII nos campos de detalhe de erro/incidente, para cumprir ADR-002.

**Acceptance criteria (draft):**
1. Campos de texto livre agregados de multiplas fontes (`tipo_erro`, detalhes de incidente)
   DEVEM passar pelo mesmo mascaramento ja usado no resto do sistema antes de aparecer no
   relatorio.

## Perguntas em aberto (bloqueiam aprovacao deste requirements.md)

1. Chave de correlacao entre as 4 fontes (Requirement 1.2).
2. Modelo de extracao futura: mesmo banco vs. servico com storage proprio (Requirement 2.2).
3. Quem consome esse relatorio primeiro — dashboard interno do ReqSys, ou ja nasce pensado
   para um cliente externo (o futuro `AI Metrics Backend`)? Afeta prioridade de design.

## Explicitamente fora de escopo desta fase

- Nao ha ainda nenhum codigo do lado "AI Metrics Backend" separado — repositorio nao existe.
  Este requirements.md so cobre a consolidacao dentro do ReqSys; a extracao e Requirement 2,
  nao uma entrega desta fase.
