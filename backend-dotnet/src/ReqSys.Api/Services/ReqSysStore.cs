using System.Collections.Concurrent;
using System.Text.Json;
using System.Text.Json.Serialization;
using ReqSys.Api.Domain;

namespace ReqSys.Api.Services;

public sealed class ReqSysStore
{
    private const string DefaultRegistryPath = "config/connectors/connection-broker-registry.json";

    private readonly ConcurrentDictionary<Guid, Requisito> _requisitos = new();
    private readonly ConcurrentDictionary<string, ConnectorCapability> _connectorRegistry = new(StringComparer.OrdinalIgnoreCase);
    private readonly ConcurrentQueue<AuditoriaEvento> _auditoria = new();

    public ReqSysStore()
    {
        Seed();
    }

    public IReadOnlyCollection<Requisito> ListarRequisitos() =>
        _requisitos.Values.OrderByDescending(item => item.CriadoEm).ToArray();

    public Requisito? ObterRequisito(Guid id) =>
        _requisitos.TryGetValue(id, out var requisito) ? requisito : null;

    public Requisito CriarRequisito(RequisitoRequest request, string usuario)
    {
        var agora = DateTimeOffset.UtcNow;
        var requisito = new Requisito(
            Guid.NewGuid(),
            $"REQ-{agora:yyyyMMddHHmmssfff}",
            request.Titulo.Trim(),
            request.Descricao.Trim(),
            request.Prioridade.Trim(),
            request.Status,
            request.Responsavel.Trim(),
            agora,
            agora);

        _requisitos[requisito.Id] = requisito;
        RegistrarAuditoria("requisito.criado", "requisito", requisito.Codigo, usuario);
        return requisito;
    }

    public Requisito? AtualizarRequisito(Guid id, RequisitoRequest request, string usuario)
    {
        if (!_requisitos.TryGetValue(id, out var existente))
        {
            return null;
        }

        var atualizado = existente with
        {
            Titulo = request.Titulo.Trim(),
            Descricao = request.Descricao.Trim(),
            Prioridade = request.Prioridade.Trim(),
            Responsavel = request.Responsavel.Trim(),
            Status = request.Status,
            AtualizadoEm = DateTimeOffset.UtcNow
        };

        _requisitos[id] = atualizado;
        RegistrarAuditoria("requisito.atualizado", "requisito", atualizado.Codigo, usuario);
        return atualizado;
    }

    public bool RemoverRequisito(Guid id, string usuario)
    {
        if (!_requisitos.TryRemove(id, out var removido))
        {
            return false;
        }

        RegistrarAuditoria("requisito.removido", "requisito", removido.Codigo, usuario);
        return true;
    }

    public DashboardResumo Dashboard()
    {
        var requisitos = _requisitos.Values.ToArray();
        return new DashboardResumo(
            requisitos.Length,
            requisitos.Count(item => item.Status == RequisitoStatus.Aprovado),
            requisitos.Count(item => item.Status == RequisitoStatus.EmAnalise),
            requisitos.Count(item => item.Status is RequisitoStatus.Rascunho or RequisitoStatus.EmDesenvolvimento),
            91.4m);
    }

    public PipelineResult ExecutarPipeline(PipelineRequest request, string usuario)
    {
        var etapas = request.Etapas.Count == 0
            ? new[] { "validar", "rastrear", "publicar" }
            : request.Etapas.Select(etapa => etapa.Trim()).Where(etapa => etapa.Length > 0).ToArray();

        var result = new PipelineResult(Guid.NewGuid(), "concluido", etapas, DateTimeOffset.UtcNow);
        RegistrarAuditoria("pipeline.executado", "pipeline", $"{request.Nome}: {request.Origem} -> {request.Destino}", usuario);
        return result;
    }

    public IReadOnlyCollection<ConnectorCapability> ListarConnectorCapabilities() =>
        _connectorRegistry.Values
            .OrderBy(item => item.Ambiente)
            .ThenBy(item => item.Conector)
            .ThenBy(item => item.Capability)
            .ToArray();

    public ConnectorCapability? ObterConnectorCapability(string ambiente, string capability)
    {
        var key = ConnectorRegistryKey(ambiente, capability);
        return _connectorRegistry.TryGetValue(key, out var item) ? item : null;
    }

    public CapabilityCheckResult VerificarConnectorCapability(string ambiente, string capability, string acao, string correlationId, string usuario)
    {
        var item = ObterConnectorCapability(ambiente, capability);
        var criticalWrite = capability.EndsWith(".write", StringComparison.OrdinalIgnoreCase) || acao.Contains("publicar", StringComparison.OrdinalIgnoreCase);
        var productionWrite = ambiente.Equals("prod", StringComparison.OrdinalIgnoreCase) && criticalWrite;
        var status = item?.Status ?? "misconfigured";
        var allowed = item is not null && status is "ready" && !productionWrite;

        if (productionWrite)
        {
            status = "blocked";
        }

        var result = new CapabilityCheckResult(
            allowed,
            status,
            ambiente,
            capability,
            acao,
            criticalWrite || item?.RequiresHumanConfirmation == true,
            allowed ? "Capability autorizada para execucao governada." : "Capability bloqueada ou pendente por regra de governanca.",
            correlationId);

        RegistrarAuditoria(
            "connection_broker.capability_check",
            "connection_broker",
            $"correlation_id={correlationId}; ambiente={ambiente}; capability={capability}; status={result.Status}; allowed={result.Allowed}",
            usuario);

        return result;
    }

