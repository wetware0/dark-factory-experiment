param(
    [Parameter(Mandatory = $false, Position = 0)]
    [ValidateSet("start", "stop", "restart", "status")]
    [string] $Action = "status",

    [string] $BoardName = "Peter's Board",
    [string] $StaffCode = "C50",
    [string] $GuardianStaffCode = "PWS",
    [bool] $ScoutDryRun = $true,
    [bool] $ArchonExecute = $false,
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
        Stop-Process -Id $ProcessId -Force
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

    $token = Get-WorkerToken
    $logPath = Get-LogPath $Name
    $escapedCommand = @"
`$env:FACTORY_WORKER_TOKEN = '$token'
`$env:PAVE_BOARD_NAME = '$BoardName'
`$env:PAVE_STAFF_CODE = '$StaffCode'
`$env:PAVE_GUARDIAN_STAFF_CODE = '$GuardianStaffCode'
`$env:FACTORY_SCOUT_DRY_RUN = '$ScoutDryRun'
`$env:FACTORY_ARCHON_EXECUTE = '$ArchonExecute'
`$env:FACTORY_API_BASE = 'http://127.0.0.1:$BackendPort/api'
`$env:VITE_API_BASE = '/api'
$Command *> '$logPath'
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
    if (-not (Test-DatabaseConfigured)) {
        throw "DATABASE_URL is not configured. The existing DynaChat backend still requires it before starting services."
    }
    if (-not (Test-FactoryStorageConfigured)) {
        throw "Factory storage is not configured. Set FACTORY_SQLSERVER_CONNECTION_STRING for SQL Server or FACTORY_STORAGE_PROVIDER=postgres with DATABASE_URL."
    }

    $appDir = Join-Path $RepoRoot "app"
    $frontendDir = Join-Path $RepoRoot "app/frontend"

    Start-FactoryService `
        -Name "backend" `
        -WorkingDirectory $appDir `
        -Command "uv --project backend run uvicorn backend.main:app --reload --host 127.0.0.1 --port $BackendPort"

    Start-FactoryService `
        -Name "frontend" `
        -WorkingDirectory $frontendDir `
        -Command "bun run dev --host 127.0.0.1 --port $FrontendPort"

    Start-FactoryService `
        -Name "scout" `
        -WorkingDirectory $appDir `
        -Command "uv --project backend run python -m backend.factory.worker --board-name '$BoardName' --staff-code '$StaffCode' --guardian-staff-code '$GuardianStaffCode'"

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
