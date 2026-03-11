$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
Add-Type -AssemblyName System.Windows.Forms

$pythonExe = "python"
if (Test-Path ".\.venv\Scripts\python.exe") { $pythonExe = ".\.venv\Scripts\python.exe" }
if (Test-Path ".\venv\Scripts\python.exe") { $pythonExe = ".\venv\Scripts\python.exe" }

try {
    $null = & $pythonExe --version
} catch {
    [System.Windows.Forms.MessageBox]::Show(
        "Python not found. Please install Python or create venv/.venv first.",
        "Startup Error",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    exit 1
}

& $pythonExe web_launcher.py
if ($LASTEXITCODE -ne 0) {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(
        "GUI launcher failed. Please check dependencies (tkinter / uvicorn).",
        "Startup Error",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    exit 1
}
