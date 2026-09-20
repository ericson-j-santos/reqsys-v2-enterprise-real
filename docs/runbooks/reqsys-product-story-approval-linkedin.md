# ReqSys Product Story — Approval Gate e LinkedIn Adapter

## Estado deste incremento

O fluxo de aprovação está implementado em modo seguro de validação. O adapter conhece o contrato oficial da LinkedIn Posts API, mas o workflow não executa publicação real.

## Fluxo

```text
Weekly Accomplishment Log
  -> Product Story Engine
  -> selected_for_review
  -> Approval Gate
  -> LinkedIn payload
  -> dry-run evidence
  -> [futuro] publish
```

## Approval Gate

Uma aprovação válida exige:

- candidato `READY_FOR_HUMAN_REVIEW`;
- `selected_for_review=true`;
- `content_hash` exato;
- confirmação literal `APPROVE`;
- `approved_by`;
- `correlation_id`;
- tipo de aprovação `human` ou `test`.

O modo `publish` nunca aceita aprovação `test`.

## Contrato LinkedIn

O adapter usa:

- endpoint: `POST https://api.linkedin.com/rest/posts`;
- `Linkedin-Version: 202609`;
- `X-Restli-Protocol-Version: 2.0.0`;
- `Content-Type: application/json`;
- author URN pessoal ou de organização;
- resposta esperada: HTTP 201;
- identificador do post: header `x-restli-id`.

Para perfil pessoal, a aplicação LinkedIn deverá possuir `w_member_social`.

## Fail closed

Publicação real exige simultaneamente:

1. aprovação `human`;
2. confirmação `APPROVE`;
3. `REQSYS_LINKEDIN_PUBLISH_ENABLED=true`;
4. `LINKEDIN_ACCESS_TOKEN`;
5. ausência de publicação anterior para o mesmo `content_hash` no ledger fornecido.

No workflow versionado neste incremento nenhuma dessas credenciais é carregada e apenas `--mode dry_run` é usado.

## Validação de PR

O workflow `ReqSys Product Story Approval Gate`:

1. baixa o último Weekly Accomplishment Log verde da `main`;
2. regenera candidatos usando o código do SHA atual;
3. executa os testes unitários/contratuais;
4. executa um controle negativo com confirmação `DENY`;
5. executa um Approval Gate positivo em `dry_run`;
6. relê o JSON produzido e confirma independentemente:
   - `DRY_RUN_APPROVED`;
   - `published=false`;
   - endpoint oficial;
   - versão `202609`;
   - protocolo Rest.li `2.0.0`;
7. publica somente artifact de evidência.

## Idempotência

O adapter recebe um ledger JSON e consulta `content_hash` antes da chamada HTTP. Em teste controlado, uma segunda tentativa para hash já publicado retorna `ALREADY_PUBLISHED` sem repetir a chamada de rede.

Esse ledger ainda não é persistido de forma definitiva entre runs; por isso publicação real permanece desabilitada no workflow.

## Próximo incremento antes de publicação real

- escolher mecanismo persistente e auditável para o ledger;
- configurar a aplicação LinkedIn e `w_member_social`;
- provisionar o access token em secret store;
- determinar o `author_urn` real;
- validar autenticação sem publicar;
- executar uma publicação real somente com autorização explícita e específica.
