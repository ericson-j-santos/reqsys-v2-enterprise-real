# Gerador — Fluxo de criação de dossiê (Pentaho)

## Objetivo

Distribuir, a partir do código versionado em `tools/gerador_pentaho/pacote/`,
uma aplicação de treinamento que reproduz — com dados exclusivamente
sintéticos — um fluxo de criação de dossiê: autenticar, criar dossiê,
validar a resposta e produzir evidências operacionais. O mesmo comportamento
é expresso tanto em Node.js (`src/`) quanto como job/transformações Pentaho
Data Integration 7.1+ (`pentaho/*.kjb`/`*.ktr`).

## Origem

Extraído em 2026-08-10 a partir da imagem de um fluxo observado, com
substituição integral de qualquer informação potencialmente sensível.
Nenhum endpoint, segredo, identificador pessoal ou nome de sistema interno
real foi reaproveitado — ver varredura de segredos em
`tests/test_gerador_pentaho.py::test_pacote_nao_contem_segredo_real` e o
histórico completo em `tools/gerador_pentaho/pacote/CHANGELOG.md`.

Até a versão 1.1.0 do script original (`gerador_solucao_completa_v2.1.0.py`,
mantido fora do controle de versão) a aplicação inteira era embarcada como
um blob base64 dentro do próprio `.py`, validada contra um SHA-256 fixo.
Essa versão trouxe o conteúdo para dentro do repositório como arquivos reais
em `tools/gerador_pentaho/pacote/` — revisável em PR, diffável, testável —
e reduziu o script a um empacotador (`gerador_solucao_completa.py`) que gera
um diretório e, opcionalmente, um ZIP portátil a partir dessa fonte.

## Como gerar

```bash
python tools/gerador_pentaho/gerador_solucao_completa.py --dry-run
python tools/gerador_pentaho/gerador_solucao_completa.py --output /tmp/dossie-pentaho --force --run-tests
```

Ver `tools/gerador_pentaho/README.md` para todas as opções e
`tools/gerador_pentaho/pacote/README.md` para como executar a aplicação
gerada (Node.js e Pentaho Data Integration).

## Testes aplicados

- `tests/test_gerador_pentaho.py` (pytest, 7 casos): listagem do pacote,
  geração de diretório idêntica byte a byte à fonte, falha esperada sem
  `--force` em destino existente, sobrescrita com `--force`, geração de ZIP
  com prefixo e conteúdo corretos, e ausência de termos de segredo no
  pacote.
- `tools/gerador_pentaho/pacote/testes/fluxo.test.js` (`node --test`, 8
  casos) — executado tanto localmente quanto pelo próprio CLI via
  `--run-tests`. Ver análise de Pareto abaixo.

Validado em CI por
`.github/workflows/gerador-pentaho-dossie-validation.yml` a cada alteração
em `tools/gerador_pentaho/**` ou neste documento.

## Pareto aplicado à cobertura de `fluxo.test.js` (2026-09-03)

Cobertura inicial (2 casos) exercitava só 2 dos 5 estados finais do fluxo
(`DOSSIÊ_CRIADO`, `CRIAÇÃO_RECUSADA`) e nenhum dos critérios de aceite de
retentativa/timeout já escritos em
`tools/gerador_pentaho/pacote/docs/mapeamento-pentaho.md`. Priorização: o
maior risco de regressão silenciosa concentrado no menor número de casos —
comportamento documentado como obrigatório, com lógica não trivial
(`chamar()` tem loop com `continue`/`throw` condicionais) e cobertura zero.

| Prioridade | Lacuna (0% de cobertura antes) | Por que entra no Pareto |
| --- | --- | --- |
| 1 | 5xx persistente esgota `MAX_TENTATIVAS` e não insiste além do limite | Critério de aceite escrito ("5xx/timeout respeita limite"); loop com estado (`tentativa`) é o trecho de lógica mais fácil de quebrar num refactor |
| 2 | Erro 4xx não é retentado automaticamente | Critério de aceite escrito ("erro HTTP 4xx não é repetido automaticamente"); inverso do caso acima, mesmo trecho de código |
| 3 | Retentativa em 5xx intermitente sucede antes de esgotar tentativas | Metade do contrato de retentativa (a outra metade é o esgotamento); sem isso, um bug que retenta 4xx ou nunca retenta 5xx passaria despercebido |
| 4 | `AUTENTICAÇÃO_RECUSADA` | Estado final documentado, 0 testes; único caminho antes só alcançável manualmente |
| 5 | `RESPOSTA_INVÁLIDA` | Estado final documentado, 0 testes; alcançado naturalmente pelo mesmo teste de esgotamento de 5xx (prioridade 1) — 1 teste, 2 lacunas fechadas |
| 6 | `FALHA_TÉCNICA` por campo obrigatório ausente | Falha antes de qualquer chamada de rede; teste puro, sem servidor, custo mínimo |
| 7 | `FALHA_TÉCNICA` por indisponibilidade (conexão recusada) | Estado final documentado; caminho operacional real (serviço fora do ar) |

Fora do corte por ora (menor retorno por esforço): variações de payload
inválido em `/oauth/token` além de `access_token` ausente, timeout por
lentidão real (vs. conexão recusada — mesmo branch de código, custo maior
para simular de forma não-flaky em CI), e idempotência ponta a ponta (o
mock não deduplica; o cálculo da chave SHA-256 já é determinístico e não
demonstrou bug).

## Bug encontrado e corrigido durante esta expansão

`node --test testes/fluxo.test.js` executado diretamente dentro do
repositório (fora de um diretório gerado por `--output`) falhava com
`ReferenceError: require is not defined in ES module scope` — a raiz do
monorepo declara `"type": "module"` em `package.json`, herdado por qualquer
`.js` sem um `package.json` mais próximo. Isso nunca apareceu no CI porque
`gerador-pentaho-dossie-validation.yml` só roda os testes via
`--output`+`--run-tests` do CLI, que copia os arquivos para fora da árvore
do repositório antes de testar. Corrigido com
`tools/gerador_pentaho/pacote/package.json` (`"type": "commonjs"`), que
também torna a aplicação gerada mais correta como pacote Node.js portátil.

## Decisão técnica

- **Fonte de verdade versionada, não blob binário.** Diffável em PR,
  revisável linha a linha, sem depender de decodificar base64 para auditar
  conteúdo (ADR-012 — documentação viva).
- **Dados exclusivamente sintéticos** (ADR-002/LGPD): `.env.example` não
  contém segredo real; `CLIENT_SECRET` é sempre injetado em runtime.
- **CLI no mesmo padrão dos demais geradores do repositório**
  (`--dry-run`/`--output`/`--force`/`--run-tests`, ver
  `tools/geradores/gerar_servicos_email_teams.py`), para reduzir a
  superfície de convenções que quem mantém o repositório precisa conhecer.
