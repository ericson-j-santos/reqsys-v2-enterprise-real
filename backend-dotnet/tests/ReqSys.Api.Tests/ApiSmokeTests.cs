using System.Net;
using System.Net.Http.Json;
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
    }

    [Fact]
    public async Task Requisitos_CanBeCreatedAndListed()
    {
        var create = await _client.PostAsJsonAsync("/v1/requisitos", new RequisitoRequest("Teste", "Criado em teste", "Alta", "QA"));
        Assert.Equal(HttpStatusCode.Created, create.StatusCode);

        var list = await _client.GetAsync("/v1/requisitos");
        Assert.Equal(HttpStatusCode.OK, list.StatusCode);
    }
}
