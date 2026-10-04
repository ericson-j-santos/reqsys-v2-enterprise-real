# Dependency security refresh — 2026-09-30

## Objetivo

Remover vulnerabilidades novas detectadas pelos gates atuais de `npm audit` e
`pip-audit`, sem desabilitar os gates e sem tratar rerun como correção.

## Requisitos

1. O frontend deve exigir no mínimo `axios 1.20.0` e `DOMPurify 3.4.16`.
2. O backend e o arquivo de auditoria devem fixar `PyJWT 2.15.0` e `urllib3 2.8.0`.
3. O token broker deve permanecer alinhado em `PyJWT 2.15.0`.
4. O `package-lock.json` deve ser regenerado pelo workflow versionado
   `CI Lockfile Security Remediation`, seguido de `npm ci` e
   `npm audit --omit=dev --audit-level=high`.
5. O gate Python deve reexecutar `pip-audit -r requirements-audit.txt --no-deps`
   no HEAD exato e não pode ignorar advisories.
6. Testes devem impedir retorno aos quatro pisos vulneráveis.
7. Nenhum deploy, produção, segredo ou permissão administrativa faz parte desta correção.

## Evidência de origem

- artifact `backend-pip-audit-report` da run `36772334403`:
  - `PyJWT 2.14.0` afetado por `CVE-2026-101918`, corrigido em `2.15.0`;
  - `urllib3 2.7.0` afetado por `CVE-2026-97687`, `CVE-2026-97688` e
    `CVE-2026-97689`, corrigidos em `2.8.0`.
- `npm audit` da mesma run detectou vulnerabilidades atuais em
  `axios 1.19.0` e `DOMPurify 3.4.13`.

## Critério de aceite

- `npm audit --omit=dev --audit-level=high` aprovado;
- `pip-audit -r requirements-audit.txt --no-deps` aprovado;
- testes de regressão aprovados;
- CI da PR verde no HEAD corrente.
