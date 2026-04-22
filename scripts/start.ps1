#Requires -Version 5.1
# Yoke Agent - Windows launcher
# Checks ports 4040 / 4000, frees them if busy, installs deps if missing, then starts both servers.

$ErrorActionPreference = "Stop"

$root         = Split-Path -Parent $PSScriptRoot
$backendPort  = 4040
$frontendPort = 4000
$backendDir   = Join-Path $root "backend"
$frontendDir  = Join-Path $root "frontend"
$venvDir      = Join-Path $backendDir ".venv"
$venvPython   = Join-Path $venvDir "Scripts\python.exe"
$venvUvicorn  = Join-Path $venvDir "Scripts\uvicorn.exe"

function Write-Step { param($m) Write-Host "==> $m" -ForegroundColor Cyan }
function Write-Ok   { param($m) Write-Host "    $m" -ForegroundColor Green }
function Write-Warn { param($m) Write-Host "  ! $m" -ForegroundColor Yellow }
function Write-Err  { param($m) Write-Host "  x $m" -ForegroundColor Red }

function Free-Port {
    param([int]$Port, [string]$Label)
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { Write-Ok "$Label port $Port is free"; return }
    $procIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $procIds) {
        if ($procId -eq 0) { continue }
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        $name = if ($proc) { $proc.ProcessName } else { "unknown" }
        Write-Warn "$Label port $Port held by PID $procId ($name) - killing"
        try {
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Write-Ok "Killed PID $procId"
        } catch {
            Write-Err "Failed to kill PID $procId - $($_.Exception.Message)"
            exit 1
        }
    }
    Start-Sleep -Milliseconds 700
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        Write-Err "$Label port $Port still in use after kill - aborting"
        exit 1
    }
}

Write-Step "Checking prerequisites"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { Write-Err "python not found - install Python 3.10+"; exit 1 }
if (-not (Get-Command npm    -ErrorAction SilentlyContinue)) { Write-Err "npm not found - install Node.js";       exit 1 }
Write-Ok "python + npm available"

Write-Step "Checking ports"
Free-Port -Port $backendPort  -Label "Backend"
Free-Port -Port $frontendPort -Label "Frontend"

Write-Step "Preparing backend"
if (-not (Test-Path $venvPython)) {
    Write-Warn "Creating venv at $venvDir"
    python -m venv $venvDir
    & $venvPython -m pip install --upgrade pip --quiet
    & $venvPython -m pip install -r (Join-Path $backendDir "requirements.txt")
    Write-Ok "venv ready"
} else {
    Write-Ok "venv already exists"
}

$envFile    = Join-Path $backendDir ".env"
$envExample = Join-Path $backendDir ".env.example"
if ((-not (Test-Path $envFile)) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envFile
    Write-Warn "Created backend/.env from .env.example - remember to add your API keys"
}

Write-Step "Preparing frontend"
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Warn "Installing node_modules..."
    Push-Location $frontendDir
    try { npm install } finally { Pop-Location }
} else {
    Write-Ok "node_modules already exists"
}

Write-Step "Launching servers"
$backendCmd  = "title Yoke Backend && cd /d `"$backendDir`" && `"$venvUvicorn`" app.main:app --reload --port $backendPort --loop asyncio"
$frontendCmd = "title Yoke Frontend && cd /d `"$frontendDir`" && npm run dev"
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $backendCmd  | Out-Null
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $frontendCmd | Out-Null

Write-Host ""
Write-Ok "Backend  -> http://localhost:$backendPort"
Write-Ok "Frontend -> http://localhost:$frontendPort"
Write-Host ""
Write-Host "Two new console windows were opened. Close them (or Ctrl+C inside) to stop."
