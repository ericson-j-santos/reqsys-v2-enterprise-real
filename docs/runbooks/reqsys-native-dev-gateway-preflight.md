# Pré-admissão nativa ReqSys DEV: fonte de evidência do Gateway (P0 #3138)

**Entrega desta etapa:** action de **pré-admissão local sem Docker** e verificador de evidências **fora do host**. Não é um emissor operacional. `ready_for_work=false` em todas as saídas deste incremento; nenhum job existente foi redirecionado.

## Dois domínios de confiança

1. **Candidato no runner Windows:** a action `.github/actions/reqsys-native-dev-preflight` executa somente `scripts/reqsys_native_gateway_preflight.py --mode local`, exigindo manifesto DEV user-scoped, SHA/labels e ferramentas. Nunca obtém chave de assinatura nem chama Gateway por conta própria. Um resultado positivo é `LOCAL_PREFLIGHT_ONLY` e **não** libera trabalho.
2. **Validator externo GitHub-hosted:** somente depois de o Session Launcher existente lançar uma sessão exclusiva com `SESSION_LAUNCH_OK`, a Runtime Platform poderá produzir uma **observação bruta** do Command Gateway canônico, usando o comando `reqsys-native-dev-readonly-probe` previamente allowlisted e sem mutações. Um validador realmente independente deve reler o run/runner na API oficial do GitHub e os artefatos originais, atestar os bytes, então assinar o recibo de elegibilidade e o vínculo com HMAC em um domínio com credencial de custódia separada. O consumidor `--mode independent` valida ambos. `scripts/reqsys_native_github_readback.py` realiza somente as leituras oficiais do run, job e runner; não certifica sozinho a identidade física, e depende de token de leitura separado no executor externo. Não existe nesta PR um job capaz de assinar ou disparar a coleta; sem o emissor implantado falha fechado.

## Testes no checkout

`python -m pytest -q tests/test_reqsys_native_dev_profile.py tests/test_reqsys_native_gateway_preflight.py tests/test_reqsys_native_github_readback.py`

`python -m py_compile scripts/reqsys_native_gateway_preflight.py scripts/validate_reqsys_native_dev_profile.py`

## Prova necessária para a próxima fase

- Admissão física do DESKTOP-PDQK954/runner ID 22 em escopo DEV por Session Launcher, perfil NORMAL, Gateway, SHA, lease/worktree exclusivos e origem integra;
- Emissão independente e readback de observações originais vinculadas a `run_id`, `source_sha`, `runner_instance_id`, `event_id`, `correlation_id` e digest; consulta do runner pela API GitHub **fora** do host;
- Rejeição de prova falsa de label, sessão caduca, SHA antigo, runner busy, origem do mesmo host, custo desconhecido, replay divergente;
- Emissão/validação E2E da **mesma tarefa** entre dois hosts físicos distintos, com recuperação de checkpoint e posse única;
- Só depois adaptar workflow TODO Global realmente nativo; o `reconcile-runtime` atual usa Docker e Azure, portanto não mudar seus labels nem dispatch.

Esta alteração não lê/rotaciona `REQSYS_TODO_GLOBAL_RUNTIME_TOKEN_DEV`, não aplica labels, não faz merge, deploy, reboot, Azure, Docker ou operação administrativa. Regras v1.6.21, SHA `58dcd4200f412a866278027ba9e433439a03f3b3`.
