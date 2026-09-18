## Resumo

### IA responsável

Informe a label principal, por exemplo: ~"ia:runtime".

### Objetivo

Descreva o incremento entregue.

### Escopo

- Arquivo ou módulo 1
- Arquivo ou módulo 2

### Fora do escopo

- Não alterar autenticação sem aprovação
- Não alterar CI global fora de MR de governança
- Não alterar runtime/deploy fora do domínio autorizado

### Evidências

- Pipeline GitLab
- Artifacts
- Testes
- Documentação

### Checklist

- [ ] Pipeline verde
- [ ] Artifact publicado quando obrigatório
- [ ] Sem conflito
- [ ] Escopo pequeno
- [ ] Documentação atualizada
- [ ] Revisão coordenadora
- [ ] Sem segredo/token/PII em logs ou código
