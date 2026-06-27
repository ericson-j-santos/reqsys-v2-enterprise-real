# Delivery Maturity Snapshot

- Modo: `report_only`
- Impacto runtime: `none`
- Média atual evidenciada: 82.88%
- Média alvo: 98.0%
- Gap médio: 15.12 p.p.
- Maior gap: produção

> Estado atual e alvo são separados. Nenhum status é declarado como consolidado sem evidência explícita.

## Dimensões

| Dimensão | Atual | Alvo | Gap | Semáforo | Confiança | Próxima ação |
| --- | ---: | ---: | ---: | --- | --- | --- |
| técnico | 86.0% | 98.0% | 12.0 p.p. | amarelo | medium | Executar CI completo e ampliar validação automatizada do schema antes de promover o snapshot de report-only para gate informativo. |
| operacional | 88.0% | 98.0% | 10.0 p.p. | amarelo | medium | Conectar histórico real dos artifacts de operação ao snapshot para reduzir inferência manual. |
| usuário final | 74.0% | 95.0% | 21.0 p.p. | vermelho | low | Coletar evidência E2E recente de jornada de usuário e anexar link do artifact antes de elevar confiança. |
| governança | 90.0% | 99.0% | 9.0 p.p. | amarelo | medium | Manter rastreabilidade artifact → contrato → dashboard e registrar exceções de PR draft até estabilização. |
| produção | 70.0% | 98.0% | 28.0 p.p. | vermelho | low | Validar gates produtivos com evidência de ambiente publicado sem alterar runtime produtivo neste incremento. |
| observabilidade | 84.0% | 98.0% | 14.0 p.p. | amarelo | medium | Integrar sinais de correlation_id, incident timeline e runtime health no dashboard dinâmico com histórico. |
| segurança | 82.0% | 99.0% | 17.0 p.p. | amarelo | medium | Anexar evidências recentes de ruff, pip-audit, bandit, npm audit e gates JWT/CORS antes de qualquer declaração consolidada. |
| evidência | 89.0% | 99.0% | 10.0 p.p. | amarelo | medium | Publicar o artifact delivery-maturity-snapshot e referenciar execução real no índice de evidências. |
