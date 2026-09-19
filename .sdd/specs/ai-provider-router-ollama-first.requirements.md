# Requisitos — AI Provider Router Ollama-first

## Escopo

Centralizar o roteamento textual de IA do ReqSys em um único `AIProviderRouter`, mantendo `LLMGateway` como porta HTTP canônica, com `ollama_gateway` como provider padrão e providers externos disponíveis somente por seleção/configuração explícita e política vigente.

## Requisitos funcionais

1. Usar `ollama_gateway` como provider textual padrão quando nenhum provider explícito for solicitado.
2. Preservar `ollama`, OpenAI, Claude, Gemini e Groq como rotas explícitas suportadas.
3. Propagar `correlation_id` pelo roteamento e registrar provider solicitado, provider efetivo e modelo.
4. Reutilizar o fallback já existente do Ollama Gateway para modelo local configurado, sem duplicar cliente HTTP.
5. Fazer Codex Governado, conversas de IA, geração RAG e IA Assistente passarem pelo `AIProviderRouter`.
6. Manter embeddings RAG na porta comum `LLMGateway`, sem criar segundo transporte HTTP.
7. Tratar `ollama_gateway` como provider local para a restrição corporativa de dados `restricted`.
8. Manter providers externos disponíveis quando autorizados e configurados; este incremento não remove multi-provider.
9. Falhar fechado para provider desconhecido ou Ollama Gateway sem configuração mínima.
10. Impedir novas integrações diretas com endpoints/SDKs de providers fora das portas canônicas por teste arquitetural.
11. Se o provider de geração RAG falhar, preservar o fallback determinístico baseado nas fontes recuperadas.
12. Não realizar deploy, promoção de ambiente, mutação de segredo ou merge neste incremento.

## Critérios de aceite

- provider omitido resolve para `ollama_gateway`;
- o modelo primário e o fallback Ollama configurados são propagados ao gateway;
- provider externo explícito continua roteável pelo mesmo router;
- Ollama direto continua disponível como rota explícita;
- provider desconhecido é bloqueado;
- Ollama Gateway sem URL configurada é bloqueado;
- Codex, conversas, RAG e IA Assistente usam o router único para geração textual;
- teste arquitetural falha se novo código de backend introduzir endpoint/SDK direto de provider fora de `ai_provider_config.py` e `llm_provider.py`;
- testes direcionados do incremento ficam verdes;
- `Pre-PR Readiness Gate` fica verde no HEAD exato;
- branch permanece `behind_by=0` antes da abertura da PR.

## Fora do escopo

- remover suporte a OpenAI, Claude, Gemini ou Groq;
- substituir embeddings RAG por Ollama neste incremento;
- alterar credenciais ou cofre;
- deploy ou promoção para HML/STG/PROD;
- merge.
