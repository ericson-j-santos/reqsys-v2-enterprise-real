using ReqSys.Api.Domain;
using ReqSys.Api.Services;

namespace ReqSys.Api.Endpoints;

public static class ReqSysEndpoints
{
    public static WebApplication MapReqSysEndpoints(this WebApplication app)
    {
        var v1 = app.MapGroup("/v1");

        app.MapGet("/health", (HttpContext context) => ApiEnvelope<object>.Ok(new { status = "ok", service = "reqsys-dotnet-api" }, context));

        v1.MapPost("/auth/login", (LoginRequest request, AuthService auth, HttpContext context) =>
        {
            var response = auth.Login(request);
            return response is null
                ? Results.Unauthorized()
                : Results.Ok(ApiEnvelope<LoginResponse>.Ok(response, context));
        });

        v1.MapGet("/sistema/info", (IConfiguration configuration, HttpContext context) =>
            ApiEnvelope<object>.Ok(new
            {
                nome = "ReqSys Enterprise API .NET",
                versao = configuration["ReqSys:Version"] ?? "3.1.0",
                stack = ".NET 8 / C# 12",
                modulos = new[] { "auth", "dashboard", "requisitos", "pipeline", "relatorios", "auditoria", "qualidade-ia" }
            }, context));

        v1.MapGet("/dashboard/resumo", (ReqSysStore store, HttpContext context) =>
            ApiEnvelope<DashboardResumo>.Ok(store.Dashboard(), context));

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

        v1.MapGet("/relatorios", (HttpContext context) =>
            ApiEnvelope<IReadOnlyList<RelatorioItem>>.Ok(new[]
            {
                new RelatorioItem("REQ-CSV", "Exportação de requisitos", "csv", "/v1/relatorios/requisitos.csv"),
                new RelatorioItem("AUD-PDF", "Auditoria operacional", "pdf", "/v1/relatorios/auditoria.pdf")
            }, context));

        v1.MapGet("/auditoria", (ReqSysStore store, HttpContext context) =>
            ApiEnvelope<IReadOnlyCollection<AuditoriaEvento>>.Ok(store.ListarAuditoria(), context));

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
                new[] { "Manter revisão humana em requisitos críticos", "Ampliar amostras de rastreabilidade" }), context));

        return app;
    }

    private static string UsuarioAtual(HttpContext context) =>
        context.Request.Headers.TryGetValue("X-User", out var usuario) && !string.IsNullOrWhiteSpace(usuario)
            ? usuario.ToString()
            : "api-user";
}
