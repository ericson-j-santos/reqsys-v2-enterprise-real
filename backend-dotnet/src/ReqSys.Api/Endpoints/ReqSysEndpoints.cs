using System.Text;
using System.Text.Json;
using ReqSys.Api.Domain;
using ReqSys.Api.Services;

namespace ReqSys.Api.Endpoints;

public static class ReqSysEndpoints
{
    public static WebApplication MapReqSysEndpoints(this WebApplication app)
    {
        var v1 = app.MapGroup("/v1");

        app.MapGet("/health", (HttpContext context) =>
            ApiEnvelope<object>.Ok(new { status = "ok", service = "reqsys-dotnet-api" }, context));

        app.MapGet("/api/connectors/health", (ReqSysStore store, HttpContext context) =>
            ApiEnvelope<object>.Ok(BuildConnectorHealth(store, context), context));

        app.MapPost("/api/connectors/capabilities/check", async (ReqSysStore store, HttpContext context) =>
            ApiEnvelope<object>.Ok(await BuildCapabilityCheckAsync(store, context), context));

        v1.MapPost("/auth/login", (LoginRequest request, AuthService auth, HttpContext context) =>
        {
            var response = auth.Login(request);
            return response is null
                ? Results.Unauthorized()
                : Results.Ok(ApiEnvelope<LoginResponse>.Ok(response, context));
        });

        v1.MapGet("/auth/config", (HttpContext context) =>
            ApiEnvelope<object>.Ok(new
            {
                azure_enabled = false,
                azure_tenant_id = "",
                azure_client_id = "",
                redirect_uri = ""
            }, context));

        v1.MapPost("/auth/azure-code", (HttpContext context) =>
            Results.BadRequest(ApiEnvelope<object>.Ok(new
            {
                error = "azure_auth_not_configured",
                message = "Azure AD is not enabled in the .NET compatibility stack."
            }, context)));

        v1.MapGet("/sistema/info", (IConfiguration configuration, HttpContext context) =>
            ApiEnvelope<object>.Ok(new
            {
                nome = "ReqSys Enterprise API .NET",
                versao = configuration["ReqSys:Version"] ?? "3.1.0",
                stack = ".NET 8 / C# 12",
                modulos = new[] { "auth", "dashboard", "requisitos", "pipeline", "relatorios", "auditoria", "qualidade-ia", "connection-broker" }
            }, context));

        v1.MapGet("/dashboard/resumo", (ReqSysStore store, HttpContext context) =>
            ApiEnvelope<DashboardResumo>.Ok(store.Dashboard(), context));

        v1.MapGet("/dashboard/requisitos", (ReqSysStore store, HttpContext context) =>
        {
            var dashboard = store.Dashboard();
            return ApiEnvelope<object>.Ok(new
            {
                total = dashboard.TotalRequisitos,
                aprovados = dashboard.Aprovados,
                em_analise = dashboard.EmAnalise,
                pendentes = dashboard.Pendentes,
                qualidade_ia_score = dashboard.QualidadeIaScore
            }, context);
        });

        v1.MapGet("/dashboard/info", (IConfiguration configuration, HttpContext context) =>
            ApiEnvelope<object>.Ok(new
            {
                app = "ReqSys Enterprise",
                api = "reqsys-dotnet-api",
                versao = configuration["ReqSys:Version"] ?? "3.1.0",
                stack = ".NET 8 / C# 12",
                conectado = true
            }, context));

        v1.MapGet("/connectors/health", (ReqSysStore store, HttpContext context) =>
            ApiEnvelope<object>.Ok(BuildConnectorHealth(store, context), context));

        v1.MapPost("/connectors/capabilities/check", async (ReqSysStore store, HttpContext context) =>
            ApiEnvelope<object>.Ok(await BuildCapabilityCheckAsync(store, context), context));

        v1.MapGet("/requisitos", (ReqSysStore store, HttpContext context) =>
            ApiEnvelope<IReadOnlyCollection<Requisito>>.Ok(store.ListarRequisitos(), context));

        v1.MapGet("/requisitos/{id:guid}", (Guid id, ReqSysStore store, HttpContext context) =>
        {
            var requisito = store.ObterRequisito(id);
            return requisito is null
                ? Results.NotFound()
                : Results.Ok(ApiEnvelope<Requisito>.Ok(requisito, context));
        });

        v1.MapPost("/requisitos", (RequisitoRequest request, ReqSysStore store, HttpContext context) =>
        {
            var requisito = store.CriarRequisito(request, UsuarioAtual(context));
            return Results.Created($"/v1/requisitos/{requisito.Id}", ApiEnvelope<Requisito>.Ok(requisito, context));
        });

        v1.MapPut("/requisitos/{id:guid}", (Guid id, RequisitoRequest request, ReqSysStore store, HttpContext context) =>
        {
            var requisito = store.AtualizarRequisito(id, request, UsuarioAtual(context));
            return requisito is null
                ? Results.NotFound()
                : Results.Ok(ApiEnvelope<Requisito>.Ok(requisito, context));
        });

        v1.MapDelete("/requisitos/{id:guid}", (Guid id, ReqSysStore store, HttpContext context) =>
            store.RemoverRequisito(id, UsuarioAtual(context)) ? Results.NoContent() : Results.NotFound());

        v1.MapPost("/pipeline/executar", (PipelineRequest request, ReqSysStore store, HttpContext context) =>
            ApiEnvelope<PipelineResult>.Ok(store.ExecutarPipeline(request, UsuarioAtual(context)), context));

        v1.MapPost("/solicitacoes", async (HttpContext context, ReqSysStore store) =>
        {
            var payload = await JsonSerializer.DeserializeAsync<JsonElement>(context.Request.Body);
            var titulo = GetString(payload, "titulo", "Solicitacao ReqSys");
            var requisito = store.CriarRequisito(new RequisitoRequest(
                titulo,
                GetString(payload, "descricao", "Criado pelo fluxo de compatibilidade .NET."),
                GetString(payload, "urgencia", "Media"),
                GetString(payload, "solicitante", UsuarioAtual(context))),
                UsuarioAtual(context));

            return Results.Ok(ApiEnvelope<object>.Ok(new
            {
                id = requisito.Id,
                codigo = requisito.Codigo,
                titulo = requisito.Titulo,
                status = "criada"
            }, context));
        });

        v1.MapPost("/requisitos/validar", async (HttpContext context) =>
        {
            var payload = await JsonSerializer.DeserializeAsync<JsonElement>(context.Request.Body);
            var titulo = GetString(payload, "titulo", "");
            var descricao = GetString(payload, "descricao", "");
            var alertas = new List<string>();
            if (titulo.Length < 5) alertas.Add("Titulo curto");
            if (descricao.Length < 20) alertas.Add("Descricao curta");

            return ApiEnvelope<object>.Ok(new
            {
                aprovado_para_triagem = alertas.Count == 0,
                score = alertas.Count == 0 ? 0.92m : 0.68m,
                alertas
            }, context);
        });

        v1.MapPost("/requisitos/estruturar/{id}", (string id, HttpContext context) =>
            ApiEnvelope<object>.Ok(new
            {
                requisito_id = id,
                requisitos_funcionais = new[]
                {
                    "Registrar solicitacao com dados obrigatorios",
                    "Manter trilha de auditoria da alteracao"
                },
                criterios_aceite = new[]
                {
                    "Dado um usuario autenticado, quando enviar dados validos, entao o requisito e criado",
                    "Dado um requisito criado, quando consultado, entao retorna codigo e status"
                }
            }, context));

        v1.MapPost("/backlog/publicar-redmine/{id}", (string id, HttpContext context) =>
            ApiEnvelope<object>.Ok(new
            {
                requisito_id = id,
                issue_principal_id = Random.Shared.Next(1000, 9999),
                subtarefas = new[] { new { id = Random.Shared.Next(10000, 99999), titulo = "Detalhar requisito" } },
                github_imported_count = 0,
                redmine_published_count = 1,
                warnings = Array.Empty<string>()
            }, context));

        v1.MapPost("/integracoes/github/issues", (HttpContext context) =>
            ApiEnvelope<object>.Ok(new { issues = Array.Empty<object>() }, context));

        v1.MapGet("/relatorios", (HttpContext context) =>
            ApiEnvelope<IReadOnlyList<RelatorioItem>>.Ok(new[]
            {
                new RelatorioItem("REQ-CSV", "Exportacao de requisitos", "csv", "/v1/relatorios/requisitos.csv"),
                new RelatorioItem("AUD-PDF", "Auditoria operacional", "pdf", "/v1/relatorios/auditoria.pdf")
            }, context));

        v1.MapGet("/relatorios/ssrs", (HttpContext context) =>
            ApiEnvelope<object>.Ok(new
            {
                configured = false,
                reports = new[]
                {
                    new { name = "Requisitos", path = "/ReqSys/Requisitos", format = "pdf" },
                    new { name = "Auditoria", path = "/ReqSys/Auditoria", format = "pdf" }
                }
            }, context));

        v1.MapGet("/relatorios/ssrs/health", (HttpContext context) =>
            ApiEnvelope<object>.Ok(new { status = "disabled", message = "SSRS not configured in .NET compatibility stack." }, context));

        v1.MapGet("/relatorios/ssrs/status", (HttpContext context) =>
            ApiEnvelope<object>.Ok(new { configured = false, online = false, reports_count = 2 }, context));

        v1.MapGet("/relatorios/ssrs/{nome}/pdf", (string nome) =>
            Results.File(Encoding.UTF8.GetBytes($"Relatorio {nome} gerado pela stack .NET de compatibilidade."),
                "text/plain",
                $"{nome}.txt"));

        v1.MapGet("/auditoria", (ReqSysStore store, HttpContext context) =>
            ApiEnvelope<IReadOnlyCollection<AuditoriaEvento>>.Ok(store.ListarAuditoria(), context));

        v1.MapGet("/auditoria/eventos", (ReqSysStore store, HttpContext context) =>
            ApiEnvelope<object>.Ok(new
            {
                dados = store.ListarAuditoria(),
                total = store.ListarAuditoria().Count
            }, context));

        v1.MapGet("/auditoria/eventos/config-infra", (ReqSysStore store, HttpContext context) =>
            ApiEnvelope<object>.Ok(new
            {
                config_historico = store.ListarAuditoria().Take(12).ToArray()
            }, context));

        v1.MapGet("/qualidade-ia/resumo", (HttpContext context) =>
            ApiEnvelope<QualidadeIaResumo>.Ok(new QualidadeIaResumo(
                91.4m,
                new Dictionary<string, decimal>
                {
                    ["acuracia"] = 92.1m,
                    ["relevancia"] = 90.7m,
                    ["consistencia"] = 93.0m,
                    ["seguranca"] = 95.2m,
                    ["cobertura"] = 86.0m
                },
                new[] { "Manter revisao humana em requisitos criticos", "Ampliar amostras de rastreabilidade" }), context));

        v1.MapPost("/qualidade-ia/snapshot", (HttpContext context) =>
            ApiEnvelope<object>.Ok(new { status = "registrado", criado_em = DateTimeOffset.UtcNow }, context));

        v1.MapGet("/qualidade-ia/tendencia.csv", () =>
            Results.Text("data,score\n2026-06-01,90.2\n2026-06-02,91.4\n", "text/csv"));

        v1.MapGet("/qualidade-ia/tendencia.pdf", () =>
            Results.File(Encoding.UTF8.GetBytes("Tendencia de qualidade IA - compatibilidade .NET"),
                "text/plain",
                "qualidade-ia-tendencia.txt"));

        v1.MapGet("/ia/status", (HttpContext context) =>
            ApiEnvelope<object>.Ok(new
            {
                provider = "dotnet-compat",
                online = true,
                fallback = false
            }, context));

        v1.MapGet("/sistema/segredos-status", (HttpContext context) =>
            ApiEnvelope<object>.Ok(new
            {
                cofre_inicializado = false,
                provider = "local-dev",
                segredos = Array.Empty<object>()
            }, context));

        v1.MapPost("/cofre/init", (HttpContext context) =>
            ApiEnvelope<object>.Ok(new { inicializado = true }, context));

        v1.MapPost("/cofre/segredos", (HttpContext context) =>
            ApiEnvelope<object>.Ok(new { salvo = true }, context));

        v1.MapDelete("/cofre/segredos/{key}", (string key, HttpContext context) =>
            ApiEnvelope<object>.Ok(new { removido = true, key }, context));

        v1.MapGet("/specs", (HttpContext context) =>
            ApiEnvelope<object>.Ok(new { features = Array.Empty<object>() }, context));

        v1.MapGet("/specs/templates", (HttpContext context) =>
            ApiEnvelope<object>.Ok(new { templates = Array.Empty<object>() }, context));

        v1.MapGet("/specs/{slug}", (string slug, HttpContext context) =>
            ApiEnvelope<object>.Ok(new { slug, arquivos = Array.Empty<object>() }, context));

        v1.MapPut("/specs/{feature}/{arquivo}.md", (string feature, string arquivo, HttpContext context) =>
            ApiEnvelope<object>.Ok(new { salvo = true, feature, arquivo }, context));

        v1.MapPost("/specs", (HttpContext context) =>
            ApiEnvelope<object>.Ok(new { criado = true }, context));

        return app;
    }

