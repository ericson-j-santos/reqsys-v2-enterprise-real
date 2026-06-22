# Release — Codex Ollama Gateway Provider v0.2.0

Data: 2026-06-22  
Branch: `feature/ollama-gateway-provider`  
Issue: #95

## Resumo

Incremento para conectar o **Codex Local/Online no ReqSys** ao **ReqSys Ollama Local Gateway** sem transformar o gateway em produto concorrente.

## Decisão operacional

O componente mantido como principal é:

```text
Codex Local/Online no ReqSys
```

O gateway passa a ser:

```text
Provider local governado de IA
```

## Mudanças implementadas

| Área | Mudança |
|---|---|
| Backend | Novo provider `ollama_gateway` no serviço `codex_governado` |
| Configuração | Novas variáveis `CODEX_OLLAMA_GATEWAY_*` |
| API | `/v1/codex/status` passa a listar `ollama_gateway` |
| Testes | Teste unitário para contrato HTTP do gateway sem rede real |
| Infra | Exemplo `.env` atualizado para provider canônico local |
| Documentação | Decisão de arquitetura e matriz de equivalência |

## Variáveis adicionadas

```env
CODEX_OLLAMA_GATEWAY_URL=
CODEX_OLLAMA_GATEWAY_API_KEY=
CODEX_OLLAMA_GATEWAY_MODEL=
CODEX_OLLAMA_GATEWAY_TIMEOUT_SECONDS=60
```

## Validação prevista no CI

```bash
pytest backend/tests/test_codex_governado.py
```

## Riscos mitigados

| Risco | Mitigação |
|---|---|
| Expor Ollama direto na rede | ReqSys consome gateway, não porta `11434` |
| Duplicar produto | Gateway tratado só como provider |
| Acoplamento forte | Contrato HTTP isolado |
| Chamada real nos testes | Teste usa monkeypatch em `_post_json` |
| Falta de rastreabilidade | Issue #95 e documentação versionada |

## Próximo incremento recomendado

Implementar tela operacional no ReqSys para selecionar provider:

- `mock`
- `ollama`
- `ollama_gateway`
- `openai`
- `claude`

com health check do gateway e status do modelo local.
