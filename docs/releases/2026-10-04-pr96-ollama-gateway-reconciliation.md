# Reconciliação do PR #96 — provider Ollama Gateway

## Estado observado

O objetivo do PR #96 já está incorporado e evoluído na `main`.

A arquitetura canônica atual possui:

- provider `ollama_gateway`;
- `CODEX_OLLAMA_GATEWAY_URL`, API key, modelo, fallback e timeout;
- roteamento central por `AIProviderRouter`;
- Codex Governado consumindo o provider canônico;
- gateway local em loopback, sem exposição direta da porta nativa do Ollama;
- bridge MCP governada;
- bootstrap e documentação do gateway;
- configuração Continue/VS Code;
- E2E self-hosted ReqSys → Ollama Gateway no PC24x7;
- regras anti-bypass e fail-closed para provider não configurado;
- fallback de modelo local versionado.

## Decisão

Não restaurar os nove arquivos históricos do PR #96. A implementação antiga antecede o roteador canônico de providers e reduziria a arquitetura atual a uma integração específica do Codex.

## Preservação do trabalho

A decisão original permanece: Codex é a experiência principal e o Ollama Gateway é um provider/componente local governado, não um produto concorrente.

## Critério de conclusão

- branch sincronizada com a `main`;
- nenhuma integração atual substituída por versão histórica;
- `behind_by=0`;
- PR sem conflitos;
- gates obrigatórios verdes no HEAD reconciliado.
