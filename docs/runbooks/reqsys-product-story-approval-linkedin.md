# ReqSys Product Story — Approval Gate e LinkedIn Adapter

## Estado deste incremento

O fluxo de aprovação está implementado em modo seguro de validação. O adapter conhece o contrato oficial da LinkedIn Posts API e possui ledger persistente governado, mas o workflow não executa publicação real.

## Fluxo

```text
Weekly Accomplishment Log
  -> Product Story Engine
  -> selected_for_review
  -> Approval Gate
  -> GitHub Ledger PREPARED
  -> LinkedIn Posts API
  -> GitHub Ledger PUBLISHED
```

No CI desta PR, o caminho externo é substituído por `dry_run`; nenhum post é criado.

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

## Ledger persistente

Fonte: GitHub Issue #1862.

Estados:

- `PREPARED`: reserva criada antes da chamada externa;
- `PUBLISHED`: publicação concluída e `post_id` persistido;
- `RECONCILE_REQUIRED`: o efeito externo pode ter ocorrido e o ledger exige reconciliação antes de qualquer retry.

Regra de idempotência:

1. consultar o issue por `content_hash`;
2. `PUBLISHED` retorna `ALREADY_PUBLISHED`;
3. `PREPARED` ou `RECONCILE_REQUIRED` bloqueiam retry automático;
4. ausência de entrada permite criar reserva `PREPARED`;
5. somente após a reserva o adapter pode chamar o LinkedIn;
6. HTTP 201 captura `x-restli-id`;
7. a mesma entrada é atualizada para `PUBLISHED`.

Esse desenho evita uma segunda publicação mesmo se ocorrer falha entre a chamada externa e a persistência final.

## Fail closed

Publicação real exige simultaneamente:

1. aprovação `human`;
2. confirmação `APPROVE`;
3. `REQSYS_LINKEDIN_PUBLISH_ENABLED=true`;
4. `LINKEDIN_ACCESS_TOKEN`;
5. `GITHUB_TOKEN` com acesso ao ledger;
6. issue #1862 acessível;
7. ausência de reserva/publicação incompatível para o mesmo `content_hash`.

No workflow versionado neste incremento nenhuma credencial LinkedIn é carregada e apenas `--mode dry_run` é usado.

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

Os testes unitários também exercitam o caminho publish com clientes falsos para comprovar reserva persistente, finalização `PUBLISHED` e ausência de segunda chamada LinkedIn.

## Próximo incremento antes de publicação real

- configurar a aplicação LinkedIn e `w_member_social`;
- provisionar o access token em secret store;
- determinar o `author_urn` real;
- validar autenticação e autorização sem publicar;
- só então executar uma publicação real com autorização explícita e específica.
