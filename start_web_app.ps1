$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$port = 8001
if ($args.Count -gt 0 -and $args[0] -ne "--check") {
    $port = [int]$args[0]
}

$pythonExe = "python"
if (Test-Path ".\.venv\Scripts\python.exe") { $pythonExe = ".\.venv\Scripts\python.exe" }
if (Test-Path ".\venv\Scripts\python.exe") { $pythonExe = ".\venv\Scripts\python.exe" }

if ($args.Count -gt 0 -and $args[0] -eq "--check") {
    Write-Host "PROJECT_DIR=$PWD"
    Write-Host "PYTHON_EXE=$pythonExe"
    Write-Host "DEFAULT_PORT=8001"
    exit 0
}

try {
    $null = & $pythonExe --version
} catch {
    Write-Host "Python not found. Please install Python or create venv/.venv first."
    Read-Host "Press Enter to exit"
    exit 1
}

$lanIp = $null
try {
    $lanIp = Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.IPAddress -notlike '169.254*' -and $_.InterfaceAlias -notmatch 'Loopback|vEthernet|VirtualBox|VMware' } |
        Select-Object -First 1 -ExpandProperty IPAddress
} catch {
    $lanIp = $null
}
if ([string]::IsNullOrWhiteSpace($lanIp)) { $lanIp = "127.0.0.1" }

Write-Host ""
Write-Host "=============================="
Write-Host "Microbial Colony Counter Web App Launcher"
Write-Host "Project: $PWD"
Write-Host "Python: $pythonExe"
Write-Host "Local URL: http://127.0.0.1:$port/"
Write-Host "LAN URL:   http://$lanIp`:$port/"
Write-Host "=============================="
Write-Host ""

& $pythonExe -m uvicorn backend.main:app --host 0.0.0.0 --port $port
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Startup failed. Check port usage or dependency installation."
    Read-Host "Press Enter to exit"
    exit 1
}
