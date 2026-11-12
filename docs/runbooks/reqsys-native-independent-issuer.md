# Emissor independente de evidências Gateway — DEV / #3138

**Estado: implementação de código validável, NÃO implantada e sem emissão física.**

## Por que existe

O Gateway e o Session Launcher executam/comprovam uma sessão, mas um JSON produzido no próprio PC não é prova de origem independente. Este incremento cria `scripts/reqsys_native_independent_issuer.py` para atuar **somente fora do computador avaliado**. Ele exige testemunho criptográfico do plano de controle independente, readback da API GitHub e prova de checkpoint por fonte separada; sem qualquer parte, retorna `BLOCKED_INDEPENDENT_ISSUER`. Mesmo com todos os dados válidos, a saída sempre conserva `ready_for_work=false`, `dispatch_allowed=false` e `continuity_certified=false`.

## Origem e custódia (mínimo obrigatório)

1. **Runtime Platform, no host:** usar o Session Launcher canônico para criar sessão NORMAL com `SESSION_LAUNCH_OK`, `state_validated=true`, SHA/worktree/lease exclusivos. Depois executar pelo Command Gateway **somente** o comando de inspeção fixa `reqsys-native-dev-readonly-probe` após sua homologação na allowlist governada. Produzir observação bruta sanitizada, sem qualquer segredo; esta observação **não** é atestado.
2. **Plano de controle independente:** conferir o evento original da auditoria do Gateway por canal autenticado fora do host, ler o checkpoint real em armazenamento CAS governado, verificar lease exclusivo e custo zero, e só então emitir `witness` Ed25519 sobre SHA, host, runner, sessão, `event_id`, `correlation_id`, lease, hashes de launcher/auditoria/checkpoint e sete gates. A chave de testemunho nunca pertence ao runner/host. O contrato de witness está em `WITNESS_FIELDS`, e os contratos de audit/CAS em `AUDIT_FIELDS` e `CHECKPOINT_FIELDS`. **Este produtor independente ainda não está implantado** e não pode ser substituído por dados autodeclarados.
3. **Validador externo em runner GitHub-hosted:** recebe somente os originais e o `witness`; relê run/job/runner pela API oficial GitHub; confere as duas chaves distintas, idade (até 300 s), SHA integral, identidade e hashes antes de emitir recibo e atestado. Usa `verify_gateway_source()` para revalidar sua própria saída. O resultado não autoriza despacho.
4. **E2E Platform:** valida um mesmo `event_id`/`correlation_id` e tarefa de um host físico para outro, com CAS, posse exclusiva e replay. A emissão em um host não comprova continuidade.

## Isolamento de segredos

O job externo, que **não deve ser executado em self-hosted**, precisa das três variáveis providas por fonte segura fora dos PCs: `REQSYS_NATIVE_GATEWAY_WITNESS_PUBLIC_KEY` (verificação PUBLICA Ed25519 de 32 bytes, em hexadecimal; NUNCA chave privada do observador), `REQSYS_NATIVE_VALIDATOR_KEY` (assinatura), `REQSYS_NATIVE_GITHUB_READ_TOKEN` (GET da API GitHub, permissão mínima). Não inserir valor em issues, PRs, comandos, args, output ou artefatos. O primeiro provisionamento da relação de confiança é ato humano e depende de ambiente externo já homologado. Não copiar chaves no PC24x7 ou Noteri.

## Entrada automatizável depois do provisionamento

A função `issue_independent_receipt()` é a interface de produção. A CLI `main()` aceita política e envelope JSON de evidências por arquivos **absolutos e restritos**, IDs esperados vindos do controlador e saída absoluta ainda inexistente; exige contexto GitHub-hosted, não utiliza Docker, SSH ou shell. Escrita ocorre exclusivamente em arquivo novo (`O_EXCL`/`O_NOFOLLOW`, modo 0600) e stdout recebe só código de status, `event_id` e hash sanitizado. Bloqueio não grava certificado. O mesmo evento e evidências com timestamp oficial idêntico produzem a mesma saída lógica, sem executar ou duplicar tarefas. Retenção/proteção durável de recibos deve ser implementada pelo plano de controle governado antes de uso real.

## Testes e limitações

`python -m pytest -q tests/test_reqsys_native_independent_issuer.py tests/test_reqsys_native_gateway_preflight.py tests/test_reqsys_native_github_readback.py`

Testes usam chaves descartáveis e API simulada; comprovam contrato, falsificações, tempo/host/runner/SHA/custo, replay e ausência de dispatch. **Não certificam a existência do emissor externo, Gateway em execução ou host pronto.** Sem producer externo, sessão física, configuração da chave e custo R$0,00 confirmado, não iniciar a rota real. Nenhum workflow, label, runner, secret, produção, deploy ou merge foi alterado por este módulo.

## Fronteira criptográfica corrigida (11/11/2026)
A verificação HMAC simétrica do witness anterior permitia que o emissor portador dessa chave criasse testemunhos. O contrato agora exige **Ed25519**. A chave PRIVADA fica exclusivamente com o observador externo; o emissor recebe apenas `REQSYS_NATIVE_GATEWAY_WITNESS_PUBLIC_KEY` (32 bytes como 64 dígitos hex), que não permite assinar testemunhos. O emissor mantém sua própria chave privada para o recibo. HMAC legado é recusado.

Esta correção de código **não implanta** a fonte independente de auditoria do Gateway nem custódia operacional. Não assinar dados fornecidos apenas pelo runner ou sintetizados. Sem fonte externa autenticada, permanecer BLOQUEADO.
