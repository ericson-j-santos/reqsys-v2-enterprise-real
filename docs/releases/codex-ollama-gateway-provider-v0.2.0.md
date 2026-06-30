# Release Note — Codex Ollama Gateway Provider v0.2.0

## Entregas

- Provider `ollama_gateway` no Codex governado (`POST /v1/codex/analyze`).
- Bootstrap v0.2.0 do gateway com `POST /v1/chat`.
- Script `scripts/sincronizar_ollama_gateway_repo.sh`.
- Documentação e contratos Tier 1 atualizados.

## Configuração

```env
CODEX_OLLAMA_GATEWAY_URL=http://localhost:8008
CODEX_OLLAMA_GATEWAY_API_KEY=placeholder-local-dev
CODEX_OLLAMA_GATEWAY_MODEL=qwen2.5-coder:7b
```

## Validação

```bash
cd backend && pytest tests/test_codex_governado.py -v
cd docs/ollama-local-gateway/bootstrap-files && pytest -q
python3 tools/codex-local-online/validate.py
```

## Referência

Issue #95 — Integrar provider Ollama Local Gateway ao Codex.
