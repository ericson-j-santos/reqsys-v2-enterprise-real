using System.Text.Json.Serialization;

namespace ReqSys.Api.Domain;

public enum RequisitoStatus
{
    Rascunho,
    EmAnalise,
    Aprovado,
    EmDesenvolvimento,
    Concluido,
    Cancelado
}

public sealed record Usuario(
    string Id,
    string Nome,
    string Email,
    [property: JsonPropertyName("papel")] string Perfil,
    [property: JsonPropertyName("permissoes")] string[] Escopos);

public sealed record LoginRequest(string Email, string Senha);

public sealed record LoginResponse(
    [property: JsonPropertyName("access_token")] string AccessToken,
    Usuario Usuario,
    [property: JsonPropertyName("expira_em")] DateTimeOffset ExpiraEm);

public sealed record Requisito(
    Guid Id,
    string Codigo,
    string Titulo,
    string Descricao,
    string Prioridade,
    RequisitoStatus Status,
    string Responsavel,
    DateTimeOffset CriadoEm,
    DateTimeOffset AtualizadoEm);

public sealed record RequisitoRequest(
    string Titulo,
    string Descricao,
    string Prioridade,
    string Responsavel,
    RequisitoStatus Status = RequisitoStatus.Rascunho);

public sealed record DashboardResumo(int TotalRequisitos, int Aprovados, int EmAnalise, int Pendentes, decimal QualidadeIaScore);

public sealed record PipelineRequest(string Nome, string Origem, string Destino, IReadOnlyList<string> Etapas);

public sealed record PipelineResult(Guid Id, string Status, IReadOnlyList<string> EtapasExecutadas, DateTimeOffset ExecutadoEm);

public sealed record AuditoriaEvento(Guid Id, string Acao, string Entidade, string Detalhes, string Usuario, DateTimeOffset CriadoEm);

public sealed record QualidadeIaResumo(decimal ScoreGeral, IReadOnlyDictionary<string, decimal> Dimensoes, IReadOnlyList<string> Recomendacoes);

public sealed record RelatorioItem(string Codigo, string Nome, string Formato, string Url);

public sealed record ApiEnvelope<T>(T Data, string CorrelationId, DateTimeOffset Timestamp)
{
    public static ApiEnvelope<T> Ok(T data, HttpContext context) =>
        new(data, context.TraceIdentifier, DateTimeOffset.UtcNow);
}
