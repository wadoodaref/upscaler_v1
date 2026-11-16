<#
    Build the portable, offline Image Upscaler folder.

        .\build_portable.ps1            # app + model weights - the default
        .\build_portable.ps1 -NoModels  # app only (on purpose; not a deliverable)
        .\build_portable.ps1 -Console   # console build, shows startup tracebacks

    House layout (same as FACE_SWAP_V1_PORTABLE): a small launcher
    "Upscaler 1.exe" is the only file at the root of -Out, everything else is
    in its app\ folder. The result needs no Python, no install and no network:
    copy the folder to any Windows 10/11 PC or USB stick and run it.

    A rebuild keeps app\settings.json and app\output\.
    After packaging, the packaged exe runs its own --selftest (every bundled
    model + face restoration) and the build fails if that does not pass.

    Model weights are bundled by default (user rule: a portable build always
    carries its engines). gfpgan_1.4 and det_10g are licensed for
    non-commercial use: fine for your own machines, do not redistribute.

    IMPORTANT: keep this file ASCII-only (Windows PowerShell 5.1 reads .ps1
    files in the ANSI codepage unless they carry a BOM).
#>

[CmdletBinding()]
param(
    [switch]$NoModels,
    [switch]$Clean,
    [switch]$Console,
    [switch]$NoPackage,
    [switch]$NoSelfTest,
    [string]$Out = "E:\projects\1output\UPSCALER_V1_PORTABLE"
)

$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
$dist = Join-Path $root "dist"

function Say($msg, $colour = "Cyan") { Write-Host "`n=== $msg" -ForegroundColor $colour }
function Fail($msg) { Write-Host "`nBUILD FAILED: $msg" -ForegroundColor Red; exit 1 }

# Same interpreter resolution as run.ps1: local .venv, else the sibling
# face_swap_v1 .venv this project shares on the dev machine.
$py = $null
foreach ($cand in @((Join-Path $root ".venv\Scripts\python.exe"),
                    "E:\projects\face_swap_v1\.venv\Scripts\python.exe")) {
    if (Test-Path $cand) { $py = $cand; break }
}
if (-not $py) { Fail "No Python environment found (.venv or face_swap_v1\.venv)." }
Write-Host "Python: $py"

& $py -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Say "Installing PyInstaller"
    & $py -m pip install --quiet pyinstaller
    if ($LASTEXITCODE -ne 0) { Fail "Could not install PyInstaller." }
}

if ($Clean) {
    Say "Cleaning previous build"
    Remove-Item -Recurse -Force (Join-Path $root "build") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $dist -ErrorAction SilentlyContinue
}

$env:UPSCALER_CONSOLE = if ($Console) { "1" } else { "0" }

# onedir, not onefile: a onefile build unpacks Qt and ONNX Runtime to a temp
# folder on every launch, which is slow and trips antivirus.
Say "Building with PyInstaller (a few minutes)"
Push-Location $root
try {
    & $py -m PyInstaller --noconfirm --clean --log-level WARN (Join-Path $root "upscaler.spec")
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { Fail "PyInstaller exited with $code." }

$appDir = Join-Path $dist "Upscaler"
if (-not (Test-Path (Join-Path $appDir "Upscaler.exe"))) { Fail "Expected output not found: $appDir\Upscaler.exe" }

# --- payload ----------------------------------------------------------------

New-Item -ItemType Directory -Force -Path (Join-Path $appDir "models") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $appDir "output") | Out-Null

if (-not $NoModels) {
    $src = Join-Path $root "models"
    foreach ($need in @("realesr-general-x4v3.onnx", "realesrgan-x4plus-fp16.onnx",
                        "realesrgan-x2plus-fp16.onnx", "realesrgan-x4plus-anime.onnx", "realesrgan-x4plus-anime-4b32f.onnx",
                        "gfpgan_1.4.onnx", "det_10g.onnx")) {
        if (-not (Test-Path (Join-Path $src $need))) {
            Fail "models\$need is missing, so the portable would lack an engine. Run .\fetch_models.ps1, or pass -NoModels on purpose."
        }
    }
    Say "Copying model weights"
    robocopy $src (Join-Path $appDir "models") /E /XF *.zip *.part /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { Fail "Copying models failed ($LASTEXITCODE)." }
    Get-ChildItem (Join-Path $appDir "models") -File | ForEach-Object {
        Write-Host ("    {0}  ({1:N1} MB)" -f $_.Name, ($_.Length / 1MB))
    }
} else {
    Write-Host "    models NOT bundled (-NoModels). Only the Fast CPU modes will work." -ForegroundColor Yellow
}

