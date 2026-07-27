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

<!-- BACEN-08:CONTROLS-SUMMARY:START -->

| Controle | Domínio | Criticidade | Status |
|---|---|---|---|
| BACEN-01 | governance | critical | partial |
| BACEN-02 | identity | critical | partial |
| BACEN-03 | incidents | critical | partial |
| BACEN-04 | continuity | critical | implemented |
| BACEN-05 | third_party | high | partial |
| BACEN-06 | secure_development | high | implemented |
| BACEN-07 | audit | high | implemented |
| BACEN-08 | executive_governance | critical | partial |

Total: **8** · Implementados: **3** · Parciais: **5** · Lacunas: **0** · Cobertura ponderada: **37.5%**
<!-- BACEN-08:CONTROLS-SUMMARY:END -->

## Incidentes de segurança do período

*(seção narrativa — a integração automatizada de dados de incidentes ainda não
existe; ver BACEN-03, hoje `partial`. Até que essa integração exista, esta seção
deve ser preenchida manualmente a partir dos registros de
`governance/bacen/INCIDENT-RESPONSE-PLAN.md` e do processo operacional real.)*

## Avaliação de terceiros e nuvem

*(seção narrativa — usar `governance/bacen/CLOUD-THIRD-PARTY-REGISTER.yaml` como
insumo; registrar decisões de risco tomadas no período)*

## Plano de ação para o próximo ciclo

*(seção narrativa — priorizar lacunas abertas na matriz de controles,
especialmente as de criticidade `critical`)*

## Aprovação

| Papel | Nome | Data | Assinatura |
|---|---|---|---|
| Responsável executivo | *(pendente)* | | |
| Revisão — GOVERNANCE | | | |
