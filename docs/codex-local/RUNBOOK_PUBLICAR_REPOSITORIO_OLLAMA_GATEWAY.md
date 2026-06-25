# Runbook — Publicar repositório independente do Ollama Local Gateway

## Objetivo

Padronizar a criação e publicação do repositório independente `ericson-j-santos/reqsys-ollama-local-gateway`, mantendo o ReqSys como produto principal e o gateway como provider local governado.

## Estado atual evidenciado

- Repositório esperado: `ericson-j-santos/reqsys-ollama-local-gateway`
- Resultado atual da validação: `404 Not Found`
- Natureza do bloqueio: ação manual humana no GitHub
- Issue relacionada: `#95`
- PR relacionado no repositório principal: `#96`

## Decisão arquitetural

O gateway independente não substitui o Codex Local/Online do ReqSys. Ele deve atuar como provider local via HTTP para permitir uso de modelos Ollama em ambiente controlado.

## Ação manual obrigatória

Criar manualmente o repositório GitHub:

```text
ericson-j-santos/reqsys-ollama-local-gateway
```

Configuração recomendada:

| Configuração | Valor recomendado |
|---|---|
| Owner | `ericson-j-santos` |
| Nome | `reqsys-ollama-local-gateway` |
| Branch padrão | `main` |
| README inicial | Sim |
| Visibilidade | Definir conforme estratégia de publicação |
| Actions | Habilitado |
| Issues | Habilitado |
| Branch protection | Habilitar após primeiro push |
| Licença | Definir explicitamente antes de uso externo |

## Estrutura mínima recomendada do repositório independente

```text
reqsys-ollama-local-gateway/
├── README.md
├── CHANGELOG.md
├── LICENSE
├── .env.example
├── .gitignore
├── pyproject.toml
├── src/
│   └── reqsys_ollama_gateway/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── audit.py
│       ├── schemas.py
│       └── ollama_client.py
├── tests/
│   ├── test_health.py
│   ├── test_chat_contract.py
│   └── test_audit.py
├── docs/
│   ├── ADR-001-provider-local-ollama.md
│   └── SECURITY.md
└── .github/
    └── workflows/
        └── ci.yml
```

## Gates mínimos antes de considerar pronto

- `pytest` verde.
- `ruff` verde.
- Nenhuma chamada real ao Ollama nos testes unitários.
- `.env.example` sem segredo real.
- Logs com `correlation_id`.
- Nenhum token, senha, CPF, PII ou connection string em log.
- Endpoint de health check sem expor informações sensíveis.
- CORS sem wildcard em produção.
- Documentação de execução local.
- CI com artifact de evidência.

## Comandos sugeridos após criação manual do repositório

```bash
git clone https://github.com/ericson-j-santos/reqsys-ollama-local-gateway.git
cd reqsys-ollama-local-gateway

git checkout -b bootstrap/gateway-inicial
# copiar/adaptar pacote independente gerado pelo ReqSys
python -m pytest -q
ruff check .

git add .
git commit -m "feat: bootstrap do ReqSys Ollama Local Gateway"
git push -u origin bootstrap/gateway-inicial
```

Depois, abrir PR para `main` no repositório independente.

## Próximo passo após publicação

1. Vincular o PR do novo repositório à issue `#95` do ReqSys.
2. Atualizar o PR `#96` com o link do repositório independente.
3. Validar consumo do gateway via provider `ollama_gateway` no ReqSys.
4. Manter isolamento arquitetural: o ReqSys consome o gateway por API; não duplicar produto dentro do monólito.

## Status operacional

Enquanto o repositório independente não existir, esta frente permanece com bloqueio manual humano.