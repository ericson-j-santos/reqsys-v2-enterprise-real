# PR Scope Labeler hardening

## Requisitos

1. Não usar `pull_request_target`.
2. Não conceder `issues: write` ao labeler.
3. Não mutar labels no workflow de snapshot inicial.
4. Não reativar CodeRabbit como dependência operacional.
5. Preservar PR Quality Review como revisão canônica.
6. Cobrir as invariantes com teste preventivo.

## Critérios de aceite

- teste preventivo verde;
- SDD/governança verdes;
- `behind_by=0`;
- PR mergeável e sem conflitos.
