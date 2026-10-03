# Versão Mínima Controlada

Contrato de emissão governada para artefatos do ReqSys.

## Objetivo

Permitir a emissão de uma versão utilizável antes do nível Padrão Ouro, sem abrir mão dos controles mínimos não negociáveis.

## Estados

- `EXPERIMENTAL`: versão gerada, ainda não aprovada para emissão controlada.
- `MINIMUM_CONTROLLED`: controles mínimos obrigatórios aprovados.
- `OPERATIONAL`: controles operacionais e evidências de ambiente aprovados.
- `GOLD_STANDARD`: controles aplicáveis completos aprovados.

## Controles mínimos obrigatórios

1. versionamento identificável;
2. manifesto de artefatos e SHA-256;
3. configuração por ambiente sem segredos no código;
4. validação de entrada;
5. tratamento de erros;
6. logs estruturados;
7. `correlation_id` quando houver fluxo distribuído ou requisição;
8. testes mínimos automatizados;
9. verificação de segredos;
10. CI aprovado;
11. changelog;
12. instrução de execução;
13. rollback definido;
14. evidência de execução dos controles.

## Controles contextuais

Controles contextuais devem ser classificados como `PASS`, `FAIL` ou `NOT_APPLICABLE`, com justificativa. Exemplos: idempotência, retentativas, circuit breaker, fila/quarentena, autenticação/JWT, CORS, migração de banco e smoke test.

## Regra de emissão

Uma versão somente pode receber `maturity=MINIMUM_CONTROLLED` quando todos os controles obrigatórios estiverem `PASS` e nenhum controle contextual aplicável estiver `FAIL`.

O número da versão continua seguindo Versionamento Semântico. O nível de maturidade é metadado separado e não altera `MAJOR.MINOR.PATCH`.
