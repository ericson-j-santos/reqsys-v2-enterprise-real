using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.Data.SqlClient;

static string Hash16(string value)
{
    var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
    return Convert.ToHexString(bytes).ToLowerInvariant()[..16];
}

static bool SafeName(string value) => Regex.IsMatch(value, @"^[A-Za-z0-9_.\\-]+$");

if (args.Length != 2 || !SafeName(args[0]) || !SafeName(args[1]))
{
    Console.WriteLine(JsonSerializer.Serialize(new {
        schema_version = "1.0.0",
        feature = "movimento_email_source_readonly_probe_dotnet",
        connected = false,
        passed = false,
        error_type = "invalid_arguments"
    }));
    return 2;
}

var server = args[0];
var database = args[1];
var evidence = new Dictionary<string, object?>
{
    ["schema_version"] = "1.0.0",
    ["feature"] = "movimento_email_source_readonly_probe_dotnet",
    ["source_server_hash"] = Hash16(server),
    ["source_database_hash"] = Hash16(database),
    ["provider"] = "Microsoft.Data.SqlClient",
    ["auth"] = "windows_integrated",
    ["encrypt"] = true,
    ["trust_server_certificate"] = false,
    ["application_intent"] = "ReadOnly",
    ["secret_used"] = false,
    ["write_attempted"] = false,
    ["connected"] = false,
    ["candidate_objects"] = Array.Empty<string>(),
    ["expected_function_present"] = false,
    ["passed"] = false
};

try
{
    var builder = new SqlConnectionStringBuilder
    {
        DataSource = server,
        InitialCatalog = database,
        IntegratedSecurity = true,
        Encrypt = true,
        TrustServerCertificate = false,
        ApplicationIntent = ApplicationIntent.ReadOnly,
        ConnectTimeout = 8
    };

    await using var connection = new SqlConnection(builder.ConnectionString);
    await connection.OpenAsync();

    await using (var command = connection.CreateCommand())
    {
        command.CommandText =
            "SELECT CAST(SERVERPROPERTY('ServerName') AS nvarchar(256)), DB_NAME(), " +
            "CAST(DATABASEPROPERTYEX(DB_NAME(),'Updateability') AS nvarchar(60))";
        await using var reader = await command.ExecuteReaderAsync();
        if (await reader.ReadAsync())
        {
            evidence["connected"] = true;
            evidence["resolved_server_hash"] = Hash16(reader.IsDBNull(0) ? "" : reader.GetString(0));
            evidence["resolved_database_hash"] = Hash16(reader.IsDBNull(1) ? "" : reader.GetString(1));
            evidence["database_updateability"] = reader.IsDBNull(2) ? "" : reader.GetString(2);
        }
    }

    var candidates = new List<string>();
    await using (var command = connection.CreateCommand())
    {
        command.CommandText =
            "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE " +
            "FROM INFORMATION_SCHEMA.TABLES ORDER BY TABLE_SCHEMA, TABLE_NAME";
        await using var reader = await command.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            var schema = reader.GetString(0);
            var name = reader.GetString(1);
            var kind = reader.GetString(2);
            var lower = name.ToLowerInvariant();
            if (new[] { "prospec", "movimento", "pendenc", "fechamento", "consign", "portab" }.Any(lower.Contains))
            {
                candidates.Add($"{schema}.{name}:{kind}");
                if (candidates.Count >= 100) break;
            }
        }
    }
    evidence["candidate_objects"] = candidates;

    await using (var command = connection.CreateCommand())
    {
        command.CommandText =
            "SELECT CASE WHEN OBJECT_ID(N'CNS.PROSPECCAO_FN001_PAINEL_FLUXO_INTRADIA') " +
            "IS NULL THEN 0 ELSE 1 END";
        evidence["expected_function_present"] = Convert.ToInt32(await command.ExecuteScalarAsync()) == 1;
    }

    evidence["passed"] =
        (bool)evidence["connected"]! &&
        ((bool)evidence["expected_function_present"]! || candidates.Count > 0);

    Console.WriteLine(JsonSerializer.Serialize(evidence));
    return (bool)evidence["passed"]! ? 0 : 3;
}
catch (SqlException ex)
{
    evidence["error_type"] = nameof(SqlException);
    evidence["sql_error_number"] = ex.Number;
    evidence["sql_error_class"] = ex.Class;
    Console.WriteLine(JsonSerializer.Serialize(evidence));
    return 2;
}
catch (Exception ex)
{
    evidence["error_type"] = ex.GetType().Name;
    Console.WriteLine(JsonSerializer.Serialize(evidence));
    return 2;
}