    private static object BuildConnectorHealth(ReqSysStore store, HttpContext context)
    {
        var conectores = store.ListarConnectorCapabilities()
            .Select(item => new
            {
                ambiente = item.Ambiente,
                conector = item.Conector,
                capability = item.Capability,
                status = item.Status,
                criticidade = item.Criticidade,
                acao_sugerida = item.AcaoSugerida,
                requires_human_confirmation = item.RequiresHumanConfirmation
            })
            .ToArray();

        return new
        {
            correlation_id = context.TraceIdentifier,
            conectores,
            resumo = new
            {
                total = conectores.Length,
                prontos = conectores.Count(item => item.status == "ready"),
                pendentes = conectores.Count(item => item.status is "missing_permission" or "insufficient_permission" or "expired"),
                bloqueados = conectores.Count(item => item.status is "blocked" or "unavailable" or "misconfigured"),
                estado_geral = conectores.Any(item => item.status is "blocked" or "unavailable" or "misconfigured")
                    ? "bloqueado"
                    : conectores.Any(item => item.status is "missing_permission" or "insufficient_permission" or "expired") ? "amarelo" : "verde"
            }
        };
    }

    private static async Task<object> BuildCapabilityCheckAsync(ReqSysStore store, HttpContext context)
    {
        var payload = await JsonSerializer.DeserializeAsync<JsonElement>(context.Request.Body);
        var correlationId = GetString(payload, "correlation_id", context.TraceIdentifier);
        var result = store.VerificarConnectorCapability(
            GetString(payload, "ambiente", "dev"),
            GetString(payload, "capability", "repository.read"),
            GetString(payload, "acao", "consultar"),
            correlationId,
            UsuarioAtual(context));

        return new
        {
            allowed = result.Allowed,
            status = result.Status,
            ambiente = result.Ambiente,
            capability = result.Capability,
            acao = result.Acao,
            requires_human_confirmation = result.RequiresHumanConfirmation,
            message = result.Message,
            correlation_id = result.CorrelationId
        };
    }

    private static string UsuarioAtual(HttpContext context) =>
        context.Request.Headers.TryGetValue("X-User", out var usuario) && !string.IsNullOrWhiteSpace(usuario)
            ? usuario.ToString()
            : "api-user";

    private static string GetString(JsonElement payload, string propertyName, string fallback)
    {
        if (payload.ValueKind == JsonValueKind.Object &&
            payload.TryGetProperty(propertyName, out var value) &&
            value.ValueKind == JsonValueKind.String)
        {
            return value.GetString() ?? fallback;
        }

        return fallback;
    }
}