$readme = @"
Image Upscaler 1 - portable build

Run "Upscaler 1.exe". No installation, no Python, no internet needed.

Everything lives in the app\ folder:
  models\    the AI model files (upscaler, face detector, face restorer)
  output\    results are written here unless you choose another folder
  settings.json, upscaler.log   created on first run

Models: Real-ESRGAN Compact (fast default), Real-ESRGAN Plus (best for photos,
slower), Anime 6B and Anime Light (drawings), plus two instant "Fast" modes.

gfpgan_1.4 and det_10g are licensed for non-commercial use.
"@
$readme | Set-Content -Path (Join-Path $appDir "READ ME.txt") -Encoding ascii

if ($NoPackage) {
    Say "Done (not packaged) - $appDir" "Green"
    exit 0
}

# --- house layout: one launcher exe at the root, everything else in app\ ------

Say "Packaging into $Out"
$app = Join-Path $Out "app"
New-Item -ItemType Directory -Force -Path $app | Out-Null
# mirror the build into app\; the user's settings.json and output\ are left alone
robocopy $appDir $app /MIR /XD output /XF settings.json /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Fail "robocopy failed ($LASTEXITCODE)." }
New-Item -ItemType Directory -Force -Path (Join-Path $app "output") | Out-Null

$cs = @'
using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
static class Launcher {
  [STAThread]
  static void Main() {
    string dir = Path.Combine(Path.GetDirectoryName(Process.GetCurrentProcess().MainModule.FileName), "app");
    string exe = Path.Combine(dir, "Upscaler.exe");
    if (!File.Exists(exe)) { MessageBox.Show("The app folder is missing next to this program.", "Upscaler 1"); return; }
    Process.Start(new ProcessStartInfo(exe) { WorkingDirectory = dir, UseShellExecute = false });
  }
}
'@
$csFile = Join-Path $env:TEMP "upscaler1_launcher.cs"
Set-Content $csFile $cs -Encoding ascii
$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
& $csc /nologo /target:winexe /optimize+ /r:System.Windows.Forms.dll "/out:$Out\Upscaler 1.exe" $csFile
if ($LASTEXITCODE -ne 0) { Fail "Launcher build failed." }
Remove-Item $csFile -ErrorAction SilentlyContinue

# --- verify the packaged build itself ----------------------------------------

if (-not $NoSelfTest -and -not $NoModels) {
    Say "Self-test of the packaged exe (all bundled models + face restoration)"
    $report = Join-Path $app "selftest.json"
    Remove-Item $report, (Join-Path $app "startup_error.log") -ErrorAction SilentlyContinue
    $p = Start-Process -FilePath (Join-Path $app "Upscaler.exe") -ArgumentList "--selftest" `
                       -WorkingDirectory $app -PassThru -WindowStyle Hidden
    if (-not $p.WaitForExit(600000)) { $p.Kill(); Fail "Self-test timed out." }
    if (Test-Path (Join-Path $app "startup_error.log")) {
        Get-Content (Join-Path $app "startup_error.log") | Select-Object -Last 15
        Fail "The packaged exe failed to start."
    }
    if ($p.ExitCode -ne 0 -or -not (Test-Path $report)) {
        if (Test-Path $report) { Get-Content $report }
        Fail "Self-test failed (exit $($p.ExitCode)). See $app\upscaler.log"
    }
    $r = Get-Content $report -Raw | ConvertFrom-Json
    foreach ($m in $r.models.PSObject.Properties) {
        Write-Host ("    {0,-32} {1,-24} {2}s" -f $m.Name, $m.Value.provider, $m.Value.seconds)
    }
    Write-Host "    face restorer: ok"
    Remove-Item $report, (Join-Path $app "upscaler.log") -ErrorAction SilentlyContinue
}

$sizeMb = [math]::Round(((Get-ChildItem $Out -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB), 0)
Write-Host "    root of $Out :"; Get-ChildItem $Out | ForEach-Object { Write-Host "      $($_.Name)" }
Say "Done - $Out ($sizeMb MB)" "Green"
