# 📝 Descrição

[Descreva as mudanças desta PR]

## 🧪 Tipo de Mudança

- [ ] 🐛 Bug fix (não-breaking)
- [ ] ✨ Feature (não-breaking)
- [ ] 🔐 Security update
- [ ] 📚 Documentation
- [ ] 🔧 Configuration

---

# Checklist Governança

## Obrigatório

- [ ] CI validado
- [ ] Ambiente impactado identificado
- [ ] Evidências anexadas
- [ ] Documentação atualizada
- [ ] Changelog atualizado
- [ ] Impacto em segurança avaliado
- [ ] Impacto em analytics avaliado
- [ ] Responsividade validada
- [ ] Rollback conhecido
- [ ] Próximos passos registrados

## Operacional

- [ ] Smoke test executado
- [ ] Logs verificados
- [ ] Monitoramento atualizado
- [ ] Gates aprovados

---

# 🔐 OCR Setup Checklist

<!-- Se esta PR envolve OCR, incluir: -->
<!-- Remova esta seção se NÃO é relacionada a OCR -->

- [ ] Documentação OCR atualizada (`docs/guides/ocr-*.md`)
- [ ] Nenhuma chave de criptografia em código/arquivo (verificar com `git diff`)
- [ ] `.env.example` reflete todas as mudanças
- [ ] Script `scripts/validate-ocr-setup.ps1` testado localmente
- [ ] Referências à arquitetura incluídas (`ocr-secure-review-v2.md`)
- [ ] Sem breaking changes em endpoints OCR (`/v1/ocr/*`)
- [ ] Teste com `.\scripts\validate-ocr-setup.ps1` passou
- [ ] Endpoint `/v1/ocr/readiness` retorna `ready=true`

## Integração governada

- [ ] PR fora de draft somente após estabilização da implementação.
- [ ] Branch atualizada com a `main` (`behind_by=0`).
- [ ] Todos os checks obrigatórios verdes no HEAD atual.
- [ ] Sem conflitos e sem conversas bloqueantes pendentes.
- [ ] Evidências pertencem ao SHA atual; evidência de SHA anterior não autoriza merge.
- [ ] Merge executado somente pela rota governada/autorizada, protegido pelo HEAD esperado.
- [ ] Validação pós-merge prevista quando aplicável.

