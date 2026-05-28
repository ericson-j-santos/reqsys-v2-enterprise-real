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
        policy.WithOrigins(origins)
            .AllowAnyHeader()
            .AllowAnyMethod()
            .AllowCredentials();
    });
});

var app = builder.Build();

app.UseCors("ReqSysCors");
app.Use(async (context, next) =>
{
    context.Response.Headers.TryAdd("X-Request-ID", context.TraceIdentifier);
    await next();
});

app.MapHealthChecks("/healthz");
app.MapReqSysEndpoints();

app.Run();

public partial class Program;
