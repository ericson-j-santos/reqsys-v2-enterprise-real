# Changelog — Security Executive Summary

## Resumo

Adicionado consolidator executivo para os scanners especializados de segurança do ReqSys.

## Objetivo

Unificar as evidências técnicas dos scanners em um contrato executivo único, rastreável e consumível por dashboards e gates futuros.

## Arquivos adicionados

- `scripts/build_security_executive_summary.py`
- `tests/test_security_executive_summary.py`
- `docs/changelog/security-executive-summary.md`

## Arquivo atualizado

- `.github/workflows/security-specialized-scanners.yml`

## Contrato gerado

```text
artifacts/security-executive-summary/security-executive-summary.json
artifacts/security-executive-summary/security-executive-summary.md
```

## Scanners consolidados

- Gitleaks.
- pip-audit.
- npm audit.
- CycloneDX SBOM.

## Política operacional

- `pull_request` e `push`: modo report-only.
- `workflow_dispatch` com `strict=true`: bloqueia quando houver achado crítico consolidado.
- Sem deploy.
- Sem leitura de secrets.
- Sem chamadas externas no consolidator.
- Sem alteração funcional no runtime.

## Próximo incremento seguro

Expor `security-executive-summary.json` no Ops Dashboard como card executivo de segurança, mantendo o mesmo contrato como fonte única.