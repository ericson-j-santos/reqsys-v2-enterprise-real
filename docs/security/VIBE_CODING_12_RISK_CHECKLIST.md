# Vibe Coding — checklist de segurança dos 12 riscos

## Objetivo

Consolidar no ReqSys uma revisão objetiva dos 12 riscos do guia KipperDev **Vibe coding com segurança**, sem transformar busca textual em falsa evidência de segurança.

O gate automatizado fica em `scripts/vibe_security_gate.py` e reutiliza o workflow `Security Baseline Gate`. Ele é deliberadamente conservador:

- sinais estáticos de alta confiança podem bloquear a CI;
- riscos dependentes de contexto são marcados como `review_required`;
- `no_signal` significa apenas que o scanner não encontrou aquele padrão;
- ausência de sinal **não** significa que o risco foi eliminado.

## Matriz de controles

| # | Risco | Automação no ReqSys | Evidência complementar obrigatória |
|---|---|---|---|
| 01 | Segredos no frontend | Bloqueia nomes públicos de ambiente que indiquem segredo; Gitleaks continua ativo | Inspecionar bundle/mapas/respostas e comprovar que segredos ficam no backend; revogar/rotacionar quando houver exposição |
| 02 | Entradas sem validação | Sinaliza uso direto de payload/body para revisão | Testes de schema no servidor: tipo inválido, excesso de tamanho, campo extra e caso válido |
| 03 | SQL injection | Bloqueia construção SQL dinâmica de alta confiança | Consulta parametrizada + teste que trate payload malicioso como dado; CodeQL/Bandit complementam |
| 04 | Prompt injection | Sinaliza fluxo IA→ferramenta sem marcador de autorização | Fixture com instrução hostil e comprovação de autorização no backend, independente da saída do modelo |
| 05 | XSS | Bloqueia sinks HTML bruto sem sanitizador explícito | Teste em navegador com marcador inofensivo; HTML necessário deve usar sanitizador mantido |
| 06 | IDOR/BOLA | Sinaliza acesso por objeto sem marcador de identidade/tenant | Duas identidades/tenants: A não pode ler, alterar ou excluir recurso de B e continua acessando o próprio |
| 07 | SSRF | Sinaliza destino HTTP dinâmico sem allowlist aparente | Mocks para loopback, IPv4/IPv6 privado, redirecionamento e DNS; validar timeout/limite de resposta e egress |
| 08 | Senhas em texto puro | Bloqueia hash fraco de senha e sinaliza persistência suspeita | Preferir IdP; quando houver senha local, validar Argon2id/biblioteca, salt/custo e ausência em logs/respostas |
| 09 | Abuso de requisições / DoS / DDoS | Sinaliza login/cadastro sem rate limit aparente | Teste controlado de HTTP 429, recuperação da janela, limites de payload/timeout e proteção de borda |
| 10 | Enumeração e rotas administrativas | Sinaliza rota administrativa sem autorização aparente | Matriz de acesso: sem sessão → 401/403; usuário comum → 403/404; administrador autorizado → sucesso |
| 11 | Bots em login e cadastro | Sinaliza cadastro sem CAPTCHA/rate limit aparente | Validar token no backend, action/hostname, token ausente/inválido/expirado/reutilizado e falha do provedor |
| 12 | Mensagens de erro que vazam dados | Bloqueia retorno explícito de exceção em resposta | Forçar erro controlado; resposta não pode conter stack/SQL/path/token; request/correlation id deve ligar a log sanitizado |

## Como a CI deve interpretar o relatório

O artifact do `Security Baseline Gate` passa a incluir:

```text
artifacts/security-baseline/
├── security-baseline-report.json
├── security-baseline-report.md
└── vibe-security/
    ├── vibe-security-report.json
    └── vibe-security-report.md
```

Estados por risco:

- `blocked`: sinal estático de alta confiança; o gate falha em modo estrito.
- `review_required`: há superfície de risco que exige confirmação por teste/contexto.
- `no_signal`: nenhum padrão foi encontrado no escopo analisado; **não é declaração de segurança**.

## Controles já existentes que permanecem válidos

Este incremento não duplica scanners especializados. O ReqSys já possui:

- Gitleaks para segredos;
- CodeQL para SAST;
- Bandit para Python;
- `pip-audit` e `npm audit` para dependências;
- SBOM CycloneDX;
- baseline determinístico para `.env`, segredo hardcoded, CORS, TLS e logs.

O gate de 12 riscos acrescenta a camada semântica alinhada ao guia e direciona quais testes precisam comprovar os riscos contextuais.

## Evidência mínima para fechar um achado

Para cada risco confirmado/corrigido, registrar:

1. arquivo e linha;
2. fluxo de dados e pré-condição;
3. branch e SHA exatos;
4. ambiente;
5. caso que reproduzia a falha;
6. correção mínima;
7. caso negativo/controle;
8. caso válido que continua funcionando;
9. leitura independente do efeito quando houver persistência ou integração;
10. dependências de infraestrutura ainda não verificadas.

Não usar como prova isolada: build verde, exit code 0, HTTP 2xx, log de sucesso ou ausência em busca textual.

## Limites operacionais

- Não executar carga em produção para validar DoS/DDoS.
- Não consultar metadata real de nuvem para testar SSRF; usar mocks/ambiente autorizado.
- Não imprimir ou copiar segredos para evidência.
- Não promover ambiente por resultado deste gate isoladamente.
- Qualquer evidência de outro SHA é inválida para o HEAD atual.
