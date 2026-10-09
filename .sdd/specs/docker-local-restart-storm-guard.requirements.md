# Requisitos — proteção contra tempestades de reinício Docker local

## Objetivo

Conter loops de reinício em ambientes locais sem remover containers ou volumes e sem
reduzir silenciosamente as proteções necessárias a produção.

## Critérios de aceite

1. O Compose base DEVE usar uma política que não reinicie indefinidamente serviços DEV/test.
2. O overlay de produção DEVE limitar a recuperação automática de falhas consecutivas.
3. Entrypoints de subida e reinício DEVEM executar preflight e falhar antes de iniciar a
   stack quando arquivos, Dockerfiles, configuração nginx ou daemon estiverem inválidos.
4. A auditoria local DEVE detectar loops históricos, containers unhealthy, binds inválidos
   e políticas persistentes inadequadas sem persistir conteúdo bruto potencialmente sensível.
5. O agendamento automático DEVE ser opt-in e não exigir privilégio elevado por padrão.
6. Testes regressivos DEVEM provar as políticas, os preflights e os guardrails destrutivos.
7. Nenhum teste DEVE remover containers, volumes ou executar deploy/promoção de ambiente.

## Rollback

Reverter o PR restaura as políticas e scripts anteriores. A evidência histórica permanece
imutável para auditoria; qualquer reativação de restart persistente deve ser deliberada.
