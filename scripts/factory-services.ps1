param(
    [Parameter(Mandatory = $false, Position = 0)]
    [ValidateSet("start", "stop", "restart", "status")]
    [string] $Action = "status",

    [string] $BoardName = "Peter's Board",
    [string] $StaffCode = "C50",
    [string] $GuardianStaffCode = "PWS",
    [bool] $ScoutDryRun = $true,
    [bool] $ArchonExecute = $false,
    [bool] $FactoryApiOnly = $true,
    [int] $BackendPort = 8000,
    [int] $FrontendPort = 5173
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$FactoryDir = Join-Path $RepoRoot ".factory"
$PidDir = Join-Path $FactoryDir "pids"
$LogDir = Join-Path $FactoryDir "logs"
$TokenPath = Join-Path $FactoryDir "factory-worker-token.txt"

function Ensure-FactoryDirs {
    New-Item -ItemType Directory -Force -Path $FactoryDir | Out-Null
    New-Item -ItemType Directory -Force -Path $PidDir | Out-Null
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}

function Get-WorkerToken {
    Ensure-FactoryDirs
    if (-not (Test-Path -LiteralPath $TokenPath)) {
        $bytes = [System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32)
        [Convert]::ToBase64String($bytes) | Set-Content -LiteralPath $TokenPath -Encoding ascii
    }
    return (Get-Content -LiteralPath $TokenPath -Raw).Trim()
}

function Get-PidPath([string] $Name) {
    return Join-Path $PidDir "$Name.pid"
}

function Get-LogPath([string] $Name) {
    return Join-Path $LogDir "$Name.log"
}

function ConvertTo-PowerShellSingleQuotedLiteral([string] $Value) {
    if ($null -eq $Value) {
        $Value = ""
    }
    return "'" + ($Value -replace "'", "''") + "'"
}

function New-EnvAssignment([string] $Name, [string] $Value) {
    return '$env:' + $Name + ' = ' + (ConvertTo-PowerShellSingleQuotedLiteral $Value)
}

function Get-ConfiguredValue([string] $Name, [string] $Default = "") {
    $envValue = [Environment]::GetEnvironmentVariable($Name)
    if ($envValue) {
        return $envValue
    }
    foreach ($candidate in @(
        (Join-Path $RepoRoot ".env"),
        (Join-Path $RepoRoot "app/.env"),
        (Join-Path $RepoRoot "app/backend/.env")
    )) {
        if (Test-Path -LiteralPath $candidate) {
            $match = Select-String -LiteralPath $candidate -Pattern "^\s*$Name\s*=\s*(.*)\s*$" | Select-Object -First 1
            if ($match) {
                return ($match.Matches[0].Groups[1].Value).Trim().Trim('"').Trim("'")
            }
        }
    }
    return $Default
}

function Test-DatabaseConfigured {
    return [bool] (Get-ConfiguredValue "DATABASE_URL")
}

function Test-FactoryApiOnly {
    $value = (Get-ConfiguredValue "FACTORY_API_ONLY" ([string] $FactoryApiOnly)).Trim().ToLowerInvariant()
    return $value -in @("1", "true", "yes", "on")
}

function Test-FactoryStorageConfigured {
    $provider = (Get-ConfiguredValue "FACTORY_STORAGE_PROVIDER" "sqlserver").ToLowerInvariant()
    if ($provider -in @("sqlserver", "mssql", "sql_server")) {
        return [bool] (Get-ConfiguredValue "FACTORY_SQLSERVER_CONNECTION_STRING")
    }
    if ($provider -in @("postgres", "postgresql")) {
        return [bool] (Get-ConfiguredValue "DATABASE_URL")
    }
    if ($provider -in @("sqlite", "sqlite3")) {
        return $true
    }
    return $false
}

function Test-ProcessRunning([int] $ProcessId) {
    try {
        $process = Get-Process -Id $ProcessId -ErrorAction Stop
        return -not $process.HasExited
    }
    catch {
        return $false
    }
}

function Stop-ProcessTree([int] $ProcessId) {
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Stop-ProcessTree -ProcessId ([int] $child.ProcessId)
    }
    if (Test-ProcessRunning $ProcessId) {
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Stop-MatchingFactoryProcesses([string] $Name) {
    $repoPattern = "*" + [string] $RepoRoot + "*"
    $patterns = switch ($Name) {
        "backend" {
            @(
                "*uvicorn backend.main:app*--port $BackendPort*"
            )
        }
        "frontend" {
            @(
                "*$RepoRoot*app*frontend*",
                "*vite*--port $FrontendPort*"
            )
        }
        "scout" {
            @(
                "*backend.factory.worker*--staff-code $StaffCode*",
                "*backend.factory.worker*--board-name*$BoardName*"
            )
        }
        default { @() }
    }
    if ($patterns.Count -eq 0) {
        return
    }

    $matches = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $commandLine = $_.CommandLine
        $executablePath = $_.ExecutablePath
        if (-not $commandLine) {
            return $false
        }
        if ([int] $_.ProcessId -eq $PID) {
            return $false
        }
        $isRepoLocal = ($commandLine -like $repoPattern) -or ($executablePath -like $repoPattern)
        $isServiceMatch = $false
        foreach ($pattern in $patterns) {
            if ($commandLine -like $pattern) {
                $isServiceMatch = $true
                break
            }
        }
        if (-not $isServiceMatch) {
            return $false
        }
        if ($Name -eq "scout") {
            return $true
        }
        return $isRepoLocal
    }

    foreach ($process in ($matches | Sort-Object ProcessId -Descending)) {
        Stop-ProcessTree -ProcessId ([int] $process.ProcessId)
    }
}

function Read-ServicePid([string] $Name) {
    $path = Get-PidPath $Name
    if (-not (Test-Path -LiteralPath $path)) {
        return $null
    }
    $raw = (Get-Content -LiteralPath $path -Raw).Trim()
    if (-not $raw) {
        return $null
    }
    return [int] $raw
}

function Start-FactoryService(
    [string] $Name,
    [string] $WorkingDirectory,
    [string] $Command
) {
    Ensure-FactoryDirs
    $existingPid = Read-ServicePid $Name
    if ($null -ne $existingPid -and (Test-ProcessRunning $existingPid)) {
        Write-Host "$Name already running (PID $existingPid)"
        return
    }
    Stop-MatchingFactoryProcesses $Name

    $token = Get-WorkerToken
    $logPath = Get-LogPath $Name
    $envLines = @(
        (New-EnvAssignment "FACTORY_WORKER_TOKEN" $token),
        (New-EnvAssignment "PAVE_BOARD_NAME" $BoardName),
        (New-EnvAssignment "PAVE_STAFF_CODE" $StaffCode),
        (New-EnvAssignment "PAVE_GUARDIAN_STAFF_CODE" $GuardianStaffCode),
        (New-EnvAssignment "FACTORY_SCOUT_DRY_RUN" ([string] $ScoutDryRun)),
        (New-EnvAssignment "FACTORY_ARCHON_EXECUTE" ([string] $ArchonExecute)),
        (New-EnvAssignment "FACTORY_API_ONLY" (Get-ConfiguredValue "FACTORY_API_ONLY" ([string] $FactoryApiOnly))),
        (New-EnvAssignment "FACTORY_ALLOW_OAUTH_STAFF_MISMATCH" (Get-ConfiguredValue "FACTORY_ALLOW_OAUTH_STAFF_MISMATCH" "false")),
        (New-EnvAssignment "FACTORY_STORAGE_PROVIDER" (Get-ConfiguredValue "FACTORY_STORAGE_PROVIDER" "sqlserver")),
        (New-EnvAssignment "FACTORY_SQLSERVER_CONNECTION_STRING" (Get-ConfiguredValue "FACTORY_SQLSERVER_CONNECTION_STRING")),
        (New-EnvAssignment "FACTORY_SQLITE_PATH" (Get-ConfiguredValue "FACTORY_SQLITE_PATH" ".factory/factory.sqlite3")),
        (New-EnvAssignment "FACTORY_API_BASE" "http://127.0.0.1:$BackendPort/api"),
        (New-EnvAssignment "VITE_API_BASE" "/api")
    )
    $databaseUrl = Get-ConfiguredValue "DATABASE_URL"
    if ($databaseUrl) {
        $envLines += New-EnvAssignment "DATABASE_URL" $databaseUrl
    }
    $jwtSecret = Get-ConfiguredValue "JWT_SECRET" "factory-local-jwt-secret"
    if ($jwtSecret) {
        $envLines += New-EnvAssignment "JWT_SECRET" $jwtSecret
    }
    $envBlock = $envLines -join "`r`n"
    $logLiteral = ConvertTo-PowerShellSingleQuotedLiteral $logPath
    $escapedCommand = @"
$envBlock
$Command *> $logLiteral
"@

    $process = Start-Process `
        -FilePath "powershell" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $escapedCommand) `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden `
        -PassThru

    $process.Id | Set-Content -LiteralPath (Get-PidPath $Name) -Encoding ascii
    Write-Host "Started $Name (PID $($process.Id)); log: $logPath"
}

function Stop-FactoryService([string] $Name) {
    $pidPath = Get-PidPath $Name
    $servicePid = Read-ServicePid $Name
    if ($null -eq $servicePid) {
        Write-Host "$Name is not running"
        return
    }
    if (Test-ProcessRunning $servicePid) {
        Stop-ProcessTree -ProcessId $servicePid
        Write-Host "Stopped $Name (PID $servicePid)"
    }
    else {
        Write-Host "$Name was not running (stale PID $servicePid)"
    }
    if (Test-Path -LiteralPath $pidPath) {
        Remove-Item -LiteralPath $pidPath
    }
    Stop-MatchingFactoryProcesses $Name
}

function Show-FactoryStatus {
    Ensure-FactoryDirs
    foreach ($name in @("backend", "frontend", "scout")) {
        $servicePid = Read-ServicePid $name
        if ($null -ne $servicePid -and (Test-ProcessRunning $servicePid)) {
            Write-Host ("{0,-8} running PID {1} log {2}" -f $name, $servicePid, (Get-LogPath $name))
        }
        elseif ($null -ne $servicePid) {
            Write-Host ("{0,-8} stopped stale PID {1} log {2}" -f $name, $servicePid, (Get-LogPath $name))
        }
        else {
            Write-Host ("{0,-8} stopped log {1}" -f $name, (Get-LogPath $name))
        }
    }
}

function Start-Factory {
    $factoryApiOnlyEnabled = Test-FactoryApiOnly
    if (-not $factoryApiOnlyEnabled -and -not (Test-DatabaseConfigured)) {
        throw "DATABASE_URL is not configured. The existing DynaChat backend still requires it before starting services."
    }
    if (-not (Test-FactoryStorageConfigured)) {
        throw "Factory storage is not configured. Set FACTORY_SQLSERVER_CONNECTION_STRING for SQL Server or FACTORY_STORAGE_PROVIDER=postgres with DATABASE_URL."
    }

    $appDir = Join-Path $RepoRoot "app"
    $frontendDir = Join-Path $RepoRoot "app/frontend"
    $backendCommand = "uv --project backend run uvicorn backend.main:app --host 127.0.0.1 --port $BackendPort"
    if (-not $factoryApiOnlyEnabled) {
        $backendCommand = "uv --project backend run uvicorn backend.main:app --reload --host 127.0.0.1 --port $BackendPort"
    }
    $boardArg = ConvertTo-PowerShellSingleQuotedLiteral $BoardName
    $staffArg = ConvertTo-PowerShellSingleQuotedLiteral $StaffCode
    $guardianArg = ConvertTo-PowerShellSingleQuotedLiteral $GuardianStaffCode

    Start-FactoryService `
        -Name "backend" `
        -WorkingDirectory $appDir `
        -Command $backendCommand

    Start-FactoryService `
        -Name "frontend" `
        -WorkingDirectory $frontendDir `
        -Command "bun run dev --host 127.0.0.1 --port $FrontendPort"

    Start-FactoryService `
        -Name "scout" `
        -WorkingDirectory $appDir `
        -Command "uv --project backend run python -m backend.factory.worker --board-name $boardArg --staff-code $staffArg --guardian-staff-code $guardianArg"

    Write-Host "Factory dashboard: http://127.0.0.1:$FrontendPort/factory"
}

switch ($Action) {
    "start" {
        Start-Factory
        Show-FactoryStatus
    }
    "stop" {
        Stop-FactoryService "scout"
        Stop-FactoryService "frontend"
        Stop-FactoryService "backend"
        Show-FactoryStatus
    }
    "restart" {
        Stop-FactoryService "scout"
        Stop-FactoryService "frontend"
        Stop-FactoryService "backend"
        Start-Factory
        Show-FactoryStatus
    }
    "status" {
        Show-FactoryStatus
    }
}
