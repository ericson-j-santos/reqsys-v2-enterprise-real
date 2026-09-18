# Release Note — Codex Local Online v1.0.0

## Entregas

- Aplicação online estática.
- Workflow de validação e deploy GitHub Pages.
- Integração ReqSys por payload rastreável.
- Guard rails básicos contra credenciais e PII.
- ADR e runbook.

## Validação local

```bash
python tools/codex-local-online/validate.py
```

## Próximo incremento

Publicar backend governado para execução real com modelo, autenticação, CORS restrito, auditoria e rate limit.
