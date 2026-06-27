# Trilhas A–E — Padrão Ouro

Hub consolidado das trilhas operacionais do ReqSys.

## Navegação

- **Hub HTML:** [`index.html`](index.html)
- **Registry:** [`trilhas-registry.json`](trilhas-registry.json)
- **ADR:** [`docs/adr/ADR-040-trilhas-padrao-ouro.md`](../../adr/ADR-040-trilhas-padrao-ouro.md)
- **Runbook:** [`docs/runbooks/trilhas-padrao-ouro.md`](../../runbooks/trilhas-padrao-ouro.md)

## Validação

```bash
python scripts/trilhas_padrao_ouro.py
cat audit/trilhas/trilhas-padrao-ouro-report.json
```

Workflow: `.github/workflows/trilhas-padrao-ouro.yml`
