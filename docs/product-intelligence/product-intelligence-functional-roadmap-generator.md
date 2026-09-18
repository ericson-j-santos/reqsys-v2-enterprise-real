# Product Intelligence Functional Roadmap Generator

## Objetivo

Gerar roadmap funcional governado a partir dos artifacts da camada `ReqSys Product Intelligence Layer`.

## Capacidades implementadas

- Gerador Python sem dependências externas.
- Roadmap funcional determinístico e revisável.
- Consolidação de dashboard, decisão, backlog e gate.
- Fases funcionais com critérios de entrada e saída.
- Relatórios JSON, Markdown e HTML.
- Workflow CI dedicado.
- Artifact de roadmap funcional.

## Fases iniciais

| Fase | Objetivo |
|---|---|
| Refinamento funcional governado | Elevar qualidade, BDD, clareza e prontidão |
| Rastreabilidade funcional viva | Conectar requisito a PRs, testes, decisões e riscos |
| Implementação governada | Preparar implementação com revisão humana e evidências |
| Feedback e aprendizado funcional | Reexecutar analytics funcionais após evolução |

## Governança

- Roadmap em modo review-only.
- Escrita externa desabilitada.
- Execução de agente desabilitada.
- Revisão humana obrigatória.
- Sem alteração de runtime produtivo.

## Limites

- Não cria issues automaticamente.
- Não cria tarefas em Redmine automaticamente.
- Não executa agentes automaticamente.
- Não substitui aprovação humana.
- Não altera gates operacionais existentes.

## Próximo incremento recomendado

Product Intelligence Runtime Readiness Gate.
