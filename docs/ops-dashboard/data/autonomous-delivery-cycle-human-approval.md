# Política de aprovação humana — Autonomous Delivery Cycle

## Regra central

A automação só executa merge quando houver autorização explícita por label:

- `cycle:auto-merge-approved`

Essa label representa aprovação humana ou decisão governada externa para permitir que o ciclo avalie e, se tudo estiver verde, execute o merge.

## Responsabilidade da label

Aplicar a label somente quando:

- PR é pequeno;
- PR é de baixo risco;
- PR está verde;
- PR não altera contratos críticos sem revisão;
- PR já passou pela fila governada;
- não há bloqueio operacional em `main`.

## Remoção da label

Remover imediatamente se:

- aparecer falha de CI;
- surgir conflito;
- o escopo aumentar;
- houver comentário de revisão pendente;
- o PR tocar segurança, autenticação, dados sensíveis ou produção.
