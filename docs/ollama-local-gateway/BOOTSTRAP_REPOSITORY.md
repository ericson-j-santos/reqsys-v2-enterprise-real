# Bootstrap — reqsys-ollama-local-gateway

## Objetivo

Definir o pacote mínimo governado para criação e inicialização do repositório externo `ericson-j-santos/reqsys-ollama-local-gateway`.

## Pendência P0

Repositório externo **criado**. Publicar v0.2.0 via `scripts/sincronizar_ollama_gateway_repo.sh` (requer permissão de push no repo externo).

## Repositório alvo

- Owner: `ericson-j-santos`
- Nome: `reqsys-ollama-local-gateway`
- Visibilidade recomendada: privada, salvo decisão explícita contrária
- Branch padrão: `main`

## Configurações obrigatórias

| Dimensão | Configuração mínima |
|---|---|
| Actions | Habilitado |
| Branch protection | `main` protegida |
| Required checks | CI, security, governance |
| Environments | `dev`, `hml`, `prod` |
| Secrets | Governados por ambiente |
| CODEOWNERS | Obrigatório |
| SECURITY.md | Obrigatório |
| Dependabot | Ativo |
| Release | SemVer + changelog |

## Estrutura inicial recomendada

```text
reqsys-ollama-local-gateway/
├── .github/
│   ├── CODEOWNERS
│   ├── dependabot.yml
│   ├── pull_request_template.md
│   └── workflows/
│       ├── ci.yml
│       └── governance.yml
├── docs/
│   ├── ARCHITECTURE.md
│   ├── SECURITY_GUARDRAILS.md
│   └── OPERATIONS.md
├── src/
│   └── reqsys_ollama_gateway/
│       ├── __init__.py
│       ├── app.py
│       ├── config.py
│       ├── gateway.py
│       └── schemas.py
├── tests/
│   └── test_health.py
├── .gitignore
├── LICENSE
├── README.md
├── SECURITY.md
└── pyproject.toml
```

## Guardrails permanentes

- Não expor connector admin sem autenticação.
- Não registrar tokens, prompts sensíveis, PII ou connection strings em logs.
- Exigir `correlation_id` em chamadas operacionais.
- Bloquear produção sem autenticação real.
- Bloquear CORS wildcard em produção.
- Não permitir fallback que gere resposta inventada sem fonte.
- Separar dev/hml/prod por environment.

## Próximo passo após criação humana

1. Criar o repositório no GitHub.
2. Aplicar os arquivos do `docs/ollama-local-gateway/bootstrap-files/`.
3. Criar PR inicial no novo repositório.
4. Validar CI verde.
5. Fechar a issue #125 como concluída.
