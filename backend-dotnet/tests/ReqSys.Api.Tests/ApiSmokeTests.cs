using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.AspNetCore.Mvc.Testing;
using ReqSys.Api.Domain;
using Xunit;

namespace ReqSys.Api.Tests;

public sealed class ApiSmokeTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;

    public ApiSmokeTests(WebApplicationFactory<Program> factory)
    {
        _client = factory.CreateClient();
    }

    [Fact]
    public async Task Health_ReturnsOk()
    {
        var response = await _client.GetAsync("/health");
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Fact]
    public async Task Login_WithDemoCredentials_ReturnsToken()
    {
        var response = await _client.PostAsJsonAsync("/v1/auth/login", new LoginRequest("admin@reqsys.local", "admin123"));
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var body = await response.Content.ReadAsStringAsync();
        using var document = JsonDocument.Parse(body);
        Assert.True(document.RootElement.GetProperty("data").TryGetProperty("access_token", out _));
        Assert.True(document.RootElement.GetProperty("data").GetProperty("usuario").TryGetProperty("permissoes", out _));
    }

    [Fact]
    public async Task Requisitos_CanBeCreatedAndListed()
    {
        var create = await _client.PostAsJsonAsync("/v1/requisitos", new RequisitoRequest("Teste", "Criado em teste", "Alta", "QA"));
        Assert.Equal(HttpStatusCode.Created, create.StatusCode);

        var list = await _client.GetAsync("/v1/requisitos");
        Assert.Equal(HttpStatusCode.OK, list.StatusCode);
    }

    [Fact]
    public async Task FrontendCompatibilityEndpoints_ReturnOk()
    {
        var authConfig = await _client.GetAsync("/v1/auth/config");
        var dashboardInfo = await _client.GetAsync("/v1/dashboard/info");
        var ssrsStatus = await _client.GetAsync("/v1/relatorios/ssrs/status");
        var auditEvents = await _client.GetAsync("/v1/auditoria/eventos");

        Assert.Equal(HttpStatusCode.OK, authConfig.StatusCode);
        Assert.Equal(HttpStatusCode.OK, dashboardInfo.StatusCode);
        Assert.Equal(HttpStatusCode.OK, ssrsStatus.StatusCode);
        Assert.Equal(HttpStatusCode.OK, auditEvents.StatusCode);
    }

    [Fact]
    public async Task ConnectionBrokerHealth_ReturnsOperationalShape()
    {
        var response = await _client.GetAsync("/api/connectors/health");
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var body = await response.Content.ReadAsStringAsync();
        using var document = JsonDocument.Parse(body);
        var data = document.RootElement.GetProperty("data");

        Assert.True(data.TryGetProperty("correlation_id", out _));
        Assert.True(data.TryGetProperty("conectores", out var connectors));
        Assert.True(connectors.GetArrayLength() >= 1);
        Assert.True(data.TryGetProperty("resumo", out _));
    }

    [Fact]
    public async Task ConnectionBrokerCapabilityCheck_BlocksProductionWrite()
    {
        var response = await _client.PostAsJsonAsync("/api/connectors/capabilities/check", new
        {
            ambiente = "prod",
            capability = "repository.write",
            acao = "publicar_pr"
        });
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var body = await response.Content.ReadAsStringAsync();
        using var document = JsonDocument.Parse(body);
        var data = document.RootElement.GetProperty("data");

        Assert.False(data.GetProperty("allowed").GetBoolean());
        Assert.Equal("blocked", data.GetProperty("status").GetString());
        Assert.True(data.GetProperty("requires_human_confirmation").GetBoolean());
    }

    [Fact]
    public async Task FrontendPipelineFlow_ReturnsExpectedShape()
    {
        var solicitacao = await _client.PostAsJsonAsync("/v1/solicitacoes", new
        {
            titulo = "Nova solicitacao",
            descricao = "Descricao suficiente para validacao de compatibilidade",
            urgencia = "Alta",
            solicitante = "QA"
        });
        Assert.Equal(HttpStatusCode.OK, solicitacao.StatusCode);

        var validar = await _client.PostAsJsonAsync("/v1/requisitos/validar", new
        {
            titulo = "Nova solicitacao",
            descricao = "Descricao suficiente para validacao de compatibilidade"
        });
        Assert.Equal(HttpStatusCode.OK, validar.StatusCode);

        var estruturar = await _client.PostAsJsonAsync("/v1/requisitos/estruturar/1", new { titulo = "Nova solicitacao" });
        var publicar = await _client.PostAsJsonAsync("/v1/backlog/publicar-redmine/1", new { use_github_import = false });

        Assert.Equal(HttpStatusCode.OK, estruturar.StatusCode);
        Assert.Equal(HttpStatusCode.OK, publicar.StatusCode);
    }
}