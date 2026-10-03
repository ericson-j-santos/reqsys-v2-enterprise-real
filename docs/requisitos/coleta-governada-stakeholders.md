# Coleta governada de informações para geração de requisitos

## Objetivo

Padronizar como partes interessadas e integrantes da equipe fornecem informações ao ReqSys antes da geração de requisitos. O formulário não deve pedir uma solução pronta como primeira pergunta; ele deve capturar problema, objetivo, contexto, regras, critérios de aceite, dependências e rastreabilidade.

## Decisão de canal

1. **ReqSys**: canal preferencial e fonte de verdade. O formulário deve ser renderizado a partir do contrato publicado pela API `GET /api/requisitos/coleta/formulario`.
2. **Microsoft Forms**: canal de entrada simples quando o público ainda não tiver acesso direto ao ReqSys. As respostas devem ser transformadas pelo Power Automate no mesmo contrato canônico.
3. **Power Apps**: indicado quando houver regras condicionais complexas, listas corporativas, permissões específicas ou validações que não sejam adequadas a um formulário simples.
4. **Teams**: canal de comunicação e atalho para abrir o formulário; não deve ser a fonte primária de texto livre para requisitos.
5. **Power Automate**: camada de integração entre canais externos e o contrato canônico do ReqSys.

## Regra principal

Nenhum canal externo cria um requisito diretamente. Todos enviam o mesmo contrato para `POST /api/requisitos/coleta/previsualizar` e, somente quando a pontuação mínima for atingida, para `POST /api/requisitos/coleta/gerar`.

## Perguntas que devem ser apresentadas

### 1. Identificação e contexto

- Quem está solicitando?
- Qual área é responsável pela necessidade?
- Qual sistema, processo ou produto é afetado?
- Qual é o tipo de demanda: nova funcionalidade, alteração, correção, automação, relatório, integração ou regulatório?
- Existe chamado, norma, política, épico, incidente ou outra referência rastreável?

### 2. Problema e resultado esperado

- Qual problema existe hoje? Descreva o impacto e não apenas a solução desejada.
- Qual resultado precisa ser alcançado?
- Quem é o usuário, perfil ou área afetada?
- Como o processo funciona atualmente?
- Como deve funcionar no cenário desejado?

### 3. Regras e critérios

- Quais regras de negócio precisam ser respeitadas?
- Quais condições permitem afirmar que a demanda foi atendida?
- Há impacto regulatório, normativo, de segurança, privacidade ou auditoria?

Os critérios de aceite devem ser objetivos e verificáveis. Evitar frases como “funcionar corretamente”, “ser rápido” ou “ficar melhor” sem uma condição mensurável.

### 4. Dependências

- Quais dados são necessários?
- Quais sistemas, APIs, filas, arquivos ou serviços participam do fluxo?
- Há restrições técnicas, operacionais, de prazo, acesso ou ambiente?
- Qual a urgência real?
- Existe data limite externa? Se existir, por quê?

## Informações que não devem ser inseridas

- senha;
- token;
- segredo;
- chave de acesso;
- cadeia de conexão;
- dado pessoal desnecessário para definir o requisito;
- conteúdo binário ou Base64 quando um link corporativo governado puder ser utilizado.

## Qualidade e bloqueio

A coleta recebe pontuação de 0 a 100. O primeiro contrato usa pontuação mínima de **80** para geração automática. Coletas abaixo do limite permanecem em refinamento e retornam as pendências objetivas ao solicitante.

Demandas com impacto regulatório exigem uma referência externa rastreável.

## Idempotência

Toda submissão destinada à criação deve possuir `chave_idempotencia`. Para integrações:

- Microsoft Forms: usar identificador da resposta combinado com o identificador do formulário;
- Power Apps: usar identificador único gerado no registro;
- Power Automate: preservar a chave recebida, sem gerar uma nova em cada tentativa;
- ReqSys: gerar UUID no início da submissão e reutilizá-lo em retentativas.

O ReqSys armazena apenas o hash da chave na auditoria.

## Fluxo alvo

```text
PARTE INTERESSADA / EQUIPE
        |
        v
FORMULÁRIO ESTRUTURADO
        |
        v
PREVISUALIZAÇÃO + PONTUAÇÃO
        |
        +---- < 80 ----> REFINAMENTO / PENDÊNCIAS
        |
        v >= 80
GERAÇÃO IDEMPOTENTE
        |
        v
REQUISITO = RECEBIDO
        |
        v
WORKFLOW GOVERNADO DO REQSYS
```

## Evidências operacionais

Cada geração bem-sucedida registra evento de auditoria com:

- versão do contrato;
- origem;
- tipo de demanda;
- pontuação;
- classificação;
- hash da chave de idempotência;
- hash do conteúdo recebido;
- `correlation_id`.

O conteúdo sensível da coleta não deve ser duplicado no evento de auditoria.

## Próximos incrementos

1. Renderizar o contrato declarativo como formulário nativo no frontend principal do ReqSys.
2. Criar modelo de Microsoft Forms e fluxo Power Automate com mapeamento 1:1 para o contrato.
3. Publicar indicadores no Dashboard: volume de coletas, taxa de aprovação na primeira submissão, pontuação média, principais pendências, tempo de refinamento e origem.
4. Enviar acompanhamento no Teams somente após a observabilidade do evento estar validada, evitando mensagens duplicadas.
