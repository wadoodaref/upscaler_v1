# Image Upscaler Desktop v1

A modern, high-performance offline desktop application to upscale images and restore portrait faces on Windows. Designed with the exact look, feel, and dark UI architecture of **Face Swap v1**.

---

## Key Features

1. **Multi-Engine Offline Architecture**:
   - **ONNX Runtime (DirectML & CPU)**: Leverages DirectX 12 hardware acceleration on **any GPU** (NVIDIA, AMD Radeon, Intel Arc, and Intel Integrated UHD/Iris Xe). If no GPU is available, it runs directly on CPU with multi-threaded vectorization.
   - **NCNN-Vulkan (CLI Sidecar)**: Optional standalone binary integration for Vulkan GPU acceleration.
   - **Fast Algorithmic Engine (Instant CPU Fallback)**: High-order Lanczos4 & Bicubic interpolation with smart edge-preserving unsharp masking. Runs in sub-second time on even weak dual-core CPUs with 0 MB model downloads.
2. **Built-in Seam Blending & Memory Tiling**:
   - Supports 200px, 256px, and 400px tiling to prevent Out Of Memory (OOM) errors on low-VRAM GPUs or systems with limited RAM.
3. **Face Restoration Add-on**:
   - **SCRFD** face detection + **GFPGAN v1.4** (both ONNX): every face is found, aligned, restored and blended back with a feathered mask.
4. **Intuitive Face Swap v1-style UI**:
   - **Interactive Before / After Split Slider**: Drag with mouse or use arrow keys (Left/Right, Home/End) to inspect fine details.
   - **Batch Queue**: Drag and drop single images or entire folders, track per-item progress, elapsed time, and ETA.
   - **Clean Dark Theme**: Custom palette matching `#16181d` / `#1d2027` with `#4c8dff` accent.

---

## Quick Start

### 1. Launch the App
Run with PowerShell:
```powershell
.\run.ps1
```

### 2. Hardware Diagnostics
Check available hardware acceleration providers:
```powershell
.\run.ps1 -Doctor
```

### 3. Portable offline build
```powershell
.\build_portable.ps1
```
Produces `E:\projects\1output\UPSCALER_V1_PORTABLE\` (about 680 MB):

```
UPSCALER_V1_PORTABLE\
  Upscaler 1.exe        <- the only file at the root; double-click this
  app\                  <- Upscaler.exe, runtime, models\, output\, settings.json
```

The folder needs no Python, no installation and no internet. Copy it to any
Windows 10/11 PC or USB stick. Model weights are bundled. The build runs the
packaged exe's own `--selftest` (every bundled model + face restoration) and
fails if that does not pass. A rebuild keeps `app\settings.json` and `app\output\`.

### 4. Models
All of these are bundled and required by the build. The two "Fast" modes need
no model. The app lists only models whose file is present in `models\`.
`.\fetch_models.ps1` downloads the Real-ESRGAN Plus/Anime files and
checks their SHA-256.

**Best quality** for photos is Real-ESRGAN Plus (4x, or the dedicated 2x model,
which the app picks automatically when you ask for 2x) with Face Restoration on.
The Photo models are fp16: visually identical to fp32 (54 dB PSNR) but about
1.8x faster and half the size. On a GPU (DirectML) they are 2-3x faster than on
CPU; the small models (Compact, Anime Light) run equally well on either.

| File name | Model | Size | Source |
|---|---|---:|---|
| `realesr-general-x4v3.onnx` | Real-ESRGAN Compact (default, fast) | 4.6 MB | already on dev machine |
| `realesrgan-x4plus-fp16.onnx` | Real-ESRGAN Plus 4x (photo, best quality) | 35 MB | HF `facefusion/models-3.0.0` `real_esrgan_x4_fp16.onnx` |
| `realesrgan-x2plus-fp16.onnx` | Real-ESRGAN Plus 2x (photo, about 4x faster than 4x) | 35 MB | HF `facefusion/models-3.0.0` `real_esrgan_x2_fp16.onnx` |
| `realesrgan-x4plus-anime.onnx` | Real-ESRGAN Anime 6B | 17 MB | HF `deepghs/imgutils-models` |
| `realesrgan-x4plus-anime-4b32f.onnx` | Real-ESRGAN Anime Light | 4.9 MB | HF `deepghs/imgutils-models` |
| `det_10g.onnx` | SCRFD face detector | 16 MB | local face_swap projects |
| `gfpgan_1.4.onnx` | GFPGAN face restorer | 325 MB | local face_swap projects |

`gfpgan_1.4` and `det_10g` are licensed for non-commercial use.

---

## Project Structure

```
E:\projects\upscaler_v1\
  ├── app\
  │   ├── core\
  │   │   ├── models_registry.py   # Model specifications
  │   │   ├── pipeline.py          # Processing and batch management
  │   │   ├── providers.py         # DirectML, CUDA, and CPU detection
  │   │   ├── restorer.py          # GFPGAN face restoration
  │   │   ├── tiler.py             # Memory-bounded tiling and seam blending
  │   │   └── upscaler.py          # Multi-engine execution
  │   ├── ui\
  │   │   ├── eta.py               # ETA calculation and time formatting
  │   │   ├── main_window.py       # Main PySide6 window
  │   │   ├── theme.py             # Dark styling matching face_swap_v1
  │   │   └── widgets\
  │   │       ├── compare_view.py  # Interactive split comparison slider
  │   │       ├── image_view.py    # Drag & drop preview widget
  │   │       └── queue_view.py    # Batch queue table
  │   ├── util\
  │   │   ├── config.py            # Settings persistence (settings.json)
  │   │   └── logging_setup.py
  │   └── main.py                  # Entry point
  ├── models\                      # ONNX models storage
  ├── output\                      # Default output directory
  ├── build_portable.ps1           # Portable offline build (PyInstaller + launcher)
  ├── launch.py                    # Entry point for the frozen build
  ├── upscaler.spec                # PyInstaller spec
  ├── fetch_models.ps1             # Model downloader script
  ├── requirements.txt
  └── run.ps1                      # App launcher
```
