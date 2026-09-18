# Instruções permanentes de aceite — ReqSys

Para qualquer funcionalidade, incremento, ambiente ou correção deste repositório, **não declarar 100%, concluído operacionalmente, padrão ouro ou aceito** apenas porque CI, testes automatizados, cobertura, build, smoke ou `/health` passaram.

O critério obrigatório é cumulativo:

```text
testes automatizados passaram
        +
deploy real passou
        +
browser real sem mocks passou
        +
integrações externas reais passaram
        +
efeito de negócio foi comprovado
        ↓
      100% aceito
```

Regras:

- mocks são permitidos em testes unitários e de interface, mas nunca podem contar como evidência de browser real, integração externa real ou efeito de negócio;
- browser real deve apontar para o ambiente efetivamente publicado e não pode interceptar/substituir as APIs da jornada validada;
- integrações devem usar os serviços externos reais da jornada;
- o efeito de negócio deve ser observado no destino final esperado, com evidência rastreável;
- qualquer camada ausente, simulada, sem evidência ou desatualizada mantém o estado `quality_blocked`;
- `100%`, `concluído`, `aceito` ou equivalente só podem ser informados quando `scripts/user_journey_acceptance_gate.py` retornar `accepted=true` e `one_hundred_percent_allowed=true`;
- separar sempre em relatórios: qualidade técnica, publicação real e aceite da jornada do usuário.

Política executável: `config/user-journey-acceptance-policy.json`.
Runbook: `docs/governance/aceite-jornada-real.md`.
