# ReqSys — Incremento de Relatorio Executivo MIME HTML v1

## Objetivo

Garantir que relatorios executivos enviados por e-mail preservem layout visual com cards, cores de status, bordas, tabelas e semaforo operacional em clientes compativeis com HTML.

## Problema observado

O envio simples via conector de e-mail pode tratar HTML como texto puro. Nesse caso, tags, CSS e cores nao sao renderizados como layout visual.

## Decisao tecnica

Implementar montagem de mensagem `MIME multipart/alternative` no backend, contendo:

- parte `text/plain` como fallback compativel;
- parte `text/html` com CSS inline;
- headers auditaveis:
  - `X-Correlation-ID`;
  - `X-ReqSys-Report-Type`.

## Arquivos implementados

- `backend/app/services/email_mime_report_service.py`
- `backend/tests/test_email_mime_report_service.py`

## Validacoes automatizadas

Os testes validam:

| Validacao | Resultado esperado |
|---|---|
| HTML contem cores inline | PASS |
| HTML contem `correlation_id` | PASS |
| Texto fallback nao contem HTML | PASS |
| Mensagem e multipart | PASS |
| Partes MIME estao em ordem correta | `text/plain`, `text/html` |
| Headers auditaveis presentes | PASS |

## Criterios de aceite

- [x] Criar builder MIME HTML reutilizavel.
- [x] Preservar fallback texto.
- [x] Preservar CSS inline.
- [x] Incluir `correlation_id` no header e corpo.
- [x] Testar sem envio real.
- [ ] Integrar com provedor SMTP/Gmail API/Power Automate em ambiente com secrets.
- [ ] Executar envio E2E real com evidência de renderizacao.

## Proxima acao recomendada

Integrar o builder a um gateway real de envio, por exemplo:

1. SMTP corporativo com TLS;
2. Gmail API com MIME raw;
3. Microsoft Graph/Outlook;
4. Power Automate com HTML preservado;
5. endpoint interno ReqSys `/v1/relatorios/executivo/email`.

## Observabilidade

Cada envio deve registrar:

- `correlation_id`;
- destinatarios mascarados em log;
- provedor utilizado;
- status de entrega;
- message id retornado pelo provedor;
- erro tecnico, quando houver, sem vazar segredo.
