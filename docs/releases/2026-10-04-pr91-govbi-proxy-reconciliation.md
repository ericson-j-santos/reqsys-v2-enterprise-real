# Reconciliação do PR #91 — proxy GovBI governado

## Estado observado

O objetivo do PR #91 já está incorporado e evoluído na `main`.

A implementação canônica atual possui:

- router backend `/api/govbi`;
- proxy `POST /api/govbi/perguntas`;
- health e verificação de funcionamento;
- correlação operacional;
- normalização defensiva;
- fallback governado;
- validação explícita de `GOVBI_BASE_URL`;
- bloqueio de hosts Fly.io/fly.dev;
- testes de sucesso, erro de negócio, fallback e configuração;
- frontend consumindo `/govbi/perguntas` pelo serviço central;
- histórico, métricas, filtros e evidência operacional na UI.

## Decisão

Não restaurar os quatro arquivos históricos do PR #91 sobre a `main`, pois isso removeria evoluções posteriores de segurança, observabilidade, UX e a aposentadoria permanente do Fly.io.

## Preservação do trabalho

O incremento original — retirar a chamada direta do navegador ao provider externo e inserir um proxy governado no backend — permanece ativo na arquitetura canônica.

## Critério de conclusão

- branch sincronizada com a `main`;
- nenhuma implementação atual substituída por versão histórica;
- `behind_by=0`;
- PR sem conflitos;
- gates obrigatórios verdes no HEAD reconciliado.
