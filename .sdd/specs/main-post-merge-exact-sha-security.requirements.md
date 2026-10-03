# Main Post-Merge — segurança no SHA exato

## Objetivo

Fechar a lacuna de evidência em merges automatizados: workflows acionados por `push` podem não ser disparados por uma mutação feita com credencial do próprio GitHub Actions, portanto a validação pós-merge não pode depender apenas de procurar runs externos.

## Requisitos

1. O workflow `Main Post-Merge Validation` deve resolver e fazer checkout do SHA exato de `main` que está validando.
2. O checkout observado deve ser comparado ao `validated_sha`; divergência falha fechado.
3. A validação deve calcular o delta entre o primeiro pai do commit de `main` e o próprio commit validado.
4. O delta deve executar `validate_security_baseline.py --strict --scope changed`.
5. O delta deve executar `vibe_security_gate.py --strict --scope changed` com mapa de linhas adicionadas.
6. O controle negativo interno do Vibe Security Gate deve executar antes do gate real.
7. O mesmo SHA deve gerar snapshot completo `scope=all` sem `--strict`, preservando a dívida histórica como evidência sem convertê-la em falso bloqueio.
8. A política report-only de descoberta de workflows externos permanece; somente a validação de segurança delta local é fail-closed.
9. Os artifacts de pós-merge devem conter os relatórios delta e postura completa dentro de `audit/security-post-merge/`.
10. Nenhum deploy, promoção, segredo ou produção faz parte deste incremento.

## Critérios de aceite

- Pre-PR Readiness verde no HEAD exato e `behind_by=0`;
- testes de contrato comprovam checkout do SHA, delta estrito e snapshot full report-only;
- o workflow preserva `mode: 'report_only'` para descoberta externa;
- um blocker novo no delta faz a etapa de segurança falhar;
- blockers históricos fora do delta permanecem visíveis no snapshot completo, sem quebrar a etapa de postura.
