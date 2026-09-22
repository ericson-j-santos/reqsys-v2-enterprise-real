# Movimento Owner Runtime Feed

## Objetivo

Alimentar automaticamente a fonte `owner_movimento` com dados reais produzidos pelo próprio ambiente ReqSys DEV, sem depender de fonte corporativa externa e sem fabricar semântica de negócio.

## Requisitos

1. Ler apenas `/api/health` e `/api/runtime/health` do runtime local ReqSys.
2. Projetar somente métricas efetivamente presentes nas respostas.
3. Gravar as métricas no dataset `fechamento_diario`.
4. Marcar explicitamente que a captura é operacional DEV e não representa transação comercial.
5. Manter `pendencias_cadastro`, `pendencias_historicas` e `pendencias_observacao` vazios até existir fonte semanticamente compatível.
6. Falhar fechado se qualquer métrica obrigatória estiver ausente.
7. Executar o worker no Noteri, lendo o runtime do Desktop por `http://DESKTOP-PDQK954:8081` e chamando o Owner Gateway local no próprio Noteri.
8. Manter o owner token somente no Noteri; não copiar o token para o Desktop.
9. Reaproveitar a idempotência SHA-256 já existente do owner source.
10. Instalar persistência do worker por `HKCU\\...\\Run`, com intervalo padrão de 900 segundos e sem exigir privilégio administrativo.
11. Não coletar PII.
12. Não tocar PROD.

## Critérios de aceite

1. O projetor produz exatamente 8 indicadores reais do runtime.
2. Nenhum dos três datasets de pendência recebe dados sintéticos.
3. A ingestão owner-managed retorna `applied` ou `noop`.
4. O primeiro sync DEV reflete as linhas ingeridas.
5. O replay do mesmo estado retorna `noop`.
6. Leitura independente confirma igualdade entre fonte e destino para a data.
7. O bootstrap persistente retorna `worker_running=true` e `autostart_registered=true`.
8. Uma execução `--once` do worker no Noteri conclui `status=passed` usando o runtime real do Desktop.
9. Testes direcionados passam integralmente.
10. Pre-PR Readiness passa no HEAD exato com `behind_by=0`.
