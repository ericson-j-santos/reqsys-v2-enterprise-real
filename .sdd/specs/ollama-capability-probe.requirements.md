# Probe governado de capacidade Ollama

## Requisito 1 — inventário real do runtime
O probe deve consultar a API HTTP do Ollama em loopback e registrar versão, modelos disponíveis/ativos, capacidades e metadados suficientes para distinguir modelo local de referência remota/cloud quando a API fornecer esses campos.

## Requisito 2 — contexto suportado e efetivo
O resultado deve separar o limite de contexto informado pelo modelo dos valores efetivamente reportados pelo runtime, incluindo `context_length` e `num_ctx` quando presentes.

## Requisito 3 — benchmark de código
O probe deve executar uma tarefa de código controlada, sem acesso a arquivos, segredos ou ferramentas externas, registrar latência/tokens por segundo e verificar requisitos objetivos mínimos da resposta.

## Requisito 4 — tool calling sem efeito real
O benchmark de tool calling deve fornecer apenas um schema de ferramenta fictícia. A validação termina na emissão correta da chamada e dos argumentos; a ferramenta não deve ser executada pelo probe.

## Requisito 5 — segurança e governança
Por padrão, somente endpoints loopback são permitidos. Endpoint remoto exige opção explícita. O probe não deve ler credenciais, arquivos de ambiente ou tokens, e sua saída não deve conter segredos.

## Requisito 6 — comparação de thinking
Deve ser possível executar o benchmark preservando o comportamento padrão do modelo ou com `thinking` explicitamente desligado, sem alterar permanentemente a configuração do Ollama.

## Critérios de aceite
1. Os testes unitários offline do probe passam sem exigir Ollama instalado.
2. Um runtime Ollama acessível em loopback produz JSON contendo modelo selecionado, capacidades e contexto reportado.
3. O benchmark de tool calling identifica nome e argumentos corretos sem executar a ferramenta fictícia.
4. O benchmark de código registra métricas e uma avaliação objetiva dos requisitos do exercício.
5. URLs não-loopback são recusadas por padrão.
6. Nenhum benchmark altera o repositório ou grava segredo.
