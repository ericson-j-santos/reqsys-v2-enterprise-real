# GitHub Copilot Ollama MCP — requisitos

## Objetivo

Disponibilizar um agente selecionável **Ollama** no GitHub Copilot cloud agent,
usando o Ollama do PC24x7 como ferramenta MCP governada, sem expor a porta
`:11434` e sem transformar a resposta do modelo em autoridade de governança.

## Requisitos

1. O perfil `.github/agents/ollama.agent.md` deve ser `user-invocable` e
   direcionado a `github-copilot`.
2. O agente deve chamar somente a ferramenta MCP `ollama_analyze` para acesso
   ao Ollama; nenhum endpoint Ollama direto pode constar no perfil.
3. URL e token do MCP devem vir de Agents variable/secret
   `COPILOT_MCP_OLLAMA_URL` e `COPILOT_MCP_OLLAMA_TOKEN`; nenhum segredo
   literal pode ser versionado.
4. O bridge local deve aceitar somente o gateway
   `http://127.0.0.1:8008`/localhost:8008 e permanecer em bind loopback
   `127.0.0.1:8010`.
5. Apenas modelos allowlisted podem ser solicitados ou retornados. O baseline é
   `gemma4:31b-cloud` com fallback `gemma4:26b-q8-code`.
6. A chamada MCP deve exigir Bearer token e comparar o valor em tempo constante.
7. A ferramenta deve declarar `readOnlyHint=true` e não realizar escrita,
   deploy, alteração de permissão ou acesso a segredo.
8. Prompt, contexto, task type e `correlation_id` devem ser validados antes de
   qualquer chamada de rede.
9. Erros do gateway devem falhar com mensagem sanitizada; prompt, resposta e
   token não devem ser registrados como evidência.
10. Testes devem provar caso positivo, bloqueio de endpoint remoto, bloqueio de
    modelo não allowlisted, correlação inválida e contrato do custom agent.
11. O Pre-PR Readiness deve retornar `READY_FOR_PR=passed` no HEAD exato antes
    da abertura da PR.
12. O E2E funcional só é concluído quando o GitHub.com executar o agente Ollama
    contra URL HTTPS estável do MCP, a chamada chegar ao PC24x7, retornar pelo
    gateway com o mesmo `correlation_id` e um controle negativo rejeitar token
    inválido. Até isso ocorrer, o runtime permanece parcial.
