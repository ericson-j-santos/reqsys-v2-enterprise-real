# Implementação — promoção automática Fly por evidências

Data: 2026-07-31

## Estado anterior

O `Fly Enterprise Sync` detectava drift em `push` da `main`, mas exigia `workflow_dispatch` para implantação. As capturas de runtime, publicação e login existiam de forma dispersa e não formavam uma decisão única de promoção.

## Estado implementado

- captura reutilizável e sanitizada do estado Fly por ambiente;
- correlação entre Fly, runtime público, SHA publicado e login;
- decisão fail-closed por ambiente;
- promoção sequencial DEV → STG → PROD;
- implantação apenas quando o ambiente estiver dessincronizado;
- bloqueio de SHA obsoleto;
- verificação estrita pós-deploy;
- produção sujeita ao BACEN Production Hard Gate e ao environment `production` do GitHub;
- reconciliação horária e disparo após validação pós-merge bem-sucedida.

## Limitações preservadas

- a implementação não altera secrets nem permissões de environments;
- nenhum valor de secret é persistido nos artifacts;
- o gate BACEN pode manter produção bloqueada;
- falhas interrompem a cadeia e exigem correção da causa raiz antes de nova tentativa;
- rollback produtivo permanece um fluxo governado separado.

`production_touched=false`
