# BACEN-04 — contrato de evidência de recuperação sem falso sucesso

## Objetivo

Corrigir o avaliador de evidências do backup legado para impedir que entradas incompletas ou inválidas sejam interpretadas como recuperação válida. Não reativar a rota aposentada do Fly.io.

## Requisitos

1. Datas de ponto de recuperação e conclusão da restauração devem conter fuso horário, ser válidas e ocorrer em ordem cronológica.
2. Ausência de `generated_at`, data inválida, data futura ou sem fuso deve retornar `rpo_minutes: null` e `result: failed`, nunca RPO igual a zero.
3. A integridade exige SHA-256 válido de 64 caracteres hexadecimais na origem, hash igual na restauração, `quick_check=ok` e mapa de contagens.
4. RTO negativo, infinito ou NaN deve resultar em `rto_seconds: null` e `result: failed`.
5. Quota diferente de `healthy` deve impedir a declaração de recuperação aprovada.
6. Preservar testes positivos de evidência válida e incluir testes negativos determinísticos, sem acessar banco real, armazenamento externo ou segredos.
7. A prova de CI demonstra somente contrato; não demonstra RPO/RTO operacional, criptografia Restic ou restauração fora da origem.
8. Não modificar política de promoção: STG exige evidência real DEV e PROD exige evidência real STG e autorização própria.
9. Código legado e inventário Fly/SQLite permanecem inativos; inventário de PostgreSQL atual exige diagnóstico governado de host e novo incremento aprovado.
10. Custo adicional máximo R$ 0,00, sem Docker, alteração de PROD, criação de bucket ou aumento de quota.

## Critérios de aceite

- Cenário positivo: manifesto de origem com timestamp UTC, SHA válido, contagens equivalentes, RTO dentro do limite e quota saudável devolve `result=passed`.
- Cenários negativos: timestamp ausente, malformado, sem fuso ou futuro, hash ausente, RTO inválido e quota em warning devolvem `result=failed`.
- Sintaxe Python, testes de regressão e SDD gate obrigatórios devem passar na branch no SHA atual.
- A árvore de execução deve permanecer separada da `main`, sem PR antes de `READY_FOR_PR=passed`.
- DEV/STG reais: apenas após origem e destino identificados, prova de custo zero, captura criptografada, restauração isolada e leitura independente; sem isso, o estado BACEN-04 permanece bloqueado.
- PROD: nenhuma execução nem habilitação nesta entrega.
