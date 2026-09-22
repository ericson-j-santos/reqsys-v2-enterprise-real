# Vibe Coding — análise de lacunas para baseline enterprise

## Escopo

O guia KipperDev usado como referência cobre 12 riscos práticos e exige evidência, testes positivos/negativos e distinção entre falha confirmada, suspeita e item não verificado. O próprio material se apresenta como ponto de partida; portanto, esta nota registra controles adicionais necessários para um baseline enterprise do ReqSys.

Esta seção é **complementar ao guia**. Os itens abaixo não são apresentados como parte dos 12 riscos originais.

## O que o guia cobre bem e foi incorporado

- segredos expostos ao frontend;
- validação de entradas;
- SQL injection;
- prompt injection e autorização fora do modelo;
- XSS;
- IDOR/BOLA;
- SSRF;
- armazenamento de senhas;
- abuso de requisições;
- rotas administrativas;
- bots em autenticação/cadastro;
- tratamento de erros sem vazamento;
- exigência de evidência, reprodução mínima e teste de regressão.

O ReqSys materializa essa camada no `vibe_security_gate.py`, mas não usa ausência de regex como prova de segurança.

## Lacunas complementares para o ReqSys

| Domínio complementar | Por que não deve ser inferido como coberto pelos 12 riscos | Controle ReqSys esperado |
|---|---|---|
| Autenticação, sessão, OAuth/OIDC e JWT | IDOR/BOLA trata autorização por objeto, não ciclo completo de identidade | issuer/audience/scopes, expiração, rotação, logout/revogação quando aplicável, cookies seguros, testes de sessão e claims |
| CSRF | XSS e CORS não substituem proteção CSRF | SameSite adequado, token/defesa equivalente em operações baseadas em cookie e teste cross-origin |
| Injeção de comando/template/LDAP/NoSQL | SQL injection cobre apenas SQL | APIs seguras, allowlists, sem shell dinâmico; SAST e testes por sink |
| Uploads, path traversal e arquivos | Validação de entrada genérica não prova isolamento de filesystem | nome/caminho gerado no servidor, limites de tipo/tamanho, diretório isolado, antivírus quando aplicável |
| Desserialização/parsers | Não é tratada explicitamente | formatos seguros, schemas, parser atualizado e limites de profundidade/tamanho |
| Supply chain | Os 12 riscos focam código/runtime da aplicação | dependências auditadas, lockfiles, SBOM, CodeQL/SAST, Gitleaks, ações pinadas e política de atualização |
| Permissões de CI/IaC/cloud | SSRF e segredos não provam menor privilégio da infraestrutura | permissões mínimas, OIDC quando possível, ambientes protegidos, revisão de IaC e separação DEV/STG/PROD |
| Criptografia e gestão de chaves | Senhas têm tratamento específico, mas dados/chaves em geral não | algoritmos/bibliotecas mantidos, secret store, rotação, TLS e política de dados em repouso/trânsito |
| Cabeçalhos e políticas de navegador | CSP aparece como camada de XSS, mas baseline web é mais amplo | CSP, HSTS, framing, content-type, referrer policy e cookies `Secure/HttpOnly/SameSite` |
| Webhooks e integrações inbound | Não coberto explicitamente | assinatura/autenticidade, replay protection, timestamp/nonce e idempotência |
| Concorrência e idempotência | Não é um dos 12 riscos | idempotency key, locks/controle otimista, replay sem duplicidade e teste concorrente |
| PII/LGPD e retenção | Mensagens de erro tratam vazamento, não ciclo de vida dos dados | minimização, mascaramento, retenção, auditoria de acesso e descarte |
| Observabilidade e resposta a incidente | Logs sanitizados são parte do risco 12, mas não bastam | correlation_id, alertas, trilha imutável, runbook, rollback e evidência pós-incidente |
| Backup/restauração e continuidade | Fora do escopo dos 12 riscos | backup verificável, teste de restauração, RPO/RTO quando definidos e evidência periódica |

## Estado já evidenciado no repositório

Na baseline atual do ReqSys existem mecanismos complementares para Gitleaks, CodeQL, Bandit, `pip-audit`, `npm audit`, SBOM CycloneDX, baseline de CORS/TLS/segredos/logs e gates de governança. Este incremento **não os substitui**; ele adiciona a matriz semântica dos 12 riscos e mantém as demais camadas como defesa em profundidade.

## Pareto de evolução

A prioridade deste incremento é impedir falso verde com baixo custo:

1. manter os scanners especializados existentes;
2. executar os 12 riscos no mesmo `Security Baseline Gate`;
3. bloquear somente sinais determinísticos de alta confiança;
4. transformar riscos contextuais em obrigação explícita de teste;
5. vincular evidência ao SHA e ao ambiente;
6. evoluir os controles complementares por risco/alteração, sem criar workflows redundantes.

## Critério de maturidade

O ReqSys não deve receber uma classificação global "seguro" a partir deste gate. O estado correto é composto por:

- bloqueadores estáticos;
- revisões contextuais pendentes;
- testes automatizados;
- evidência E2E/runtime;
- dependências externas não verificadas;
- risco residual explicitado.

Esse modelo preserva a regra de que resultado verde de scanner é evidência de uma camada, e não certificação integral da aplicação.
