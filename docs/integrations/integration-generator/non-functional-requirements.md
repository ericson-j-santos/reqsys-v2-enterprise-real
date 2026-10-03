# Requisitos não funcionais

- Idempotência obrigatória por chave de negócio.
- Rastreabilidade por `correlation_id`.
- Proibição de segredos no perfil ou código.
- Entrada SQL parametrizada em JSON; sem concatenação de identificadores em SQL dinâmico.
- Rejeição/quarentena de identificadores inválidos antes da consulta de negócio.
- Leitura independente do destino após escrita.
- Reprocessamento seguro da mesma entrada.
- Ambientes configurados externamente ao código.
- Erros explícitos e observáveis; nenhuma falha deve ser convertida silenciosamente em sucesso.
