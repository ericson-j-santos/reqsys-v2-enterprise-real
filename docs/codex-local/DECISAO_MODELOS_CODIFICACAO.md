# Decisão Técnica — Codex Local para Codificação

## Estado recomendado

Para o Codex gratuito/local com foco em codificação, a decisão recomendada é **não começar pelo Code Llama como modelo principal**.

Code Llama continua útil como referência histórica e fallback, mas hoje a estratégia mais eficiente é usar modelos coder mais recentes e leves para execução local.

## Decisão objetiva

### Modelo principal recomendado

| Prioridade | Modelo | Uso recomendado |
|---|---|---|
| 1 | Qwen Coder / Qwen2.5-Coder / Qwen3-Coder, conforme disponibilidade no runtime | Melhor equilíbrio para código, refatoração e agentes |
| 2 | DeepSeek Coder | Boa alternativa para geração e análise de código |
| 3 | Code Llama | Fallback, comparação e compatibilidade |
| 4 | Llama Instruct geral | Apoio em análise, documentação, requisitos e explicação |

## Por que não iniciar pelo Code Llama como principal

- É adequado para código, mas não é mais a opção mais eficiente para agente local moderno.
- Modelos coder mais recentes tendem a lidar melhor com tarefas agentic, refatoração, geração de testes e análise contextual.
- Para PC local, eficiência por RAM/VRAM importa mais que apenas tamanho nominal do modelo.

## Banco de dados dedicado

### Não obrigatório no primeiro incremento

Para começar, não é obrigatório criar banco relacional dedicado.

O mínimo necessário é:

- volume local para modelos Ollama;
- pasta versionada de configuração;
- logs estruturados;
- base vetorial opcional para RAG.

### Quando passa a ser necessário

Um banco dedicado passa a fazer sentido quando o Codex precisar manter:

- histórico de execuções;
- trilhas de auditoria;
- permissões por usuário/projeto;
- memória operacional governada;
- métricas de tokens, latência e custo;
- catálogo de repositórios, branches, PRs e artefatos;
- resultados de validação e remediação.

## Estratégia de dados recomendada

| Necessidade | Tecnologia recomendada |
|---|---|
| Configuração simples | Arquivos versionados YAML/JSON |
| RAG sobre código/documentação | Qdrant |
| Auditoria e operação | PostgreSQL ou SQL Server |
| Cache/fila | Redis |
| Métricas | Prometheus/OpenTelemetry |

## Uso de PC com muita memória

Faz sentido usar um PC próprio com bastante memória, principalmente para:

- execução local gratuita;
- validação de modelos;
- inferência sem custo por token;
- análise de código e documentação;
- ambiente de desenvolvimento assistido.

### Melhor cenário

- CPU moderna;
- 32 GB RAM mínimo;
- 64 GB RAM recomendado;
- SSD/NVMe;
- GPU NVIDIA com VRAM, se disponível.

### Observação importante

Para LLM local, muita RAM ajuda, mas **VRAM da GPU é o fator que mais melhora performance**. Se não houver GPU, ainda funciona via CPU, porém com menor velocidade.

## Decisão operacional para agora

Implementar em fases:

1. Subir Ollama local com modelo coder eficiente.
2. Adicionar adapter governado no backend.
3. Registrar auditoria e correlation_id.
4. Integrar com ReqSys como provider local.
5. Adicionar Qdrant apenas quando iniciar RAG sobre repositórios e ADRs.
6. Adicionar PostgreSQL/SQL Server dedicado apenas quando houver necessidade real de histórico operacional estruturado.

## Configuração recomendada inicial

```bash
ollama pull qwen2.5-coder:7b
ollama pull deepseek-coder:6.7b
ollama pull codellama:7b
```

## Provider recomendado

```txt
Provider principal: Ollama
Modelo principal: qwen2.5-coder:7b ou equivalente coder mais recente disponível
Fallback local: deepseek-coder:6.7b
Fallback compatibilidade: codellama:7b
Fallback cloud governado: OpenAI/Claude, se habilitado
```

## Gate de segurança

O Codex local não deve executar comandos automaticamente fora de sandbox.

Regras obrigatórias:

- sem acesso direto a secrets;
- sem execução direta em produção;
- sem SQL livre em bases reais;
- sem push automático sem revisão;
- logs com mascaramento de dados sensíveis;
- todas as ações com `correlation_id`;
- execução em Docker/sandbox para comandos de shell.
