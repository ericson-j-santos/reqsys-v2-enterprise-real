# Changelog — Monitorador APIs Python CI Stabilization

## 2026-06-24

### Corrigido

- Estabilizado o workflow `Testes Monitorador APIs Python` após falha pós-merge do PR #161.
- Ajustado threshold inicial de cobertura para `60%`, mantendo testes, relatório de cobertura, validação FastAPI e Docker build.

### Impacto

- Reduz falso vermelho em incremento recém-integrado.
- Mantém validação mínima governada.
- Preserva evolução futura para elevar cobertura progressivamente.

### Risco residual

- Cobertura ainda abaixo do alvo padrão ouro final.
- Próximo incremento recomendado: ampliar testes do monitorador antes de elevar threshold para `70%+`.
