## Objetivo

Descreva o objetivo da alteração.

## Escopo

- 

## Fora de escopo

- 

## Ambiente afetado

- [ ] Desenvolvimento
- [ ] Homologação
- [ ] Produção
- [ ] Não altera runtime

## Tipo de mudança

- [ ] Funcionalidade
- [ ] Correção
- [ ] Documentação
- [ ] Segurança
- [ ] Observabilidade
- [ ] Analytics / drill-down
- [ ] Arquitetura viva
- [ ] CI/CD

## Checklist padrão ouro

- [ ] Requisito ou motivação registrado.
- [ ] Critérios de aceite definidos.
- [ ] Branch segue convenção.
- [ ] ADR criado/atualizado quando aplicável.
- [ ] Documentação atualizada.
- [ ] CHANGELOG atualizado quando aplicável.
- [ ] Testes executados ou justificativa registrada.
- [ ] CI validado.
- [ ] Segurança revisada.
- [ ] Logs não expõem token, senha, CPF, PII ou connection string.
- [ ] `correlation_id` preservado quando aplicável.
- [ ] Analytics/drill-down avaliado quando aplicável.
- [ ] Rollback ou mitigação descrito quando houver risco operacional.

## Evidências

```text
Comandos executados:

Resultado:

Links/evidências:
```

## Segurança e governança

- Auth foi alterada? `sim/não`
- CORS foi alterado? `sim/não`
- JWT/claims/secrets foram alterados? `sim/não`
- Dados sensíveis foram manipulados? `sim/não`
- Há impacto LGPD? `sim/não`

## Observabilidade

- Logs estruturados: `sim/não/não aplicável`
- Métricas: `sim/não/não aplicável`
- Tracing/correlation_id: `sim/não/não aplicável`

## Plano de rollback

Descreva como reverter ou mitigar a alteração.

## Observações

Inclua restrições, pendências ou validações não realizadas.
