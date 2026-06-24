# Security Policy

## Regras P0

Este gateway não deve operar em produção se qualquer condição abaixo for verdadeira:

- autenticação desligada;
- CORS com wildcard;
- logs contendo token, senha, CPF, PII ou connection string;
- auditoria sem `correlation_id`;
- connector/admin exposto sem RBAC;
- resposta de IA sem fonte quando fonte for obrigatória;
- secrets em arquivos versionados.

## Comunicação de vulnerabilidades

Registrar vulnerabilidades como issue privada ou canal corporativo seguro. Não abrir detalhes sensíveis em issue pública.

## Evidência mínima

Toda execução governada deve produzir:

- ambiente;
- `correlation_id`;
- decisão operacional;
- status de guardrails;
- timestamp UTC.
