$ErrorActionPreference = "SilentlyContinue"
Set-Location -Path $PSScriptRoot

$port = 8001
if ($args.Count -gt 0) {
    $port = [int]$args[0]
}

$listeners = Get-NetTCPConnection -State Listen -LocalPort $port
if (-not $listeners) {
    Write-Host "No listening process found on port $port."
    exit 0
}

$pids = $listeners | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($pid in $pids) {
    Write-Host "Stopping PID $pid on port $port ..."
    Stop-Process -Id $pid -Force
}

Write-Host "Done."
