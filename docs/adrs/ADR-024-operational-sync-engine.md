# ADR-024 — Operational Sync Engine v1

## Status

Aceito para PR em draft ate validacao continua verde.

## Contexto

O ReqSys possui PRs, pipelines, agenda operacional, relatórios HTML, artefatos de governança e solicitações recorrentes de monitoramento. O risco principal é a fragmentação: cada canal pode informar um estado diferente e atrasar a próxima ação objetiva.

## Decisão

Implementar o **Operational Sync Engine v1** como capability transversal do Runtime Operational Center.

O incremento estabelece:

- snapshot operacional versionado;
- score de risco por tarefa;
- agenda operacional em três janelas úteis;
- relatório HTML autocontido como retorno obrigatório;
- retorno visual Figma/FigJam quando o conector estiver disponível;
- evidência por `correlation_id`;
- guard rails contra automação produtiva sem aprovação humana.

## Regras

1. GitHub continua sendo a fonte da verdade da execução técnica.
2. ReqSys continua sendo a fonte da verdade da governança e rastreabilidade.
3. Agenda deve ser tratada como janela operacional, não como simples lembrete.
4. O `.html` autocontido deve ser gerado ou atualizado em todo incremento operacional relevante.
5. Figma/FigJam deve ter retorno visual quando houver arquivo/plano disponível; caso contrário, registrar fallback versionado e pendência explícita.
6. Produção não pode ser alterada automaticamente sem aprovação, auditoria e evidência.

## Consequências

- Acompanhamento deixa de ser manual e passa a ter snapshot auditável.
- PRs verdes, falhos e pendentes ficam correlacionados por risco.
- A agenda passa a refletir cadência operacional objetiva.
- A ausência de Figma deixa de ser falha silenciosa e passa a ser pendência rastreável.
