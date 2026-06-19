using ReqSys.Api.Endpoints;
using ReqSys.Api.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddSingleton<AuthService>();
builder.Services.AddSingleton<ReqSysStore>();
builder.Services.AddHealthChecks();
builder.Services.AddCors(options =>
{
    options.AddPolicy("ReqSysCors", policy =>
    {
        var origins = builder.Configuration.GetSection("ReqSys:CorsOrigins")
            .GetChildren()
            .Select(item => item.Value)
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Cast<string>()
            .ToArray();

        if (origins.Length == 0)
        {
            policy.DisallowCredentials();
            return;
        }

        policy.WithOrigins(origins)
            .AllowAnyHeader()
            .AllowAnyMethod()
            .AllowCredentials();
    });
});

ValidateRuntimeConfiguration(builder.Configuration, builder.Environment);

var app = builder.Build();

app.UseCors("ReqSysCors");
app.Use(async (context, next) =>
{
    context.Response.Headers.TryAdd("X-Request-ID", context.TraceIdentifier);
    context.Response.Headers.TryAdd("X-Content-Type-Options", "nosniff");
    await next();
});

app.MapHealthChecks("/healthz");
app.MapHealthChecks("/live");
app.MapHealthChecks("/ready");
app.MapReqSysEndpoints();

app.Run();

static void ValidateRuntimeConfiguration(IConfiguration configuration, IWebHostEnvironment environment)
{
    if (environment.IsDevelopment())
    {
        return;
    }

    var requiredKeys = new[]
    {
        "ReqSys:CorsOrigins:0",
        "ReqSys:Jwt:Issuer",
        "ReqSys:Jwt:Audience",
        "ReqSys:Jwt:Secret"
    };

    var missingKeys = requiredKeys
        .Where(key => string.IsNullOrWhiteSpace(configuration[key]))
        .ToArray();

    if (missingKeys.Length > 0)
    {
        throw new InvalidOperationException($"Configuracao obrigatoria ausente para ambiente {environment.EnvironmentName}: {string.Join(", ", missingKeys)}");
    }

    var jwtSecret = configuration["ReqSys:Jwt:Secret"];
    if (jwtSecret is not null && jwtSecret.Length < 32)
    {
        throw new InvalidOperationException("ReqSys:Jwt:Secret deve possuir pelo menos 32 caracteres.");
    }
}

public partial class Program;
