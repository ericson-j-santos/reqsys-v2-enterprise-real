using System.Net;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

namespace ReqSys.Api.Tests;

public sealed class ConnectionBrokerMetricsTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;

    public ConnectionBrokerMetricsTests(WebApplicationFactory<Program> factory)
    {
        _client = factory.CreateClient();
    }

    [Fact]
    public async Task MetricsEndpoint_ReturnsPrometheusText()
    {
        var response = await _client.GetAsync("/api/connectors/metrics");
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.StartsWith("text/plain", response.Content.Headers.ContentType?.MediaType ?? string.Empty);

        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("# HELP reqsys_connection_broker_capabilities_total", body);
        Assert.Contains("# TYPE reqsys_connection_broker_capabilities_total gauge", body);
        Assert.Contains("reqsys_connection_broker_capabilities_total", body);
        Assert.Contains("reqsys_connection_broker_capabilities_by_status_total", body);
        Assert.Contains("reqsys_connection_broker_human_confirmation_required_total", body);
    }

    [Fact]
    public async Task VersionedMetricsEndpoint_ReturnsSameMetricFamily()
    {
        var response = await _client.GetAsync("/v1/connectors/metrics");
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("reqsys_connection_broker_capabilities_by_criticality_total", body);
        Assert.Contains("reqsys_connection_broker_audit_events_total", body);
    }
}
