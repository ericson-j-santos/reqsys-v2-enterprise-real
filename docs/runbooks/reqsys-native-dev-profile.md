# ReqSys native DEV — contrato de pré-admissão (P0 #3138)

**Estado: CÓDIGO DE CONTRATO / ADOPTION_PENDING. NÃO OPERACIONAL.** Este incremento não adiciona labels, não muda `.github/workflows`, não substitui o perfil Docker legado e não acessa computadores.

A configuração é `config/reqsys-native-dev-profile.json`. O verificador é `scripts/validate_reqsys_native_dev_profile.py` (biblioteca Python stdlib). A validação da política estática só devolve `ready_for_work=false`. O verificador de recibo admite exclusivamente um recibo HMAC-SHA256 de emissor independente previamente integrado e vinculado a SHA, identidade, timestamps, lease, hash de checkpoint e sete gates. Ele não emite nem assina recibos reais. Não enviar chave via issue, logs, CLI, PR ou frontend; o exemplo do teste usa uma chave descartável explícita. Mesmo com recibo válido, `dispatch_allowed=false` e `continuity_certified=false`.

## Validação isolada

```text
python -m pytest -q tests/test_reqsys_native_dev_profile.py
python -m compileall -q scripts/validate_reqsys_native_dev_profile.py
```

## Próximas integrações (não implementadas)

1. Runtime Platform deve implementar fonte de recibo realmente independente no Session Launcher + Command Gateway, com credencial de verificação de custódia separada, metadados sanitizados e readback externo. Não gerar recibo a partir de campos autodeclarados pelo runner.
2. Integrar seletor `native_runtime` à política do pool e ao preflight compartilhado **somente após** testes negativos da fonte e revisão por segurança. Perfil Docker `runtime` não pode herdar `native_runtime` e vice-versa.
3. Criar onboarding nativo Windows x64 sem Docker e reconciliação allowlisted exclusiva com manifestos em user scope, CAS, worktree/lease e registro completo da execução. Exigir readback online/Idle sem transformar labels em prova de prontidão.
4. Migrar apenas o job TODO Global/Notion comprovadamente nativo. O atual `todo-global-hourly-cycle.yml::reconcile-runtime` depende de Azure OIDC, Key Vault e Docker: **não** retargetar esse job. Não ler/rotacionar secret até capacidade nativa da issue #3138 e autorização específica.
5. E2E físico de mesma tarefa em dois hosts, Validator independente, evidência execution-bound e readback. Somente depois declarar `ready_for_work`/continuidade.

Custo adicional máximo R$ 0,00; sem Docker, GUI, reboot, deploy, merge ou administração automática. Controles específicos e bloqueios: issue #3138, TODO-59 e `e2e-platform#10`.
