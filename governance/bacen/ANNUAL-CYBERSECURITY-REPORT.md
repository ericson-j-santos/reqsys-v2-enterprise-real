# Relatório Anual de Segurança Cibernética — ReqSys

> **Status: RASCUNHO TÉCNICO — pendente de emissão formal.**
> Este documento é um esqueleto preparado para revisão humana e assinatura do
> responsável executivo designado (ver `governance/bacen/EXECUTIVE-DESIGNATION.yaml`).
> Ele **não** constitui o relatório anual formalmente emitido exigido pelo controle
> BACEN-08 até que: (1) um responsável executivo seja formalmente designado; (2) as
> seções narrativas abaixo sejam revisadas e completadas por humanos; (3) o
> documento seja aprovado e assinado pelo responsável executivo.

## Ciclo de referência

- Período coberto: *(preencher — ex.: 2026)*
- Data de emissão formal: *(preencher quando aprovado)*

## Baseline normativa utilizada

- `as_of`: `2026-09-02T22:01:00Z`
- Estado da baseline: `transitional_pending_normative_axis`
- Norma-base: Resolução CMN nº 4.893/2021 — texto consolidado.
- Alteração material incorporada ao contrato: Resolução CMN nº 5.274/2025, publicada em 18/12/2025.
- Família Resolução BCB nº 85/2021 + Resolução BCB nº 538/2025: `applicability_pending`.
- Documentos vivos SFN referenciados pela norma: `nao_avaliado` até a implantação do eixo normativo versionado do ADR-015.

> Este bloco registra a baseline usada para estruturar o relatório. Não constitui
> decisão institucional de aplicabilidade nem declaração de conformidade. A
> reconciliação com documentos vivos, seus hashes de texto normalizado e a
> aplicabilidade por entidade permanece pendente do eixo normativo.

## Responsável executivo

<!-- BACEN-08:EXECUTIVE:START -->
- Status da designação: `pending_formal_designation`
- Nome: *(pendente de designação formal)*
- Cargo: *(pendente de designação formal)*
<!-- BACEN-08:EXECUTIVE:END -->

## Resumo executivo

*(seção narrativa — preencher: principais riscos do período, decisões relevantes,
investimentos em segurança, mudanças regulatórias observadas)*

## Panorama dos controles mínimos BACEN

Gerado automaticamente a partir de `governance/bacen/BACEN-CONTROL-MATRIX.yaml` por
`scripts/generate_bacen_annual_report.py`. Não editar manualmente entre os
marcadores abaixo — a próxima execução do gerador sobrescreve este bloco.

> **Escopo deste quadro:** os itens abaixo são macrocontroles internos do ReqSys
> relacionados ao BACEN; eles não constituem, isoladamente, o universo normativo
> vigente. Enquanto o eixo normativo não estiver integralmente modelado e avaliado,
> este relatório não publica percentual agregado de cobertura regulatória.

<!-- BACEN-08:CONTROLS-SUMMARY:START -->

| Controle interno | Domínio | Criticidade | Status |
|---|---|---|---|
| BACEN-01 | governance | critical | partial |
| BACEN-02 | identity | critical | partial |
| BACEN-03 | incidents | critical | implemented |
| BACEN-04 | continuity | critical | implemented |
| BACEN-05 | third_party | high | partial |
| BACEN-06 | secure_development | high | implemented |
| BACEN-07 | audit | high | implemented |
| BACEN-08 | executive_governance | critical | partial |

> **Nota:** estes são macrocontroles internos do ReqSys. Nenhum percentual agregado de cobertura regulatória é publicado enquanto o eixo normativo vigente não estiver integralmente modelado e avaliado.
<!-- BACEN-08:CONTROLS-SUMMARY:END -->

## Incidentes de segurança do período

- Estado do bloco normativo: `nao_avaliado`.
- Evidência técnica disponível: `artifacts/bacen/bacen-03-incident-exercise-evidence.json`.
- Política/plano técnico relacionado: `governance/bacen/INCIDENT-RESPONSE-PLAN.md`.
- Cenário de exercício relacionado: `governance/bacen/INCIDENT-EXERCISE-SCENARIO.json`.
- Lacuna: métricas e registros de incidentes cibernéticos reais do período ainda não estão integrados ao gerador anual.

*(seção narrativa — revisar os incidentes cibernéticos relevantes efetivamente
ocorridos no período. Exercício de resposta não deve ser promovido automaticamente
a incidente real.)*

## Resultados dos testes de continuidade de negócios

- Estado do bloco normativo: `nao_avaliado`.
- Insumo técnico existente: evidências BACEN-04 de backup/restauração.
- Lacuna: o ReqSys ainda não reconcilia automaticamente essas evidências com o contrato normativo de resultados dos testes de continuidade de negócios do período.

> Até essa reconciliação, backup/restauração técnico não é declarado como resultado
> completo de teste de continuidade de negócios para fins regulatórios.

## Resultados dos testes de intrusão

- Estado do bloco normativo: `nao_avaliado`.
- Evidência de pentest independente vigente: `nao_evidenciada_no_repositorio`.
- Plano corretivo associado: `nao_avaliado`.

> A ausência de evidência no repositório não afirma que o teste não exista na
> instituição; afirma somente que o ReqSys não possui evidência governada suficiente
> para preencher este bloco como `evidenciado`.

## Varreduras e análises de vulnerabilidades

- Estado do bloco normativo: `nao_avaliado`.
- Existem scanners e gates técnicos de segurança no ReqSys, porém ainda não há mapeamento normativo que permita promovê-los automaticamente a evidência deste bloco.
- Resultado agregado do período: `pendente_de_reconciliacao`.

## Avaliação de terceiros e nuvem

*(seção narrativa — usar `governance/bacen/CLOUD-THIRD-PARTY-REGISTER.yaml` como
insumo; registrar decisões de risco tomadas no período)*

## Plano de ação para o próximo ciclo

- Estado do bloco normativo: `parcial`.
- Ações técnicas existentes permanecem rastreadas nos controles internos e artefatos BACEN do ReqSys.
- Lacuna: consolidar neste relatório os planos corretivos derivados de incidentes, continuidade, pentest e vulnerabilidades, sem converter ausência de avaliação em conformidade parcial.

*(seção narrativa — priorizar lacunas abertas na matriz de controles,
especialmente as de criticidade `critical`)*

## Aprovação

| Papel | Nome | Data | Assinatura |
|---|---|---|---|
| Responsável executivo | *(pendente)* | | |
| Revisão — GOVERNANCE | | | |
