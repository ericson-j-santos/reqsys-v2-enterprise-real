using System.Text;
using ReqSys.Api.Services;

namespace ReqSys.Api.Endpoints;

public static class ConnectionBrokerMetricsEndpoints
{
    public static WebApplication MapConnectionBrokerMetricsEndpoints(this WebApplication app)
    {
        app.MapGet("/api/connectors/metrics", (ReqSysStore store) =>
            Results.Text(BuildMetrics(store), "text/plain; version=0.0.4; charset=utf-8"));

        app.MapGet("/v1/connectors/metrics", (ReqSysStore store) =>
            Results.Text(BuildMetrics(store), "text/plain; version=0.0.4; charset=utf-8"));

        return app;
    }

    private static string BuildMetrics(ReqSysStore store)
    {
        var capabilities = store.ListarConnectorCapabilities();
        var auditEvents = store.ListarAuditoria();
        var builder = new StringBuilder();

        AppendHelp(builder, "reqsys_connection_broker_capabilities_total", "Total de capabilities registradas no Connection Broker.");
        AppendType(builder, "reqsys_connection_broker_capabilities_total", "gauge");
        builder.AppendLine($"reqsys_connection_broker_capabilities_total {capabilities.Count}");

        AppendHelp(builder, "reqsys_connection_broker_capabilities_by_status_total", "Total de capabilities por status operacional.");
        AppendType(builder, "reqsys_connection_broker_capabilities_by_status_total", "gauge");
        foreach (var group in capabilities.GroupBy(item => item.Status).OrderBy(item => item.Key, StringComparer.Ordinal))
        {
            builder.AppendLine($"reqsys_connection_broker_capabilities_by_status_total{{status=\"{SanitizeLabel(group.Key)}\"}} {group.Count()}");
        }

        AppendHelp(builder, "reqsys_connection_broker_capabilities_by_criticality_total", "Total de capabilities por criticidade.");
        AppendType(builder, "reqsys_connection_broker_capabilities_by_criticality_total", "gauge");
        foreach (var group in capabilities.GroupBy(item => item.Criticidade).OrderBy(item => item.Key, StringComparer.Ordinal))
        {
            builder.AppendLine($"reqsys_connection_broker_capabilities_by_criticality_total{{criticality=\"{SanitizeLabel(group.Key)}\"}} {group.Count()}");
        }

        AppendHelp(builder, "reqsys_connection_broker_human_confirmation_required_total", "Total de capabilities que exigem confirmacao humana.");
        AppendType(builder, "reqsys_connection_broker_human_confirmation_required_total", "gauge");
        builder.AppendLine($"reqsys_connection_broker_human_confirmation_required_total {capabilities.Count(item => item.RequiresHumanConfirmation)}");

        AppendHelp(builder, "reqsys_connection_broker_audit_events_total", "Total de eventos de auditoria relacionados ao Connection Broker mantidos no processo.");
        AppendType(builder, "reqsys_connection_broker_audit_events_total", "gauge");
        var connectionBrokerAuditEvents = auditEvents.Count(item => item.Entidade == "connection_broker");
        builder.AppendLine($"reqsys_connection_broker_audit_events_total {connectionBrokerAuditEvents}");

        return builder.ToString();
    }

    private static void AppendHelp(StringBuilder builder, string name, string help) =>
        builder.AppendLine($"# HELP {name} {help}");

    private static void AppendType(StringBuilder builder, string name, string type) =>
        builder.AppendLine($"# TYPE {name} {type}");

    private static string SanitizeLabel(string value) =>
        value.Replace("\\", "\\\\", StringComparison.Ordinal).Replace("\"", "\\\"", StringComparison.Ordinal);
}
