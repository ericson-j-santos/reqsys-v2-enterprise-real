# CHANGE Impact Benchmark v1 — Requisitos

Objetivo: medir, sobre mudanças históricas conhecidas do ReqSys, quanto três estratégias reduzem revisão manual sem perder impactos reais.

## Requisito 1 — ground truth histórico versionado
O benchmark deve usar mudanças históricas com impacto conhecido e registrar a origem dos artefatos e o SHA de referência do dataset. O dataset inicial é apenas baseline e não pode ser apresentado como evidência de generalização.

## Requisito 2 — mesmas entradas para as estratégias
Cada mudança deve ser avaliada sobre o mesmo conjunto de artefatos por:
1. rastreabilidade explícita em grafo;
2. recuperação semântica usando o mecanismo local já existente no RAG do ReqSys;
3. híbrido grafo + RAG + LLM pelo `AIProviderRouter`.

## Requisito 3 — LLM restrito aos candidatos recuperados
O LLM não pode criar artefatos, links ou evidências canônicas. Ele somente seleciona e classifica IDs já recuperados pelo grafo/RAG. IDs fora do contexto recuperado devem ser ignorados.

## Requisito 4 — saída explicável
Cada candidato deve conter:
- `artifact_id`;
- tipo de relação;
- confiança entre 0 e 1;
- evidência derivada da fonte recuperada;
- justificativa;
- estratégia que produziu o candidato.

## Requisito 5 — métricas
Para cada mudança e estratégia, registrar ao menos:
- `recall`;
- `precision`;
- quantidade de candidatos;
- `review_rate`, isto é, fração do universo não-seed que precisaria de revisão.

Recall é a métrica de segurança principal; redução de revisão não pode ser interpretada como sucesso se impactos reais forem omitidos.

## Requisito 6 — falha fechada do LLM
Saída inválida, indisponibilidade do provider ou JSON malformado não pode virar candidato. Quando o LLM não estiver habilitado, o caminho híbrido deve ser identificado explicitamente como `hybrid_retrieval_fallback`, sem fingir validação de LLM.

## Requisito 7 — custo zero e reuso
A recuperação semântica deve reutilizar o mecanismo local do ReqSys. O LLM deve usar o roteador já existente, com preferência pela rota Ollama configurada, sem criar novo provedor ou runtime pago.

## Requisito 8 — validação e falso positivo
O incremento deve incluir:
- caso positivo do grafo contra ground truth conhecido;
- recuperação semântica real pelo mecanismo local;
- teste de LLM com ID alucinado que prove descarte;
- teste de saída LLM inválida que prove falha fechada;
- execução ponta a ponta do script dataset -> métricas -> artifact;
- caso negativo com dataset inconsistente e ausência de artifact de sucesso.

## Requisito 9 — evidência do LLM real
O contrato híbrido pode ser validado em CI por injeção determinística, mas a estratégia `grafo + RAG + LLM` só pode ser declarada funcionalmente validada depois de uma execução real no provider configurado, vinculada ao SHA atual e com `llm_status=used`.

## Requisito 10 — governança
O benchmark é somente leitura sobre dados versionados. Não executa merge, deploy, promoção, alteração de segredo nem grava rastreabilidade canônica do produto.

## Critérios de aceite
1. O dataset histórico é validado e referências inexistentes falham fechado.
2. Grafo e recuperação semântica executam sobre os mesmos casos.
3. O caminho híbrido rejeita IDs inventados pelo LLM.
4. Métricas são persistidas em JSON reproduzível.
5. O script retorna falha para dataset inconsistente e não cria artifact de sucesso.
6. `Pre-PR Readiness` retorna `READY_FOR_PR=passed` no HEAD final e `behind_by=0` antes da PR.
7. Conclusão da terceira estratégia exige E2E real do provider configurado no mesmo SHA; sem isso o estado permanece parcial.
