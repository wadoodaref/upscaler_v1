<#
    Download or link models for Image Upscaler Desktop.

        .\fetch_models.ps1          # Download compact and standard upscaler models
        .\fetch_models.ps1 -Ncnn    # Also download standalone realesrgan-ncnn-vulkan executable
#>

[CmdletBinding()]
param(
    [switch]$Ncnn,
    [switch]$Force
)

$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
$models = Join-Path $root "models"
New-Item -ItemType Directory -Force -Path $models | Out-Null

function Say($msg, $colour = "Cyan") { Write-Host "`n=== $msg" -ForegroundColor $colour }

# 1. Check if face_swap_v1 already has gfpgan_1.4.onnx
$localGfpgan = "E:\projects\face_swap_v1\models\gfpgan_1.4.onnx"
$destGfpgan = Join-Path $models "gfpgan_1.4.onnx"
if ((Test-Path $localGfpgan) -and (-not (Test-Path $destGfpgan))) {
    Say "Linking existing GFPGAN face restoration model from face_swap_v1..." "Green"
    Copy-Item $localGfpgan $destGfpgan
}

# 1b. Face detector (SCRFD det_10g) used by face restoration - also local
$destDet = Join-Path $models "det_10g.onnx"
if (-not (Test-Path $destDet)) {
    foreach ($cand in @("E:\projects\face_swap_v2\models\det_10g.onnx",
                        "E:\projects\face_swap_v1\models\.insightface\models\buffalo_l\det_10g.onnx")) {
        if (Test-Path $cand) {
            Say "Copying face detector det_10g.onnx from $cand" "Green"
            Copy-Item $cand $destDet
            break
        }
    }
}

# 2. Known model targets
$targets = @(
    @{
        Name = "realesr-general-x4v3.onnx"
        Urls = @(
            "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.onnx",
            "https://huggingface.co/qualcomm/Real-ESRGAN-General-x4v3/resolve/main/realesr-general-x4v3.onnx"
        )
    },
    @{
        Name = "realesrgan-x4plus.onnx"
        Urls = @(
            "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/realesrgan-x4plus.onnx",
            "https://huggingface.co/facefusion/models-3.0.0/resolve/main/realesrgan_x4plus.onnx"
        )
    },
    @{
        Name = "realesrgan-x4plus-anime.onnx"
        Urls = @(
            "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/realesrgan-x4plus-anime.onnx"
        )
    }
)

foreach ($t in $targets) {
    $targetPath = Join-Path $models $t.Name
    if ((Test-Path $targetPath) -and (-not $Force)) {
        Write-Host "Model already present: $($t.Name)" -ForegroundColor DarkGray
        continue
    }

    Say "Downloading $($t.Name)..." "Yellow"
    $success = $false
    foreach ($url in $t.Urls) {
        Write-Host "Trying $url ..."
        try {
            if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
                & curl.exe -L --fail --retry 3 -C - -o $targetPath $url
                if ($LASTEXITCODE -eq 0 -and (Test-Path $targetPath)) {
                    $success = $true
                    break
                }
            } else {
                Invoke-WebRequest -Uri $url -OutFile $targetPath
                $success = $true
                break
            }
        } catch {
            Write-Host "Download from $url failed: $_" -ForegroundColor DarkYellow
        }
    }

    if ($success) {
        Write-Host "Downloaded $($t.Name) successfully." -ForegroundColor Green
    } else {
        Write-Host "Note: Could not automatically download $($t.Name). The app will run in Fast CPU mode or you can place the ONNX file manually." -ForegroundColor Yellow
    }
}

if ($Ncnn) {
    Say "Fetching realesrgan-ncnn-vulkan standalone Windows binary..." "Yellow"
    $ncnnUrl = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip"
    $binDir = Join-Path $models "bin"
    New-Item -ItemType Directory -Force -Path $binDir | Out-Null
    $zipPath = Join-Path $models "ncnn.zip"
    try {
        & curl.exe -L -o $zipPath $ncnnUrl
        Expand-Archive -Path $zipPath -DestinationPath $binDir -Force
        Remove-Item $zipPath -Force
        Write-Host "NCNN Vulkan binary extracted to $binDir" -ForegroundColor Green
    } catch {
        Write-Host "NCNN download failed: $_" -ForegroundColor Yellow
    }
}

Say "Model setup finished!" "Green"
