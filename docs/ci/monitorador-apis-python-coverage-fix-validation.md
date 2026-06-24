# Checklist de validação — Coverage Fix

## Obrigatório antes do merge

- [ ] `Testes Monitorador APIs Python` concluído com sucesso.
- [ ] Cobertura mínima de 85% preservada.
- [ ] Sem chamadas externas reais durante testes.
- [ ] Sem alteração de deploy.
- [ ] Sem alteração em secrets, branch protection ou ambientes.

## Evidência esperada

- Link do workflow verde no PR.
- Confirmação da etapa `Executar testes com cobertura mínima`.
