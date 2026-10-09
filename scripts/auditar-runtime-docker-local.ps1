[CmdletBinding()]
param(
    [string]$OutputDirectory = "",
    [int]$RestartThreshold = 3,
    [switch]$FailOnCritical
)

$ErrorActionPreference = 'Stop'

function Convert-DockerDesktopHostPath {
    [CmdletBinding()]
    param(
        [AllowNull()]
        [AllowEmptyString()]
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $Path
    }

    $candidate = $Path.Trim()
    if ($candidate -match '^/(?:run/desktop/mnt/host|host_mnt)/([A-Za-z])(?:/(.*))?$') {
        $drive = $Matches[1].ToUpperInvariant()
        $relativePath = [string]$Matches[2]
        if ([string]::IsNullOrWhiteSpace($relativePath)) {
            return ('{0}:\' -f $drive)
        }

        return ('{0}:\{1}' -f $drive, ($relativePath -replace '/', '\'))
    }

    return $candidate
}

function Get-LocalPathKind {
    [CmdletBinding()]
    param(
        [AllowNull()]
        [AllowEmptyString()]
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return 'missing'
    }

    try {
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            return 'file'
        }
        if (Test-Path -LiteralPath $Path -PathType Container) {
            return 'directory'
        }
        if (Test-Path -LiteralPath $Path) {
            return 'other'
        }
    }
    catch {
        return 'unreadable'
    }

    return 'missing'
}

function Get-ExpectedBindSourceKind {
    [CmdletBinding()]
    param(
        [AllowNull()]
        [AllowEmptyString()]
        [string]$Destination
    )

    if ([string]::IsNullOrWhiteSpace($Destination)) {
        return $null
    }

    $leaf = ($Destination.TrimEnd('/', '\') -split '[/\\]')[-1]
    if ($leaf -match '^(?i:Caddyfile|Dockerfile|Makefile)$') {
        return 'file'
    }

    $extension = [System.IO.Path]::GetExtension($leaf).ToLowerInvariant()
    $knownFileExtensions = @(
        '.conf', '.crt', '.env', '.ini', '.js', '.json', '.key', '.pem',
        '.ps1', '.sh', '.sql', '.toml', '.ts', '.txt', '.xml', '.yaml', '.yml'
    )
    if ($extension -in $knownFileExtensions) {
        return 'file'
    }

    # Sem um sinal inequivoco, nao presumimos que o destino seja diretorio.
    # Isso evita classificar incorretamente diretorios com ponto no nome.
    return $null
}

function Convert-ToArtifactPathAlias {
    [CmdletBinding()]
    param(
        [AllowNull()]
        [AllowEmptyString()]
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $Path
    }

    $normalizedPath = Convert-DockerDesktopHostPath -Path $Path
    $hashAlgorithm = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($normalizedPath.ToLowerInvariant())
        $hash = $hashAlgorithm.ComputeHash($bytes)
        $shortHash = -join ($hash[0..5] | ForEach-Object { $_.ToString('x2') })
    }
    finally {
        $hashAlgorithm.Dispose()
    }

    $leaf = [System.IO.Path]::GetFileName($normalizedPath.TrimEnd('/', '\'))
    if ([string]::IsNullOrWhiteSpace($leaf) -or $leaf -ieq $env:USERNAME) {
        $leaf = 'path'
    }
    $safeLeaf = (Protect-ArtifactText -Value $leaf) -replace '[^A-Za-z0-9._-]', '_'
    return "<LOCAL_PATH:$shortHash>/$safeLeaf"
}

function Protect-ArtifactText {
    [CmdletBinding()]
    param(
        [AllowNull()]
        [AllowEmptyString()]
        [string]$Value
    )

    if ($null -eq $Value) {
        return $null
    }

    $protected = $Value
    foreach ($sensitiveValue in @($env:COMPUTERNAME, $env:USERNAME)) {
        if (-not [string]::IsNullOrWhiteSpace($sensitiveValue)) {
            $protected = $protected -replace [regex]::Escape($sensitiveValue), '<REDACTED>'
        }
    }
    return $protected
}

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $PSScriptRoot '..\artifacts\local-docker-runtime-audit'
}

$null = docker version --format '{{.Server.Version}}' 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'Docker Engine indisponivel; auditoria nao executada.'
}

$collectionStartedAtUtc = (Get-Date).ToUniversalTime()

$containerIds = @(docker ps -aq)
if ($LASTEXITCODE -ne 0) {
    throw 'Falha ao listar containers Docker.'
}

$inspectItems = @()
if ($containerIds.Count -gt 0) {
    $inspectJson = docker inspect @containerIds
    if ($LASTEXITCODE -ne 0) {
        throw 'Falha ao inspecionar containers Docker.'
    }
    $inspectItems = @($inspectJson | ConvertFrom-Json)
}

$statsByName = @{}
foreach ($line in @(docker stats --no-stream --format '{{json .}}')) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    try {
        $stat = $line | ConvertFrom-Json
        $statsByName[$stat.Name] = $stat
    }
    catch {
        # Uma linha de stats malformada nao deve invalidar o inventario estrutural.
    }
}

$signaturePatterns = [ordered]@{
    'package-json-missing' = '(?i)(/app/package\.json|Could not read package\.json|ENOENT.*package\.json)'
    'cloudflare-tunnel-not-found' = '(?i)(Unauthorized:\s*Tunnel not found|Tunnel not found)'
    'connection-refused' = '(?i)(Connection refused|connection refused)'
}

$containers = @(
    foreach ($item in $inspectItems) {
        $name = $item.Name.TrimStart('/')
        $labels = $item.Config.Labels
        $project = if ($labels) { $labels.'com.docker.compose.project' } else { $null }
        $service = if ($labels) { $labels.'com.docker.compose.service' } else { $null }
        $composeLabel = if ($labels) { $labels.'com.docker.compose.project.config_files' } else { $null }
        $composeFiles = @(
            if (-not [string]::IsNullOrWhiteSpace($composeLabel)) {
                $composeLabel -split ',' |
                    ForEach-Object { Convert-DockerDesktopHostPath -Path $_.Trim() } |
                    Where-Object { $_ }
            }
        )
        $missingComposeFiles = @(
            $composeFiles | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) }
        )
        $bindMountIssues = @(
            foreach ($mount in @($item.Mounts)) {
                if ($mount.Type -ne 'bind') {
                    continue
                }

                $hostSource = Convert-DockerDesktopHostPath -Path $mount.Source
                $actualKind = Get-LocalPathKind -Path $hostSource
                $expectedKind = Get-ExpectedBindSourceKind -Destination $mount.Destination
                $code = $null
                if ($actualKind -eq 'missing') {
                    $code = 'missing-bind-source'
                }
                elseif ($actualKind -eq 'unreadable') {
                    $code = 'unreadable-bind-source'
                }
                elseif ($expectedKind -and $actualKind -ne $expectedKind) {
                    $code = 'bind-source-type-mismatch'
                }

                if ($code) {
                    [PSCustomObject]@{
                        code = $code
                        source = Convert-ToArtifactPathAlias -Path $hostSource
                        destination = Protect-ArtifactText -Value ([string]$mount.Destination)
                        expected_type = if ($expectedKind) { $expectedKind } else { 'unspecified' }
                        actual_type = $actualKind
                        docker_desktop_path_normalized = ([string]$mount.Source -ne $hostSource)
                    }
                }
            }
        )
        $missingBindSources = @(
            $bindMountIssues |
                Where-Object code -eq 'missing-bind-source' |
                ForEach-Object source
        )
        $typeMismatchedBindSources = @(
            $bindMountIssues | Where-Object code -eq 'bind-source-type-mismatch'
        )
        $artifactComposeFiles = @($composeFiles | ForEach-Object { Convert-ToArtifactPathAlias -Path $_ })
        $artifactMissingComposeFiles = @($missingComposeFiles | ForEach-Object { Convert-ToArtifactPathAlias -Path $_ })

        $health = if ($item.State.Health) { $item.State.Health.Status } else { $null }
        $status = $item.State.Status
        $restartPolicy = $item.HostConfig.RestartPolicy.Name
        $restartCount = [int64]$item.RestartCount
        $command = (@($item.Config.Entrypoint) + @($item.Config.Cmd)) -join ' '
        $isDevWatcher = $command -match '(?i)(--reload|npm\s+run\s+dev|vite)'
        $hasResourceLimits = (
            [int64]$item.HostConfig.Memory -gt 0 -or
            [int64]$item.HostConfig.NanoCpus -gt 0 -or
            [int64]$item.HostConfig.CpuQuota -gt 0 -or
            [int64]$item.HostConfig.PidsLimit -gt 0
        )
        $logDriver = $item.HostConfig.LogConfig.Type
        $logOptions = $item.HostConfig.LogConfig.Config
        $hasLogRotation = (
            $logDriver -ne 'json-file' -or
            ($logOptions -and $logOptions.'max-size' -and $logOptions.'max-file')
        )

        $signatureCounts = [ordered]@{}
        if ($status -in @('running', 'restarting') -or $restartCount -ge $RestartThreshold -or $health -eq 'unhealthy') {
            $logLines = @(docker logs --since 30m --tail 500 $name 2>&1)
            foreach ($signature in $signaturePatterns.GetEnumerator()) {
                $count = @($logLines | Select-String -Pattern $signature.Value).Count
                if ($count -gt 0) {
                    $signatureCounts[$signature.Key] = $count
                }
            }
        }

        $findings = [System.Collections.Generic.List[object]]::new()
        if ($status -eq 'restarting' -or ($status -eq 'running' -and $restartCount -ge $RestartThreshold)) {
            $findings.Add([PSCustomObject]@{ Severity = 'critical'; Code = 'restart-loop'; Detail = "status=$status; restart_count=$restartCount" })
        }
        elseif ($restartCount -ge $RestartThreshold) {
            $findings.Add([PSCustomObject]@{ Severity = 'high'; Code = 'historical-restart-storm'; Detail = "state=$status; restart_count=$restartCount" })
        }
        if ($health -eq 'unhealthy') {
            $severity = if ($status -eq 'running') { 'critical' } else { 'high' }
            $findings.Add([PSCustomObject]@{ Severity = $severity; Code = 'unhealthy'; Detail = "state=$status; health=unhealthy" })
        }
        foreach ($issue in $bindMountIssues) {
            $severity = if ($status -in @('running', 'restarting')) { 'critical' } else { 'high' }
            $detail = "source=$($issue.source); destination=$($issue.destination); expected=$($issue.expected_type); actual=$($issue.actual_type)"
            $findings.Add([PSCustomObject]@{ Severity = $severity; Code = $issue.code; Detail = $detail })
        }
        foreach ($path in $artifactMissingComposeFiles) {
            $findings.Add([PSCustomObject]@{ Severity = 'high'; Code = 'missing-compose-file'; Detail = $path })
        }
        if ($restartPolicy -in @('always', 'unless-stopped') -and ($project -match '(?i)(dev|test)' -or $isDevWatcher)) {
            $artifactProject = Protect-ArtifactText -Value $project
            $findings.Add([PSCustomObject]@{ Severity = 'high'; Code = 'persistent-dev-restart'; Detail = "project=$artifactProject; policy=$restartPolicy" })
        }
        if ($signatureCounts.Contains('package-json-missing')) {
            $isActive = $status -in @('running', 'restarting')
            $severity = if ($isActive) { 'critical' } else { 'high' }
            $code = if ($isActive) { 'package-json-missing' } else { 'historical-package-json-missing' }
            $findings.Add([PSCustomObject]@{ Severity = $severity; Code = $code; Detail = "state=$status; matches_30m=$($signatureCounts['package-json-missing'])" })
        }
        if ($signatureCounts.Contains('cloudflare-tunnel-not-found')) {
            $findings.Add([PSCustomObject]@{ Severity = 'critical'; Code = 'cloudflare-tunnel-not-found'; Detail = "matches_30m=$($signatureCounts['cloudflare-tunnel-not-found'])" })
        }
        if ($signatureCounts.Contains('connection-refused') -and $health -eq 'unhealthy') {
            $findings.Add([PSCustomObject]@{ Severity = 'high'; Code = 'connection-refused'; Detail = "matches_30m=$($signatureCounts['connection-refused'])" })
        }

        $stat = $statsByName[$name]
        [PSCustomObject]@{
            name = Protect-ArtifactText -Value $name
            project = Protect-ArtifactText -Value $project
            service = Protect-ArtifactText -Value $service
            image = Protect-ArtifactText -Value $item.Config.Image
            state = $status
            health = $health
            exit_code = $item.State.ExitCode
            restart_count = $restartCount
            restart_policy = $restartPolicy
            created_at = $item.Created
            started_at = $item.State.StartedAt
            finished_at = $item.State.FinishedAt
            cpu = if ($stat) { $stat.CPUPerc } else { $null }
            memory = if ($stat) { $stat.MemUsage } else { $null }
            dev_watcher = $isDevWatcher
            has_resource_limits = $hasResourceLimits
            log_driver = $logDriver
            has_log_rotation = $hasLogRotation
            compose_files = $artifactComposeFiles
            missing_compose_files = $artifactMissingComposeFiles
            missing_bind_sources = $missingBindSources
            type_mismatched_bind_sources = $typeMismatchedBindSources
            bind_mount_issues = $bindMountIssues
            log_signatures_30m = $signatureCounts
            findings = @($findings)
        }
    }
)

