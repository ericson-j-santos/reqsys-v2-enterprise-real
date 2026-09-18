# Política de Auditoria, Rastreabilidade e Retenção de Evidências — ReqSys

## Objetivo

Garantir que toda evidência gerada pelos controles mínimos BACEN (`governance/bacen/BACEN-CONTROL-MATRIX.yaml`) seja íntegra, rastreável e retida pelo prazo mínimo exigido, com trilha auditável de quando e a partir de qual execução cada artifact foi produzido.

## Escopo

- todo artifact JSON publicado em `artifacts/bacen/`;
- os workflows de CI que geram esses artifacts (`bacen-minimum-controls-gate.yml`, `bacen-backup-restore-evidence.yml`, `bacen-stg-restore-test.yml`, `bacen-third-party-register-gate.yml`);
- o índice consolidado gerado por `scripts/consolidate_bacen_audit_evidence.py`.

## Requisitos mínimos

1. Toda evidência de controle deve conter, no mínimo, `schema_version`, um identificador do controle (`control_id`) e um timestamp de geração.
2. O índice consolidado deve calcular o SHA-256 de cada artifact de evidência existente no momento da execução, permitindo detectar divergência (tampering) entre execuções.
3. A retenção mínima dos artifacts publicados em CI é de 365 dias (`retention-days: 365` nos workflows), salvo prazo corporativo superior aplicável a um controle específico.
4. O índice deve ser regenerado a cada alteração em `governance/bacen/**` ou `artifacts/bacen/**` e publicado como artifact auditável.
5. Ausência de evidência declarada na matriz (`BACEN-CONTROL-MATRIX.yaml`) para um controle com status `implemented` ou `partial` é tratada como falha do gate.

## Evidência mínima do índice consolidado

O artifact `artifacts/bacen/bacen-07-audit-evidence-index.json` deve conter:

- `schema_version`;
- `control_id=BACEN-07`;
- `generated_at` (UTC);
- lista `entries`, uma por artifact de evidência encontrado, com `path`, `sha256`, `size_bytes` e `control_id` (quando declarado no próprio artifact);
- `summary` com contagem total de evidências indexadas e controles cobertos;
- `result` (`valid` ou `invalid`).

## Critérios de bloqueio

- artifact de evidência sem `schema_version` reconhecível;
- controle com status `implemented`/`partial` na matriz sem nenhum artifact correspondente indexado;
- índice não gerado na execução de CI.

## Responsabilidades

- `SECURITY`: manter o índice, revisar divergências de integridade;
- `RUNTIME_OPERATOR`: garantir que os workflows geradores de evidência publiquem artifacts corretamente;
- `GOVERNANCE`: revisar cobertura da matriz e prazos de retenção.
