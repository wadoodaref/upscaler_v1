# Handoff - Image Upscaler Desktop v1

Authoritative current state. Updated 2026-11-16 (session 5). Read
`general_rules_read_first_v7.md` first, then the tail of `chat.md`.

## State
- Python 3.14 + PySide6 desktop app, offline. Works from source (`.\run.ps1`)
  and as a portable build (`.\build_portable.ps1`).
- Portable deliverable on DR-WADOOD-HP15 as of 2026-11-14:
  `E:\projects\1output\UPSCALER_V1_PORTABLE` (767 MB) - `Upscaler 1.exe` at the
  root, everything else in `app\`. Built and self-tested across all 6 models + face restorer.
- There is no local `.venv`; `run.ps1` and `build_portable.ps1` fall back to
  `E:\projects\face_swap_v1\.venv` (this machine only). PyInstaller 6.22.3 is
  installed there.

## What works (verified)
- Models: Compact 4x, Photo 4x fp16, Photo 2x fp16, Anime 6B, Anime Light, Fast Lanczos/Bicubic. Packaged `--selftest` passes all on "auto" and CPU, plus the face restorer.
- "Auto" device: Photo models on DirectML (640x444 -> 4x: 147 s first / 104 s next image, vs 279 s / 273 s on CPU); small models and GFPGAN on CPU (DirectML start-up/compile costs 10-25 s and they run as fast on CPU).
- Photo models are fp16 (54 dB PSNR vs fp32, 1.8x faster). A 2x request on the 4x Photo model switches to the dedicated 2x model.
- DirectML rules learned the hard way: `enable_mem_pattern=False`, sequential execution, explicit `device_id` (without them the Photo model hung the GPU, 887A0006, and fell back to CPU silently); every new input shape recompiles kernels (7-25 s), so DirectML tiles are padded to one fixed size (`fixed_shape` in `tiler.py`).
- CPU sessions use the physical-core count (4 beats 8 logical threads).
- Face restoration: SCRFD `det_10g.onnx` -> FFHQ-512 alignment -> `gfpgan_1.4.onnx` -> feathered paste-back (about 3.3 s/face on CPU).

## Not done / not verified
- NCNN-Vulkan engine: optional CLI sidecar path exists in `upscaler.py`, but no binary on disk.
- No click-through GUI test of a full upscale in the portable (the pipeline is
  covered by `--selftest`, the window only by a start/close check).
- No app icon. Window title reads "Image Upscaler v1 v1.0.0" (duplicate "v1").
- `preserve_exif` setting exists but nothing implements it.

## Rules of thumb for this project
- After every app change: `.\build_portable.ps1` (user tests in the portable).
- Portable always carries its models; root holds only the launcher exe.
- OpenCV here is 5.0.0: no `CascadeClassifier`, do not reintroduce Haar code.
