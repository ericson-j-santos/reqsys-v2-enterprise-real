using System.Collections.Concurrent;
using ReqSys.Api.Domain;

namespace ReqSys.Api.Services;

public sealed class ReqSysStore
{
    private readonly ConcurrentDictionary<Guid, Requisito> _requisitos = new();
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
    }
}
