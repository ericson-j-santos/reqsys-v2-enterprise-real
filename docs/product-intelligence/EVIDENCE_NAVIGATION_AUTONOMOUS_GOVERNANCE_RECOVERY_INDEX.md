# Product Intelligence Evidence Navigation Autonomous Governance Recovery Index

## Objetivo

Criar um índice de recuperação governada para a cadeia Evidence Navigation, preparando playbooks de remediação quando houver drift, sem executar ações destrutivas ou promover produção automaticamente.

## Escopo

- Geração de índice JSON de recovery.
- Geração de sumário Markdown.
- Validação da cadeia anterior: compliance drift index.
- Upload de bundle de recovery pelo GitHub Actions.

## Política operacional

| Situação | Ação |
|---|---|
| Sem drift | Permanecer em standby |
| Drift detectado | Preparar playbook de recuperação |
| Ação destrutiva | Bloqueada |
| Execução automática | Bloqueada |
| Promoção produtiva | Bloqueada |
| Revisão humana | Obrigatória |

## Guardrails

- Não executa remediação destrutiva.
- Não altera secrets.
- Não altera regras de proteção do repositório.
- Não promove evidência para produção.
- Não faz merge automático por este índice.
- Toda recuperação exige trilha de auditoria e aprovação humana.
