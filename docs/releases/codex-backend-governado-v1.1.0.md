# Release Note — Codex Backend Governado v1.1.0

## Entregas

- Endpoint `POST /v1/codex/analyze`.
- Endpoint `GET /v1/codex/status`.
- Autenticacao via JWT existente do ReqSys.
- Rate limit por usuario.
- Auditoria estruturada por `correlation_id`.
- Bloqueio basico de conteudo sensivel.
- Providers: mock, Ollama, OpenAI e Claude.
- Payload ReqSys e publicacao opcional.
- UI GitHub Pages atualizada para backend governado.
- Testes automatizados do servico.

## Validacao

```bash
cd backend
python -m pytest tests/test_codex_governado.py -v
```

## Proximo incremento

Persistir auditoria em tabela dedicada e expor dashboard operacional do Codex Governado dentro do ReqSys.
