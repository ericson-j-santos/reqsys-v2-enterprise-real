# BACEN — renovação restrita da tolerância NONPROD (23/11 a 23/12/2026)

## Objetivo

Preparar, na mesma demanda canônica ReqSys #1615, uma nova janela de tolerância operacional apenas para `pull_request`, `dev` e `stg`, sem alterar a matriz regulatória, as aprovações humanas, a produção ou a exceção separada da #1505.

## Origem e autorização

O responsável autorizou explicitamente em 23/11/2026 **preparar** a vigência de 23/11/2026 a 23/12/2026, mantendo PROD bloqueado, controles parciais, proibição de aprovações fictícias e todos os gates obrigatórios. **Merge e deploy não foram autorizados.** Esta especificação não equivale a assinatura institucional, aceite jurídico ou aprovação regulatória.

Base técnica observada: `main@a05e64bbc58a15314b42cfa9314f1d415535b05b`. Fonte de política: `governance/bacen/NONPROD-TEMPORARY-TOLERANCE-POLICY.yaml`.

## Requisitos

1. Modificar somente `activation.valid_from` para `2026-11-23` e `activation.valid_until` para `2026-12-23` na política existente (intervalo de 30 dias).
2. Preservar exatamente os escopos permitidos `pull_request`, `dev`, `stg`, e `prod` como escopo bloqueado.
3. Preservar `maximum_review_window_days: 30`, `renewal_requires_explicit_policy_change: true`, `production_touched: false` e os requisitos anti-fabricação e preservação dos status regulatórios.
4. Manter BACEN-01, BACEN-02, BACEN-05 e BACEN-08 em `partial`; não inferir assinatura, designação, evidência jurídica ou permissão para PROD.
5. Não renovar implicitamente a exceção NONPROD da Issue #1505 vencida em 12/10/2026; seu fluxo de aprovação é distinto.
6. A branch candidata não autoriza deploy nem merge. A PR só pode ser criada com `READY_FOR_PR=passed` no SHA exato; integração e PROD continuam dependentes dos gates e autorizações específicas.

## Critérios de aceite

- [ ] Política no HEAD da branch candidata registra a janela exata 2026-11-23 a 2026-12-23, e nenhuma outra configuração de produção/regulação foi alterada.
- [ ] O gerador de decisão permite tolerância somente a controles `partial` em PR/DEV/STG durante a janela e preserva os status.
- [ ] O mesmo gerador bloqueia PROD com controles `partial`, inclusive dentro da janela.
- [ ] A partir de 2026-12-24, a política expirada volta a bloquear a tolerância, sem prorrogação automática.
- [ ] Testes positivos e negativos do gerador e contrato de bloqueio de PROD aprovados no HEAD exato.
- [ ] Pre-PR Readiness Gate e demais gates aplicáveis aprovados no HEAD corrente antes da abertura da PR.
- [ ] Nenhum merge, deploy PROD, alteração de secrets ou evidência/aprovação humana fabricada.

## Evidência e responsabilidade

- Testes existentes: `tests/test_generate_bacen_nonprod_tolerance_decision.py` e `tests/test_bacen_production_hard_gate_contract.py`.
- Gate real: `.github/workflows/bacen-nonprod-tolerance-guard.yml` e `Pre-PR Readiness Gate`.
- Issue canônica: #1615; #1505 apenas como dependência separada.
- Responsável por eventual integração: proprietário, somente mediante autorização posterior e gates atuais; responsável pela avaliação formal dos controles: GOVERNANCE/Jurídico.
