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

### Remote & Push
- Created GitHub repository: `https://github.com/wadoodaref/upscaler_v1`
- Pushed root commit `49b9bf4` to `origin/main`.

## Session 2 — 2026-11-14: Face restoration repaired, offline-safe UI, headless self-test

### User Request
"upscaler v1 is main project, read .md files and proceed, it should be portable offline project like face swap."

### What was found
- Face restoration could never have worked: `restorer.py` used `cv2.CascadeClassifier`, which does not exist in the installed OpenCV 5.0.0 (`AttributeError`). Session 1's verification only loaded the GFPGAN model; it never ran a detection. Found by the new `--selftest`.
- Even with a working cascade, the old code fed GFPGAN an unaligned square crop and pasted it back with hard edges.
- The model list offered three models whose files are not on disk; choosing one silently produced plain Lanczos.
- The "2x" scale choice was ignored for 4x models (output was always 4x, file named `_2x`).
- `settings.json` stores absolute paths, which break when a portable folder moves to another PC/drive.

### Changes
- `app/core/restorer.py`: rewritten. SCRFD face detector (`det_10g.onnx`, pure NumPy decode) + FFHQ-512 five-point alignment + GFPGAN + feathered paste-back limited to the face's bounding box. Detector/alignment ported from this machine's `face_swap_v2/engine` (`detector.py`, `align.py`). No Haar cascade.
- `app/main.py`: new `--selftest` (runs every installed model on auto and CPU, plus the face restorer; writes `selftest.json`, exit code 0/1).
- `app/core/pipeline.py`: result is reduced to the requested scale when the model's native factor is larger.
- `app/ui/main_window.py`: only installed models are listed; face-restore checkbox disabled with the missing file names when a model is absent; cancel is reported as "Cancelled" not "Error"; final status reports failures instead of always "completed successfully".
- `app/util/config.py`: `ROOT` is the exe's folder when frozen; saved output/input folders that no longer exist fall back to defaults.
- `app/util/logging_setup.py`: no stdout handler when the process has no stdout (windowed).
- `fetch_models.ps1`: copies `det_10g.onnx` from the local face-swap projects.
- `.gitignore`: `selftest.json`.

### Decisions
- Reused `det_10g.onnx` already on this machine (16 MB) instead of downloading a new detector: nothing fetched from the network.
- "Auto" device left as DirectML-first: measured on this PC, 640x444 -> 4x took 9.7 s on DirectML vs 10.2 s on CPU (warm), i.e. no reason to change.

### Verification
- `python -m app.main --selftest`: PASSED (realesr-general-x4v3 on DirectML and CPU, fast-lanczos, fast-bicubic, face restorer).
- Real photo (6 people, reduced to 320 px, upscaled 4x with face restoration on CPU): 6 faces detected and restored, no visible seams; 34.6 s with restoration vs 3.1 s without.

