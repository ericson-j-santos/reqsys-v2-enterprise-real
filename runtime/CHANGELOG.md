# Changelog do Runtime

## 0.7.1 - Recuperação de jobs órfãos

- adiciona recuperação atômica de jobs deixados na fila Redis de processamento;
- executa a recuperação antes do início do consumo pelo worker;
- adiciona testes de idempotência e ordem de inicialização.
