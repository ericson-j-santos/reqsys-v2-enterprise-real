# Integração do preflight nativo com origem de recibos independente (#3138, PR #3141)

## Objetivo
Avançar a etapa de execução nativa sem Docker ligando uma action somente leitura ao contrato de perfil, e um verificador hospedado aos recibos do Session Launcher e Command Gateway já existentes. A origem física real continua condicionada a admissão do host.

## Requisitos
1. A action isolada `reqsys-native-dev-preflight` executa apenas validação de candidato no Windows x64; jamais confunde `native_runtime` com `runtime` legado Docker.
2. Manifesto com perfil, SHA, instance_id, labels e ferramentas exatamente previstos; reparse point e root inválido bloqueiam. A action não escreve nem aplica labels, não roda Docker ou invoca Gateway automaticamente.
3. Verificador de prova independente exige **duas** assinaturas HMAC de domínio externo, uma do recibo de elegibilidade e outra do vínculo dos bytes exatos de Launcher, Gateway e inventário GitHub; nenhuma chave é fornecida ao host.
4. Evento do Launcher precisa de `SESSION_LAUNCH_OK`, `state_validated=true`, SHA, sessão, perfil NORMAL e worktree/lease exclusivos.
5. Evento Gateway exige `state_changed=false`, `result=ok`, exit code zero, mesmo SHA/sessão e comando allowlisted `reqsys-native-dev-readonly-probe`.
6. Adaptador read-only da API oficial GitHub confere run/job/runner/labels por GET, com URLs fixas, sem deduzir identidade física; o inventário de prova independente deve informar a mesma identidade, host, label, HEAD, runner online e não ocupado, além de idade máxima de 300 segundos.
7. Mesmo com ambas assinaturas sintéticas válidas, a verificação retorna `ready_for_work=false`, `dispatch_allowed=false`, `continuity_certified=false` até E2E físico e implantação do emissor no domínio separado.
8. Rejeitar campos extras, identidade, SHA, idade, assinatura, hash, ferramenta, SO, gates ou origem divergentes. Nenhum segredo em logs, argumentos, artifact, frontend ou commits.
9. Custo adicional máximo R$ 0,00, nenhuma mutação em host, nenhuma PR duplicada, nenhum merge ou deploy.

## Critérios de aceite
- Preflight local negativo e positivo, incluindo replay idempotente, sem contato com host.
- Teste de assinatura independente detecta mutações em cada fonte, SHA, sessão e inventário; testes positivos são sintéticos e não E2E físico.
- `tests/test_reqsys_native_gateway_preflight.py`, `tests/test_reqsys_native_github_readback.py` e os testes anteriores do perfil nativo passam no commit atual.
- SDD, Ruff, CI e readback no mesmo SHA antes de considerar a alteração pronta para revisão.
- Emissor independente real e fonte física somente após preflight do Session Launcher, Gateway, runner e custo zero; até lá status `ADOPTION_PENDING`, sem labels, dispatch ou secrets.
