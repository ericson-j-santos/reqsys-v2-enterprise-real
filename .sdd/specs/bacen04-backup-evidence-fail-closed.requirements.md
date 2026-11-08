# BACEN-04 — contrato de evidência de recuperação sem falso sucesso

## Objetivo

Corrigir o avaliador de evidências do backup legado para impedir que entradas incompletas ou inválidas sejam interpretadas como recuperação válida. Não reativar a rota aposentada do Fly.io.

## Requisitos

1. Datas de ponto de recuperação e conclusão da restauração devem conter fuso horário, ser válidas e ocorrer em ordem cronológica.
2. Ausência de `generated_at`, data inválida, data futura ou sem fuso deve retornar `rpo_minutes: null` e `result: failed`, nunca RPO igual a zero.
3. A integridade exige SHA-256 válido de 64 caracteres hexadecimais na origem, hash igual na restauração, `quick_check=ok` e mapa de contagens.
4. RTO negativo, infinito ou NaN deve resultar em `rto_seconds: null` e `result: failed`.
5. Quota diferente de `healthy` ou sem medições inteiras e não negativas (`total_size_bytes`, `warn_bytes`, `hard_bytes`) e ordenadas por `0 <= total < warn < hard` deve impedir a declaração de recuperação aprovada. Estatísticas Restic inválidas, negativas ou booleanas devem falhar antes da produção de evidência.
6. Preservar testes positivos de evidência válida e incluir testes negativos determinísticos, sem acessar banco real, armazenamento externo ou segredos.
7. A prova de CI demonstra somente contrato; não demonstra RPO/RTO operacional, criptografia Restic ou restauração fora da origem.
8. Não modificar política de promoção: STG exige evidência real DEV e PROD exige evidência real STG e autorização própria.
9. Código legado e inventário Fly/SQLite permanecem inativos; inventário de PostgreSQL atual exige diagnóstico governado de host e novo incremento aprovado.
10. Custo adicional máximo R$ 0,00, sem Docker, alteração de PROD, criação de bucket ou aumento de quota.

## Critérios de aceite

- Cenário positivo: manifesto de origem com timestamp UTC, SHA válido, contagens equivalentes, RTO dentro do limite e quota saudável devolve `result=passed`.
- Cenários negativos: timestamp ausente, malformado, sem fuso ou futuro, hash ausente, RTO inválido, quota em warning ou quotas rotuladas healthy sem métricas íntegras devolvem `result=failed`; Restic rejeita tamanhos inválidos.
- Sintaxe Python, testes de regressão e SDD gate obrigatórios devem passar na branch no SHA atual.
- A árvore de execução deve permanecer separada da `main`, sem PR antes de `READY_FOR_PR=passed`.
- DEV/STG reais: apenas após origem e destino identificados, prova de custo zero, captura criptografada, restauração isolada e leitura independente; sem isso, o estado BACEN-04 permanece bloqueado.
- PROD: nenhuma execução nem habilitação nesta entrega.

## Extensão 07/11/2026 — dashboard BACEN-04 da Issue #1162

A Issue #1162 é gerada periodicamente por `scripts/reqsys_free_tier_backup.py::markdown` e permanece de autoria `User`. O conteúdo histórico da tabela de backup não trazia as 12 seções de rastreabilidade, razão da falha determinante em `Issue Governance Validator` (run 42387863261, SHA 451f9da9bcc306501c7d00e649956bb765df84b9).

Requisitos adicionais:

1. Preservar tabela, URL da execução, medição de configuração, limite de quota e estados individuais dos ativos.
2. Produzir as 12 seções de governança exigidas para issue humana, mantendo descrição, situação observada, esperado, causa ainda não determinada, critérios verificáveis, riscos, dependências, evidências, PRs ainda não vinculadas, responsável, prioridade P1 e declaração de rastreabilidade marcada.
3. Não usar o marcador de exceção `<!-- reqsys-operational-panel -->` para uma Issue de autoria humana; não reduzir o rigor do validador.
4. Não transformar valores desconhecidos, `rollout_pending`, ausência de armazenamento externo ou falta de restauração real em evidência de sucesso.
5. Não reativar Fly.io, backup legado, PROD, operações externas, publicação automática nem custos incrementais.

### Critérios de aceite desta extensão

- Teste de regressão em `tests/test_reqsys_free_tier_backup.py` exige `validate_issue(..., author_type="User")` válido com 13 campos verificados e rejeita a exceção de bot.
- Cenário sem armazenamento configurado continua exibindo `false` e `rollout_pending`; a declaração assinala expressamente que não certifica backup nem restauração não comprovados.
- O `Pre-PR Readiness Gate` verifica sintaxe, Ruff, testes, SDD e demais invariantes no HEAD exato; a PR é proibida sem `READY_FOR_PR=passed`.
- O E2E real de backup DEV/STG, a restauração isolada e a operação PROD não são parte desta mudança e continuam dependentes de evidência independente e autorização específica.
