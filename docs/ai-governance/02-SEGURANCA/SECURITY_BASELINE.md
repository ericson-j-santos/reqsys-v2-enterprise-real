# Security Baseline

Codigo: AI-GOV-SEC-001

## Regras obrigatorias

- Atender LGPD, minimizacao de dados e finalidade explicita no tratamento.
- Proteger credenciais e dados sensiveis.
- Evitar registro de dados pessoais ou credenciais em logs.
- Validar autenticacao e autorizacao por ambiente.
- Restringir origens de acesso conforme ambiente.
- Aplicar menor privilegio.
- Exigir correlation_id em auditoria.
- Separar configuracoes por ambiente.
- Aplicar governanca LGPD para dados pessoais, dados sensiveis, evidencias operacionais, logs, auditoria e relatorios executivos.
- Mascarar ou anonimizar CPF, e-mail, telefone, nome de cliente, tokens, credenciais e connection strings quando exibidos em logs, telas, artifacts ou relatorios.
- Bloquear promocao para producao quando houver risco de exposicao de PII, ausencia de rastreabilidade, ausencia de base legal ou ausencia de evidencia de controle.

## Bloqueios

Producao deve ser bloqueada quando houver configuracao insegura ou ausencia de validacao critica.

Tambem deve ser bloqueada quando qualquer gate LGPD identificar:

- log com PII sem mascaramento;
- artifact contendo credenciais, tokens ou connection strings;
- relatorio operacional com dado pessoal nao anonimizado;
- auditoria sem correlation_id;
- acesso administrativo sem autenticacao e autorizacao validas;
- integracao que exponha dado sensivel sem controle de ambiente.

## Evidencias minimas

- Registro de correlation_id ponta a ponta.
- Validacao de autenticacao e autorizacao.
- Evidencia de mascaramento de PII.
- Registro de ambiente alvo: desenvolvimento, homologacao ou producao.
- Checklist de rollback para mudancas com impacto operacional.

## Referencias cruzadas

- docs/ai-governance/00_PRIORITY_RULES.md
- docs/ai-governance/06-DEVOPS/QUALITY_GATES.md
- ReqSys: login, APIs, integracoes e pipelines.
