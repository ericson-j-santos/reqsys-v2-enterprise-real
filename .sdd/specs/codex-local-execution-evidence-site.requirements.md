# Codex Local — Central de Execuções (SDD)

## Objetivo e fonte canônica

Fornecer uma interface local de documentação e inspeção somente leitura do desenvolvimento com Ollama/Qwen. Reutilizar a demanda ReqSys [#3126](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/3126) e a dependência Noteri [#42](https://github.com/ericson-j-santos/noteri-runtime/issues/42). Não criar outro ReqSys, TODO Global, ponte de runtime, registro de estado oficial ou autoridade Worker Pool.

## Requisitos

1. Mostrar demanda, issue, correlação, chave idempotente, branch, SHA esperado/confirmado, run_id, hosts, worktree, leases, modelo/digest, Builder/Validator, checkpoint/hash, testes, autorização, custo e efeito no destino.
2. Expor 12 etapas com dependências contínuas; edição de campo obrigatório ou mudança de SHA/lease/custo invalida imediatamente o progresso de etapas posteriores sem apagar referências históricas.
3. Rejeitar importação de checkpoint adulterado ou inconsistente, event_id repetido ou mudança conflitante, de forma atômica. SHA-256 do JSON é integridade, não certificação de origem nem prova de CAS durável.
4. Consultar somente sob clique explícito e por GET a API pública do GitHub para as issues #3126/#42, mains autorizadas e run_id informado; rejeitar alteração remota, credenciais, origem errada e resultados divergentes.
5. Preservar PT-BR, foco visível, navegação por teclado, separação de classificações, aviso claro de dado meramente declarado e proteção contra segredos/PII em registros locais.
6. Impedir alegação de E2E somente com CI verde, PR, relatório, nomes de jobs, artefatos listados ou 100% documental. Custo desconhecido permanece bloqueado. Não acionar GitHub Actions, ReqSys DEV, Ollama, Noteri ou Desktop.
7. Não instalar Docker, fazer automação GUI, merge, deploy, dispatch, criação de TODO/issue paralelo ou mutação de sistemas externos.

## Critérios de aceite

1. O Chromium local cadastra ficha vinculada à issue canônica, rejeita duplicidade lógica e segredos, documenta progresso somente com gates válidos e preserva trilha de auditoria.
2. Controle negativo RED: com 12 etapas documentadas e `worktree` obrigatório removido, a versão anterior exibiu 100%, aceitou acesso à etapa posterior e permitiu checkpoint inconsistente. GREEN: mostra 17% (2/12), bloqueia avanço e rejeita importação atômica.
3. Controle negativo: SHA divergente, custo desconhecido, lease repetida, host único e etapa fora de ordem bloqueiam, sem inventar IDs ou provas.
4. Exportação/reimportação do mesmo checkpoint é idempotente; hash alterado/event_id duplicado/conflicto não alteram o estado local.
5. Consulta simulada da API verifica seis fontes públicas, metadados do run, comparação SHA, bloqueio de repositório não permitido e rate limit sem gravar dados. Teste de rede real e E2E físico continuam **pendentes**.
6. Validar a sintaxe JS e executar `test_site.py` + `test_sources.py` no Chromium local; para PR, observar Pre-PR Readiness do SHA exato e seus demais gates. Não declarar READY_FOR_PR pela existência deste SDD.

## Evidências e limitações

- Testes versionados em `tools/codex-local-online/central-execucoes/`.
- `source_mode=assisted`; `model_calls=0` para esta edição, sem alegação de autoria Ollama.
- Todos os identificadores de hosts nos testes são fictícios e não provam failover.
- Não há autorização de merge/deploy/publicação do site; a branch Git de código é separada da implantação.
