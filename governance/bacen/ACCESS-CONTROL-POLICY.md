# Política de Controle de Acesso

## Regras obrigatórias

- PROD e STG: autenticação corporativa com tokens assinados, issuer, audience e expiração validados.
- MFA obrigatório para administradores, segurança e operadores de produção.
- Login demo deve permanecer desabilitado fora de DEV/testes isolados.
- Papéis não podem ser derivados de prefixo, domínio ou texto livre do e-mail.
- Menor privilégio e segregação entre desenvolvimento, aprovação e operação.
- Contas técnicas devem ser individuais, inventariadas, rotacionadas e sem login interativo quando aplicável.
- Revisão trimestral de acessos e revisão imediata após desligamento ou mudança de função.
- Toda elevação de privilégio deve gerar evento de auditoria com correlation_id.

## Evidência mínima

Relatório JSON com identidade, papel, origem da concessão, aprovador, data da revisão, resultado e próxima revisão. Dados pessoais devem ser mascarados.

## Bloqueadores de produção

1. autenticação desabilitada;
2. CORS irrestrito;
3. JWT sem validação completa;
4. login demo ativo;
5. privilégio atribuído por convenção textual do e-mail;
6. segredo ou conta compartilhada sem trilha individual.
