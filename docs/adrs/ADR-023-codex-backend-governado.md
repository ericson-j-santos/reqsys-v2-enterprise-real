# ADR-023 — Backend governado do Codex Online

## Status

Proposto para validacao em PR.

## Contexto

O Codex Online publicado em GitHub Pages precisava de uma ponte segura para executar analises reais com provedores de IA e para registrar resultados no ReqSys. O frontend nao deve armazenar credenciais de provedores nem chamar modelos diretamente.

## Decisao

Implementar o endpoint autenticado `POST /v1/codex/analyze` no backend FastAPI do ReqSys, com:

- autenticacao JWT existente;
- rate limit em memoria por usuario;
- auditoria estruturada por `correlation_id`;
- bloqueio basico de conteudo sensivel;
- suporte a providers `mock`, `ollama`, `openai` e `claude`;
- payload rastreavel para ReqSys;
- publicacao opcional para endpoint ReqSys configuravel.

## Consequencias

- O GitHub Pages passa a operar como UI de orquestracao.
- Os segredos ficam restritos ao backend.
- A integracao real depende de configuracao de ambiente.
- A execucao mock permite validacao segura sem custo externo.

## Variaveis de ambiente

- `CODEX_OLLAMA_BASE_URL`
- `CODEX_OLLAMA_MODEL`
- `CODEX_OPENAI_KEY`
- `CODEX_OPENAI_MODEL`
- `CODEX_CLAUDE_KEY`
- `CODEX_CLAUDE_MODEL`
- `CODEX_REQSYS_ENDPOINT`
- `CODEX_REQSYS_KEY`

## Guard rails

- Nao aceitar conteudo com padroes basicos de credencial ou CPF.
- Exigir JWT em todos os endpoints do Codex governado.
- Registrar auditoria sem gravar conteudo bruto completo em logs.
- Aplicar rate limit antes de chamar provedores externos.
