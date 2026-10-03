# Política de Segurança Cibernética — ReqSys

## Objetivo

Estabelecer controles para preservar confidencialidade, integridade, disponibilidade, autenticidade e rastreabilidade dos ativos do ReqSys.

## Escopo

Código, dados, identidades, pipelines, ambientes DEV/STG/PROD, integrações, provedores de nuvem, modelos de IA, logs e evidências operacionais.

## Diretrizes mínimas

1. Produção deve usar autenticação corporativa; login demo e atribuição de privilégio pelo texto do e-mail são proibidos.
2. Acessos seguem menor privilégio, segregação de funções e revisão trimestral.
3. Segredos não podem ser versionados; devem ser obtidos por cofre ou variáveis protegidas.
4. Dados e comunicações devem usar criptografia compatível com o risco.
5. Mudanças passam por PR, revisão, CI, scanners e evidência rastreável.
6. Incidentes devem ser classificados, contidos, registrados e analisados.
7. Serviços críticos devem possuir backup, restauração testada, RPO e RTO.
8. Terceiros devem ser avaliados quanto a segurança, continuidade, localização de dados e subcontratação.
9. Logs devem possuir correlation_id e mascaramento de dados pessoais e segredos.
10. Exceções exigem responsável, justificativa, risco aceito e prazo de expiração.

## Governança

- Responsável técnico: papel `SECURITY`.
- Responsável operacional: papel `RUNTIME_OPERATOR`.
- Aprovação institucional: pendente de designação formal pela administração.
- Revisão: anual ou após incidente relevante, mudança regulatória ou alteração material de arquitetura.

## Evidências

A efetividade deve ser comprovada por artifacts de CI, revisão de acesso, testes de restauração, exercícios de incidente, avaliação de terceiros e relatório anual.

> Este documento é uma base técnica versionada. Não substitui aprovação jurídica, regulatória ou executiva da instituição supervisionada.
