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
        Sha256 = "1940a93ee08283a0a7286183186357b1688fe9fa8ede74604b424586aaddf112"
        Urls = @(
            "https://huggingface.co/CoderViking/realesr-general-x4v3-onnx/resolve/main/realesr-general-x4v3.onnx"
        )
    },
    # The three below were downloaded from these URLs and checksum-verified
    # on 2026-11-14. (The realesr-general-x4v3 URLs above are unverified
    # leftovers from session 1; that file is already on the dev machine.)
    @{
        Name = "realesrgan-x4plus.onnx"
        Sha256 = "afa7fa42eed0315a3d7b2a54e79e4e44a672d3c0889c2828c4f84c9ab91edb0b"
        Urls = @("https://huggingface.co/facefusion/models-3.0.0/resolve/main/real_esrgan_x4.onnx")
    },
    @{
        Name = "realesrgan-x4plus-anime.onnx"
        Sha256 = "2648cab4c4343541c1aa291c6754e9e8edbe7a813fffc2a677423dd12cb6b7f7"
        Urls = @("https://huggingface.co/deepghs/imgutils-models/resolve/main/real_esrgan/RealESRGAN_x4plus_anime_6B.onnx")
    },
    @{
        Name = "realesrgan-x4plus-anime-4b32f.onnx"
        Sha256 = "2208c7ae8db793330abf1248fbce15585ad317e921c456265572836b92926c9a"
        Urls = @("https://huggingface.co/deepghs/imgutils-models/resolve/main/real_esrgan/RealESRGAN_x4plus_anime_4B32F.onnx")
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

    if ($success -and $t.Sha256) {
        $got = (Get-FileHash $targetPath -Algorithm SHA256).Hash.ToLower()
        if ($got -ne $t.Sha256) {
            Write-Host "Checksum mismatch for $($t.Name) - file removed." -ForegroundColor Red
            Remove-Item $targetPath -Force
            $success = $false
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
