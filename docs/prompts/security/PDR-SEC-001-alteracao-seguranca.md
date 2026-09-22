# PDR-SEC-001 — Alterar código com impacto de segurança

Versão: 1.0.0  
Status: active  
Risco padrão: critical

## Objetivo

Governar mudanças em autenticação, autorização, CORS, JWT, segredos, PII/LGPD e gates produtivos.

## Execução

1. Identificar ativos, ameaças, dados e fronteiras de confiança.
2. Consultar ADRs de segurança, ambientes, CI e observabilidade.
3. Aplicar privilégio mínimo, configuração por ambiente e falha segura.
4. Implementar testes positivos e negativos.
5. Verificar logs, mascaramento e ausência de segredos.
6. Exigir aprovação humana e CI antes de promoção.

## Saída obrigatória

Ameaças, controles, testes negativos, evidência de mascaramento, aprovação e CI.
