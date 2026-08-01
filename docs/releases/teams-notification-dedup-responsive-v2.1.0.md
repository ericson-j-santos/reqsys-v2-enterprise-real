# Teams Notifications v2.1 — deduplicação e layout responsivo

## Estado evidenciado

- Dois workflows reagiam ao mesmo `push` em `main`:
  - `teams-commit-notification.yml`, com Adaptive Card;
  - `notify-teams-repo-changes.yml`, com mensagem textual legada.
- O blueprint do flow permitia executar a regra de fallback mesmo após o cartão adaptável ter sido publicado.
- O template genérico utilizava `FactSet`, que comprime rótulos e valores longos no Teams mobile.

## Correção

1. `teams-commit-notification.yml` passa a ser a única origem de notificações de commit.
2. O workflow legado `notify-teams-repo-changes.yml` foi removido.
3. O flow v2 mantém a invariável `exactly_one_post_per_request`:
   - cartão por objeto;
   - cartão por JSON quando o objeto não existir;
   - texto somente quando nenhum cartão foi entregue e o fallback estiver habilitado.
4. O fallback pode ser suprimido por `suppressFallbackMessage=true`.
5. A idempotência usa `deduplicationKey` e, na ausência, `correlationId`.
6. O template genérico foi alterado para largura total, campos empilhados e quebra de linha, sem `FactSet`.
7. Após merge em `main`, o workflow `Teams v2 Adaptive Card Update` aplica a alteração no ambiente `reqsys-power-platform-dev`, preservando backup e artifact de evidência.

## Validação

- Testes de contrato do gerador da solution.
- Testes do modificador de `clientdata` do Power Automate.
- Teste antirregressão que impede a recriação do workflow legado.
- Evidência operacional no artifact `teams-v2-card-update-<run_id>`.

## Risco e rollback

- Escopo de aplicação automática limitado ao environment `reqsys-power-platform-dev`.
- O workflow salva o `clientdata` anterior antes do PATCH.
- Rollback: restaurar o backup do artifact e reexecutar o atualizador em modo governado.

`production_touched=false`
