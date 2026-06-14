using System.Security.Cryptography;
using System.Text;
using ReqSys.Api.Domain;

namespace ReqSys.Api.Services;

public sealed class AuthService
{
    private static readonly Usuario Admin = new(
        "usr-admin",
        "Administrador ReqSys",
        "admin@reqsys.local",
        "gestor",
        new[] { "requisito:write", "pipeline:execute", "auditoria:read", "relatorio:read" });

    public LoginResponse? Login(LoginRequest request)
    {
        var demoEmails = new[]
        {
            Admin.Email,
            "ericsonjosedossantos@tieri659.onmicrosoft.com"
        };

        if (!demoEmails.Contains(request.Email, StringComparer.OrdinalIgnoreCase) || request.Senha != "admin123")
        {
            return null;
        }

        var expiraEm = DateTimeOffset.UtcNow.AddHours(8);
        var tokenPayload = $"{Admin.Email}|{expiraEm:O}|ReqSys.DotNet";
        var token = Convert.ToBase64String(SHA256.HashData(Encoding.UTF8.GetBytes(tokenPayload)));
        return new LoginResponse(token, Admin, expiraEm);
    }
}
