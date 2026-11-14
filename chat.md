# Chat Log — Image Upscaler Desktop v1

## Session 1 — 2026-11-14: Initial scaffold of Image Upscaler Desktop (Python / PySide6)

### User Request
Create an offline desktop app to upscale pictures using Python/PySide6 with a similar UI to face swap app v1, optimized for CPU and low/no dedicated GPU hardware. After finish, log and push.

### Decisions & Rationale
- **Framework**: Python 3.14 + PySide6 matching `face_swap_v1` architecture for fast, native Windows desktop UI without requiring a Rust compiler toolchain.
- **Hardware Acceleration for Low-Spec PCs**: Used ONNX Runtime with `DmlExecutionProvider` (DirectML over DirectX 12) to leverage integrated Intel UHD/Iris Xe or AMD Radeon GPUs with zero CUDA requirement, with automatic fallback to multi-threaded `CPUExecutionProvider`.
- **Memory Tiling**: Implemented `tiler.py` with linear ramp blending to allow high-resolution upscaling (e.g. 4x up to 4K/8K) on machines with low VRAM or RAM without running out of memory.
- **Fast CPU Mode**: Built-in Lanczos4 / Bicubic algorithmic upscaling with edge-preserving unsharp masking for instant, model-free fallback on weak CPUs.
- **Face Restoration**: Integrated `restorer.py` with GFPGAN v1.4 ONNX support to restore facial details in portraits and group photos.

### Files Created
- `app/__init__.py`
- `app/main.py`
- `app/core/__init__.py`
- `app/core/providers.py`
- `app/core/models_registry.py`
- `app/core/tiler.py`
- `app/core/upscaler.py`
- `app/core/restorer.py`
- `app/core/pipeline.py`
- `app/ui/__init__.py`
- `app/ui/theme.py`
- `app/ui/eta.py`
- `app/ui/widgets/__init__.py`
- `app/ui/widgets/compare_view.py`
- `app/ui/widgets/image_view.py`
- `app/ui/widgets/queue_view.py`
- `app/ui/main_window.py`
- `app/util/__init__.py`
- `app/util/config.py`
- `app/util/logging_setup.py`
- `.gitignore`
- `general_rules_read_first_v7.md`
- `PROJECT_PLAN.md`
- `README.md`
- `requirements.txt`
- `fetch_models.ps1`
- `run.ps1`
- `GITIGNORED_FILES_DR-WADOOD-HP15.md`

### Verification
- `.\run.ps1 -Doctor`: Correctly detected `DirectML (DirectX 12 GPU)` and `CPUExecutionProvider`.
- Pipeline CPU test: Upscaled sample image 4x in under 2 seconds.
- Model detection: `realesr-general-x4v3.onnx` and `gfpgan_1.4.onnx` verified and loaded cleanly.
- GUI smoke test: `MainWindow` instantiated without errors.
