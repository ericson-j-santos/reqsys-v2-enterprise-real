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
- `tools/gerador_pentaho/pacote/testes/fluxo.test.js` (`node --test`, 2
  casos): criação de dossiê com sucesso e recusa de regra de negócio —
  executado tanto localmente quanto pelo próprio CLI via `--run-tests`.

Validado em CI por
`.github/workflows/gerador-pentaho-dossie-validation.yml` a cada alteração
em `tools/gerador_pentaho/**` ou neste documento.

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
