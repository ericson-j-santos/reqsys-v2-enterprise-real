FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY Directory.Build.props ./
COPY src/ReqSys.Api/ReqSys.Api.csproj src/ReqSys.Api/
RUN dotnet restore src/ReqSys.Api/ReqSys.Api.csproj
COPY src/ReqSys.Api src/ReqSys.Api
RUN dotnet publish src/ReqSys.Api/ReqSys.Api.csproj -c Release -o /app/publish --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /app/publish .
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080
ENTRYPOINT ["dotnet", "ReqSys.Api.dll"]