    public IReadOnlyCollection<AuditoriaEvento> ListarAuditoria() =>
        _auditoria.Reverse().Take(100).ToArray();

    public void RegistrarAuditoria(string acao, string entidade, string detalhes, string usuario) =>
        _auditoria.Enqueue(new AuditoriaEvento(Guid.NewGuid(), acao, entidade, detalhes, usuario, DateTimeOffset.UtcNow));

    private void Seed()
    {
        CriarRequisito(
            new RequisitoRequest("Portal de requisitos em .NET", "Scaffold C# para evolução do ReqSys.", "Alta", "Arquitetura", RequisitoStatus.EmAnalise),
            "system");
        CriarRequisito(
            new RequisitoRequest("Rastreabilidade de releases", "Versionamento semântico, changelog e GitFlow documentados.", "Alta", "DevOps", RequisitoStatus.Aprovado),
            "system");

        LoadConnectorRegistry();
    }

    private void LoadConnectorRegistry()
    {
        var path = Environment.GetEnvironmentVariable("REQSYS_CONNECTION_BROKER_REGISTRY") ?? DefaultRegistryPath;
        if (!File.Exists(path))
        {
            SeedConnectorRegistryFallback("registry_file_not_found");
            return;
        }

        try
        {
            var json = File.ReadAllText(path);
            var registry = JsonSerializer.Deserialize<ConnectorRegistryDocument>(json, SerializerOptions());
            var capabilities = registry?.Capabilities ?? Array.Empty<ConnectorCapability>();
            var validCapabilities = capabilities.Where(IsValidConnectorCapability).ToArray();

            if (validCapabilities.Length == 0)
            {
                SeedConnectorRegistryFallback("registry_without_valid_capabilities");
                return;
            }

            foreach (var capability in validCapabilities)
            {
                AddConnectorCapability(capability);
            }

            RegistrarAuditoria("connection_broker.registry.loaded", "connection_broker", $"source={path}; total={validCapabilities.Length}", "system");
        }
        catch (JsonException)
        {
            SeedConnectorRegistryFallback("registry_invalid_json");
        }
        catch (IOException)
        {
            SeedConnectorRegistryFallback("registry_io_error");
        }
        catch (UnauthorizedAccessException)
        {
            SeedConnectorRegistryFallback("registry_access_denied");
        }
    }

    private void SeedConnectorRegistryFallback(string reason)
    {
        AddConnectorCapability(new ConnectorCapability("dev", "repository_provider", "repository.read", "ready", "high", "Executar com auditoria e rastreabilidade.", false));
        AddConnectorCapability(new ConnectorCapability("homolog", "repository_provider", "repository.write", "missing_permission", "critical", "Solicitar autorizacao contextual antes de escrita governada.", true));
        AddConnectorCapability(new ConnectorCapability("prod", "document_provider", "document.read", "ready", "medium", "Manter health-check periodico.", false));
        AddConnectorCapability(new ConnectorCapability("prod", "communication_provider", "message.compose", "blocked", "high", "Exigir confirmacao humana antes de envio.", true));
        RegistrarAuditoria("connection_broker.registry.fallback", "connection_broker", $"reason={reason}; total={_connectorRegistry.Count}", "system");
    }

    private static bool IsValidConnectorCapability(ConnectorCapability capability) =>
        !string.IsNullOrWhiteSpace(capability.Ambiente) &&
        !string.IsNullOrWhiteSpace(capability.Conector) &&
        !string.IsNullOrWhiteSpace(capability.Capability) &&
        !string.IsNullOrWhiteSpace(capability.Status) &&
        !string.IsNullOrWhiteSpace(capability.Criticidade) &&
        !string.IsNullOrWhiteSpace(capability.AcaoSugerida);

    private void AddConnectorCapability(ConnectorCapability capability) =>
        _connectorRegistry[ConnectorRegistryKey(capability.Ambiente, capability.Capability)] = capability;

    private static string ConnectorRegistryKey(string ambiente, string capability) =>
        $"{ambiente.Trim().ToLowerInvariant()}::{capability.Trim().ToLowerInvariant()}";

    private static JsonSerializerOptions SerializerOptions() => new()
    {
        PropertyNameCaseInsensitive = true
    };
}

public sealed record ConnectorRegistryDocument(
    string Version,
    [property: JsonPropertyName("updated_at")] string UpdatedAt,
    IReadOnlyCollection<ConnectorCapability> Capabilities);

public sealed record ConnectorCapability(
    string Ambiente,
    string Conector,
    string Capability,
    string Status,
    string Criticidade,
    string AcaoSugerida,
    [property: JsonPropertyName("requires_human_confirmation")] bool RequiresHumanConfirmation);

public sealed record CapabilityCheckResult(
    bool Allowed,
    string Status,
    string Ambiente,
    string Capability,
    string Acao,
    bool RequiresHumanConfirmation,
    string Message,
    string CorrelationId);
