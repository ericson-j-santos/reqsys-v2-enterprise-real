# Definition of Done — promoção automática Fly

- [x] SHA atual da `main` resolvido e imutável durante o estágio.
- [x] execução obsoleta bloqueada.
- [x] captura de configuração, regiões, máquinas, releases e checks.
- [x] captura somente de nomes/estado de secrets.
- [x] smoke público, readiness, publicação e login correlacionados.
- [x] promoção DEV → STG → PROD sequencial.
- [x] deploy omitido quando o ambiente já está sincronizado.
- [x] validação pós-deploy estrita.
- [x] BACEN Production Hard Gate antes de PROD.
- [x] environments GitHub preservados.
- [x] artifacts auditáveis com retenção definida.
- [x] testes de contrato e scripts.
- [ ] CI completo verde no SHA da PR.
- [ ] execução pós-merge real capturada.