$allFindings = @(
    foreach ($container in $containers) {
        foreach ($finding in @($container.findings)) {
            [PSCustomObject]@{
                container = $container.name
                project = $container.project
                state = $container.state
                severity = $finding.Severity
                code = $finding.Code
                detail = $finding.Detail
            }
        }
    }
)

$summary = [ordered]@{
    total_containers = $containers.Count
    running = @($containers | Where-Object state -eq 'running').Count
    restarting = @($containers | Where-Object state -eq 'restarting').Count
    running_unhealthy = @($containers | Where-Object { $_.state -eq 'running' -and $_.health -eq 'unhealthy' }).Count
    historical_unhealthy = @($containers | Where-Object { $_.state -ne 'running' -and $_.health -eq 'unhealthy' }).Count
    running_without_resource_limits = @($containers | Where-Object { $_.state -eq 'running' -and -not $_.has_resource_limits }).Count
    running_json_file_without_rotation = @($containers | Where-Object { $_.state -eq 'running' -and $_.log_driver -eq 'json-file' -and -not $_.has_log_rotation }).Count
    running_with_missing_compose = @($containers | Where-Object { $_.state -eq 'running' -and @($_.missing_compose_files).Count -gt 0 }).Count
    missing_bind_sources = @($containers | ForEach-Object { @($_.bind_mount_issues) } | Where-Object code -eq 'missing-bind-source').Count
    bind_source_type_mismatches = @($containers | ForEach-Object { @($_.bind_mount_issues) } | Where-Object code -eq 'bind-source-type-mismatch').Count
    critical_findings = @($allFindings | Where-Object severity -eq 'critical').Count
    high_findings = @($allFindings | Where-Object severity -eq 'high').Count
}

