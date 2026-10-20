# Requisitos — classificação inválida de urgência no Assistente IA

## Objetivo e rastreabilidade

Issue canônica: [ReqSys #2973](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/2973). TODO Global: [TODO-38](https://app.notion.com/3ff4c12bae7c81cebbe9cf958bb724b1). Correlação: `REQSYS-URGENCIA-20261020-01`. Ambiente autorizado: DEV. Não alterar autenticação, armazenamento, dados de produção ou permissões.

## Requisitos funcionais

1. O serviço não pode inicializar resposta de urgência com categoria média e aceitá-la quando o provedor omitir ou apresentar categoria inválida.
2. Aceitar somente uma classificação reconhecida entre `baixa`, `media`, `alta`, `critica`, com justificativa não vazia. Normalizar as variantes de acento do contrato, mas rejeitar duplicatas, ausência, campo desconhecido e texto extra.
3. Resposta inválida deve gerar HTTP 502, código `IA_CLASSIFICACAO_INVALIDA` e mensagem fixa sanitizada; indisponibilidade permanece HTTP 503.
4. O formulário deve validar envelope `success=true`, categoria e justificativa antes de aplicar sugestão. A urgência e a descrição informadas manualmente devem sobreviver a falha parcial, edição durante a requisição, cancelamento, reabertura e salvamento.
5. A chamada deve usar o cliente API compartilhado para aproveitar configuração de runtime, autenticação e correlação existentes.
6. Nenhuma nova chamada ao provedor deve ocorrer silenciosamente somente porque a resposta recebida está malformada.

## Critérios de aceite

- A regressão reproduz o defeito na base anterior e passa com a correção.
- As quatro categorias válidas e as variantes normalizadas permanecem aceitas.
- Resposta vazia, categoria ambígua, campos repetidos ou ausentes e justificativa vazia resultam em 502 sem classificação falsa ou vazamento de conteúdo do provedor.
- O provedor indisponível retorna 503; entrada HTTP malformada retorna 422.
- HTTP 200 com envelope inválido ou `success=false` não modifica urgência.
- Em falha, `Salvar` envia exatamente os valores correntes do formulário e a consulta IA atrasada não consegue sobrescrever edições posteriores.
- Testes backend/frontend definidos em `sdd_gate.tests` devem executar e aprovar no HEAD exato.
- Pre-PR Readiness exige `READY_FOR_PR=passed` antes de abrir PR; CI e E2E aplicável posteriores não podem ser pulados.
- O E2E DEV final exige salvar um requisito de teste, recuperar por ID e comparar os campos; não afirmar esse aceite com provider ou armazenamento simulados.
- O produtor TODO Global só envia uma tarefa após elegibilidade e idempotência revalidadas; não forçar `PENDENTE` para fabricar prova.

## Prevenção e limites

A cobertura inclui casos de serviço, API, formulário e concorrência de respostas. Esta especificação é um contrato de revisão, não comprovação de testes. Runtime, deploy, merge, dispositivos, credenciais, recursos pagos e dados reais continuam fora do escopo até gates próprios.
