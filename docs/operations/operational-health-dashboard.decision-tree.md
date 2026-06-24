# Decision Tree — Operational Health Dashboard

```text
PR aberto
├─ Está duplicado ou superseded?
│  └─ Sim: fechar com justificativa
├─ Está em draft?
│  └─ Sim: classificar como experimental
├─ CI está vermelho?
│  └─ Sim: classificar como blocked
├─ Está com conflito?
│  └─ Sim: recriar branch limpa ou corrigir
├─ É documentação/governança?
│  └─ Sim: classificar como governance-only
└─ Caso contrário: validar como production-ready
```

## Decisão recomendada

Usar o decision tree antes de qualquer merge acelerado.