$collectionFinishedAtUtc = (Get-Date).ToUniversalTime()
$report = [ordered]@{
    schema_version = 2
    generated_at_utc = $collectionFinishedAtUtc.ToString('o')
    collection_started_at_utc = $collectionStartedAtUtc.ToString('o')
    collection_finished_at_utc = $collectionFinishedAtUtc.ToString('o')
    log_lookback_minutes = 30
    host_scope = 'local-workstation-redacted'
    path_alias_scheme = 'sha256-prefix-12-and-leaf'
    restart_threshold = $RestartThreshold
    summary = $summary
    findings = $allFindings
    containers = $containers
}

$null = New-Item -ItemType Directory -Path $OutputDirectory -Force
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$jsonPath = Join-Path $OutputDirectory "docker-runtime-audit-$stamp.json"
$markdownPath = Join-Path $OutputDirectory "docker-runtime-audit-$stamp.md"

$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = [System.Collections.Generic.List[string]]::new()
$markdown.Add('# Auditoria local do runtime Docker')
$markdown.Add('')
$markdown.Add("- Gerado em UTC: $($report.generated_at_utc)")
$markdown.Add("- Janela de coleta UTC: $($report.collection_started_at_utc) a $($report.collection_finished_at_utc)")
$markdown.Add("- Logs: contagens em janelas moveis de $($report.log_lookback_minutes) minutos observadas durante a coleta")
$markdown.Add('- Escopo: estacao local; hostname, username e caminhos absolutos redigidos')
$markdown.Add('- Caminhos locais: aliases estaveis no formato <LOCAL_PATH:hash>/nome')
$markdown.Add("- Containers: $($summary.total_containers) total; $($summary.running) ativos; $($summary.restarting) reiniciando; $($summary.running_unhealthy) ativos unhealthy")
$markdown.Add("- Ativos sem limites de recurso: $($summary.running_without_resource_limits); sem rotacao json-file: $($summary.running_json_file_without_rotation); com Compose ausente: $($summary.running_with_missing_compose)")
$markdown.Add("- Binds: $($summary.missing_bind_sources) origens ausentes; $($summary.bind_source_type_mismatches) incompatibilidades de tipo")
$markdown.Add("- Achados: $($summary.critical_findings) criticos; $($summary.high_findings) altos")
$markdown.Add('')
$markdown.Add('| Severidade | Container | Projeto | Estado | Codigo | Detalhe |')
$markdown.Add('| --- | --- | --- | --- | --- | --- |')
foreach ($finding in $allFindings | Sort-Object @{ Expression = { if ($_.severity -eq 'critical') { 0 } else { 1 } } }, project, container, code) {
    $detail = ([string]$finding.detail).Replace('|', '\|').Replace("`r", ' ').Replace("`n", ' ')
    $markdown.Add("| $($finding.severity) | $($finding.container) | $($finding.project) | $($finding.state) | $($finding.code) | $detail |")
}
$markdown | Set-Content -LiteralPath $markdownPath -Encoding UTF8

Write-Host "Auditoria JSON: $jsonPath"
Write-Host "Auditoria Markdown: $markdownPath"
Write-Host "Criticos: $($summary.critical_findings); altos: $($summary.high_findings)"

if ($FailOnCritical -and $summary.critical_findings -gt 0) {
    exit 1
}
