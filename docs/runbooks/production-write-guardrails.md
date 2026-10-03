# Guardrails de Escrita em Produção

> Atualização: 2026-06-30 13:30 BRT  
> Escopo: política de segurança sem alteração de código executável.

## Objetivo

Consolidar regras mínimas para impedir que incrementos automatizados, agentes, conectores ou rotinas operacionais realizem escrita em produção sem autorização, rastreabilidade e rollback.

## Princípios

1. Produção é `read-first`: validar estado antes de qualquer mutação.
2. Escrita em produção exige confirmação humana explícita quando houver impacto operacional.
3. Toda ação mutável deve possuir `correlation_id`, ator, motivo, escopo e rollback.
4. Secrets, tokens e credenciais nunca devem ser exibidos em logs, PRs ou artefatos.
5. Alterações destrutivas devem passar por dupla confirmação e janela operacional.

## Matriz de autorização

| Ação | Ambiente DEV | Ambiente TEST | Ambiente PROD |
| --- | --- | --- | --- |
| Leitura de health/status | Permitida | Permitida | Permitida |
| Geração de evidência | Permitida | Permitida | Permitida sem PII |
| Escrita idempotente | Permitida | Permitida com log | Requer aprovação |
| Alteração de configuração | Permitida com PR | Permitida com PR | Requer PR, CI verde e aprovação |
| Operação destrutiva | Restrita | Restrita | Bloqueada por padrão |

## Checklist obrigatório

- [ ] Existe `correlation_id` rastreável.
- [ ] A ação é reversível ou possui plano de rollback.
- [ ] O impacto em dados, autenticação, integração e disponibilidade foi classificado.
- [ ] Nenhum segredo ou PII foi exposto.
- [ ] O CI está verde para alterações versionadas.
- [ ] A aprovação humana está registrada quando PROD é impactado.

## O que não deve ser feito

- Executar escrita direta em produção a partir de agente sem confirmação humana.
- Registrar payloads sensíveis sem mascaramento.
- Usar token pessoal em documentação, artifact ou log.
- Alterar workflows de deploy junto com mudanças funcionais de alto risco.
- Fazer rollback manual sem registrar evidência.

## Rollback

Remover este documento. Não há alteração de runtime, banco, workflows, secrets ou infraestrutura.
