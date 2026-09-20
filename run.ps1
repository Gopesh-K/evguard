<#
.SYNOPSIS
  One-command launcher for EVGuard (Windows).

.DESCRIPTION
  Creates .venv if missing, installs requirements.txt, starts the backend
  (http://127.0.0.1:8000), waits until /health answers, starts the dashboard
  (http://127.0.0.1:8501) and stops the backend when the dashboard exits.

  Usage:   .\run.ps1
  Options: -NoDashboard   start the backend, check /health, then stop (smoke test)
  Env:     EVGUARD_NO_BROWSER=1  do not open a browser;  EVGUARD_PORT=n  backend port (default 8000)
#>
param([switch]$NoDashboard)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$BackendHost = "127.0.0.1"
$BackendPort = if ($env:EVGUARD_PORT) { [int]$env:EVGUARD_PORT } else { 8000 }
$DashboardPort = 8501
$HealthUrl = "http://${BackendHost}:${BackendPort}/health"
$LogFile = Join-Path $PSScriptRoot "evguard-backend.log"

function Fail($message) {
    Write-Host ""
    Write-Host "ERROR: $message" -ForegroundColor Red
    exit 1
}

function Test-Health {
    try {
        $r = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2
        return ($r.status -eq "ok")
    } catch {
        return $false
    }
}

# ---- 1. Find Python 3.11 / 3.12 --------------------------------------------
function Find-Python {
    $candidates = @(
        @("py", "-3.12"), @("py", "-3.11"),
        @("python3.12"), @("python3.11"),
        @("python"), @("python3")
    )
    foreach ($c in $candidates) {
        if (-not (Get-Command $c[0] -ErrorAction SilentlyContinue)) { continue }
        $extra = @()
        if ($c.Length -gt 1) { $extra = $c[1..($c.Length - 1)] }
        try {
            $version = & $c[0] @extra -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        } catch { continue }
        if ($version -eq "3.12" -or $version -eq "3.11") {
            return ,@($c[0], $extra)
        }
    }
    return $null
}

$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    $found = Find-Python
    if (-not $found) {
        Fail ("Python 3.11 or 3.12 was not found. Install Python 3.12 from " +
              "https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), " +
              "then run .\run.ps1 again.")
    }
    Write-Host "Creating virtual environment (.venv)..."
    $exe = $found[0]; $extra = $found[1]
    & $exe @extra -m venv .venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) { Fail "Could not create .venv." }
}

# ---- 2. Install dependencies ------------------------------------------------
Write-Host "Installing requirements (first run can take a minute)..."
& $VenvPython -m pip install --disable-pip-version-check -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { Fail "pip install failed. Check your internet connection and try again." }

# ---- 3. Start the backend ---------------------------------------------------
$env:EVGUARD_MOCK = "0"
$env:EVGUARD_API_URL = "http://${BackendHost}:${BackendPort}"

$backend = $null
if (Test-Health) {
    Write-Host "An EVGuard backend is already running on port $BackendPort; reusing it."
} else {
    Write-Host "Starting EVGuard backend..."
    $backend = Start-Process -FilePath $VenvPython -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $LogFile -RedirectStandardError "$LogFile.err" `
        -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", $BackendHost, "--port", $BackendPort)
}

function Stop-Backend {
    if ($backend -and -not $backend.HasExited) {
        Write-Host "Stopping EVGuard backend..."
        & taskkill /PID $backend.Id /T /F 2>$null | Out-Null
    }
}

try {
    if ($backend) {
        $ready = $false
        for ($i = 0; $i -lt 60; $i++) {
            if ($backend.HasExited) { break }
            if (Test-Health) { $ready = $true; break }
            Start-Sleep -Milliseconds 500
        }
        if (-not $ready) {
            $tail = ""
            if (Test-Path "$LogFile.err") { $tail = (Get-Content "$LogFile.err" -Tail 15) -join "`n" }
            Stop-Backend
            Fail "The backend did not answer $HealthUrl within 30 seconds.`n$tail`nFull log: $LogFile.err"
        }
    }
    Write-Host "Backend is healthy: $HealthUrl"

    if ($NoDashboard) {
        Write-Host "-NoDashboard given: backend check passed."
        return
    }

    # ---- 4. Start the dashboard ---------------------------------------------
    # Headless: no first-run email prompt. We open the browser ourselves below.
    $DashboardUrl = "http://${BackendHost}:${DashboardPort}"
    Write-Host "Starting EVGuard dashboard..."
    $dashboard = Start-Process -FilePath $VenvPython -PassThru -NoNewWindow -ArgumentList @(
        "-m", "streamlit", "run", "dashboard/app.py",
        "--server.address", $BackendHost, "--server.port", $DashboardPort,
        "--server.headless", "true")

    $up = $false
    for ($i = 0; $i -lt 60; $i++) {
        if ($dashboard.HasExited) { break }
        try {
            if ((Invoke-RestMethod -Uri "$DashboardUrl/_stcore/health" -TimeoutSec 2) -eq "ok") { $up = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    if (-not $up) {
        Fail "The dashboard did not start on port $DashboardPort (is another program using it?)."
    }

    Write-Host "Open $DashboardUrl"
    if ($env:EVGUARD_NO_BROWSER -ne "1") {
        try { Start-Process $DashboardUrl } catch { Write-Host "(Could not open a browser automatically; open the URL above.)" }
    }
    Write-Host "Press Ctrl+C here to stop EVGuard."
    $dashboard.WaitForExit()
}
finally {
    if ($dashboard -and -not $dashboard.HasExited) { & taskkill /PID $dashboard.Id /T /F 2>$null | Out-Null }
    Stop-Backend
}
