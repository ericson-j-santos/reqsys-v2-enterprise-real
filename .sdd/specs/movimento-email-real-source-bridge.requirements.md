# Requisitos — Movimento Email Corporate Source Bridge

## Problema
A camada DEV V2 consulta `movimento_src.*`, porém a alimentação ainda pode depender de `seed_e2e`. Isso não comprova integração com a origem SQL corporativa da #1520.

## Estado esperado
Um worker no PC24x7 lê a origem SQL corporativa em modo somente leitura, carrega a camada `movimento_src` do banco DEV persistente e registra evidência sanitizada, sem expor DSN ou dados pessoais.

## Requisitos funcionais
- RF01: aceitar DSN da origem por variável ou arquivo protegido no host.
- RF02: exigir `Encrypt=yes/mandatory/strict` e rejeitar `TrustServerCertificate=yes` na origem.
- RF03: validar quatro datasets e colunas antes de qualquer escrita.
- RF04: restringir a escrita ao banco cujo nome termine em `Dev`.
- RF05: substituir apenas o recorte `source_tag=CORPORATE_SQL + data_referencia`.
- RF06: executar `dry-run` sem alteração persistida.
- RF07: repetir a mesma carga sem nova escrita quando o fingerprint for idêntico.
- RF08: registrar `correlation_id`, SHA, contagens e hashes sanitizados.
- RF09: nunca escrever na origem corporativa.
- RF10: executar continuamente no runtime PC24x7 com restart automático.

## Critérios de aceite
- Testes de contrato aprovados.
- Dry-run mantém o fingerprint do alvo.
- Apply carrega a camada canônica.
- Repetição retorna `already_present_no_write`.
- Leitura das views V2 observa contagens compatíveis.
- Evidência marca `synthetic=false`.
- Produção não é tocada.
