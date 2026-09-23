# Requisitos — Report Builder Email Delivery

Issue: #2027  
Increment type: `gap_fix`

## Objetivo

Permitir que a própria aplicação ReqSys gere um relatório paginado e envie o artefato RDL por e-mail, reutilizando o provedor governado já existente no runtime, sem uso de um cliente de e-mail externo ao aplicativo.

## Requisitos funcionais

1. Expor `POST /v1/report-builder/reports/generate-and-email`.
2. Exigir autorização `report_builder:send`.
3. Reutilizar o gerador paginado existente da aplicação e manter todos os guardrails de SQL somente leitura e segredo inline.
4. Aceitar de 1 a 20 destinatários válidos, removendo duplicatas sem alterar a ordem.
5. Rejeitar assunto com CR/LF para impedir injeção de cabeçalho.
6. Em `dry_run=true`, gerar RDL/MIME e metadados sem criar sender nem executar escrita externa.
7. Em `dry_run=false`, enviar via Microsoft Graph ou SMTP conforme configuração governada já existente.
8. Anexar exatamente um arquivo `<report_name>.rdl`.
9. Incluir `X-Correlation-ID` e `X-Report-SHA256` na mensagem.
10. Não retornar token, senha, client secret ou conteúdo de credencial na resposta/log.
11. O envio real só pode ser declarado concluído após sucesso do provedor e evidência independente de entrega ao destinatário.

## Critérios de aceite

- teste positivo de dry-run comprova geração sem chamada externa;
- teste positivo de envio usa sender controlado e comprova anexo RDL, correlation_id e SHA-256;
- teste pela rota FastAPI comprova o fluxo da aplicação;
- controles negativos rejeitam destinatário inválido e SQL destrutivo;
- o E2E real usa o destinatário autorizado `ericson.takay@gmail.com` e mantém o estado parcial enquanto a entrega independente não for observada.
