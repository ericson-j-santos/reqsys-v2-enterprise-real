FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY Directory.Build.props ./
COPY src/ReqSys.Api/ReqSys.Api.csproj src/ReqSys.Api/
RUN dotnet restore src/ReqSys.Api/ReqSys.Api.csproj
COPY src/ReqSys.Api src/ReqSys.Api
RUN dotnet publish src/ReqSys.Api/ReqSys.Api.csproj -c Release -o /app/publish --no-restore /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 64198 reqsys \
    && useradd --system --uid 64198 --gid reqsys --home-dir /app --shell /usr/sbin/nologin reqsys
COPY --from=build /app/publish .
ENV ASPNETCORE_URLS=http://+:8080 \
    ASPNETCORE_ENVIRONMENT=Production \
    DOTNET_EnableDiagnostics=0 \
    DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=false
EXPOSE 8080
USER reqsys:reqsys
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail --silent --show-error http://localhost:8080/ready || exit 1
ENTRYPOINT ["dotnet", "ReqSys.Api.dll"]
