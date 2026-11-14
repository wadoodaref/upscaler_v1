<#
    Upscaler Desktop v1 - Launcher script.

        .\run.ps1                 # Start desktop app
        .\run.ps1 -Doctor         # Run hardware diagnostics
#>

[CmdletBinding()]
param(
    [switch]$Doctor
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# 1. Prefer local .venv if present
$pyLocal  = Join-Path $root ".venv\Scripts\python.exe"
$pywLocal = Join-Path $root ".venv\Scripts\pythonw.exe"

# 2. Re-use existing sibling face_swap_v1 .venv if local doesn't exist
$pySibling = "E:\projects\face_swap_v1\.venv\Scripts\python.exe"
$pywSibling = "E:\projects\face_swap_v1\.venv\Scripts\pythonw.exe"

$py = $null
$pyw = $null

if (Test-Path $pyLocal) {
    $py = $pyLocal
    $pyw = if (Test-Path $pywLocal) { $pywLocal } else { $pyLocal }
} elseif (Test-Path $pySibling) {
    $py = $pySibling
    $pyw = if (Test-Path $pywSibling) { $pywSibling } else { $pySibling }
} else {
    $pyGlobal = Get-Command python -ErrorAction SilentlyContinue
    if ($pyGlobal) {
        $py = $pyGlobal.Source
        $pyw = $py
    } else {
        Write-Host "Error: No Python environment found." -ForegroundColor Red
        Write-Host "Please set up a Python virtual environment with: python -m venv .venv" -ForegroundColor Yellow
        exit 1
    }
}

Push-Location $root
try {
    if ($Doctor) {
        & $py -m app.main --doctor
        exit $LASTEXITCODE
    }

    $exe = if ($Doctor) { $py } else { $pyw }
    & $exe -m app.main @args
} finally {
    Pop-Location
}
