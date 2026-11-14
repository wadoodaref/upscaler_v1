# Handoff - Image Upscaler Desktop v1

Authoritative current state. Updated 2026-11-14 (session 4). Read
`general_rules_read_first_v7.md` first, then the tail of `chat.md`.

## State
- Python 3.14 + PySide6 desktop app, offline. Works from source (`.\run.ps1`)
  and as a portable build (`.\build_portable.ps1`).
- Portable deliverable on DR-WADOOD-HP15 as of 2026-11-14:
  `E:\projects\1output\UPSCALER_V1_PORTABLE` (853 MB) - `Upscaler 1.exe` at the
  root, everything else in `app\`. Built and self-tested across all 6 models + face restorer.
- There is no local `.venv`; `run.ps1` and `build_portable.ps1` fall back to
  `E:\projects\face_swap_v1\.venv` (this machine only). PyInstaller 6.22.3 is
  installed there.

## What works (verified)
- Real-ESRGAN Compact (`realesr-general-x4v3.onnx`, 4.6 MB) on DirectML (2.7s) and CPU (1.0s), tiled.
- Real-ESRGAN Plus Photo (`realesrgan-x4plus.onnx`, 66.3 MB) on DirectML (9.6s) and CPU (13.6s), tiled.
- Real-ESRGAN Anime 6B (`realesrgan-x4plus-anime.onnx`, 17.1 MB) on DirectML (7.0s) and CPU (1.9s), tiled.
- Real-ESRGAN Anime Light (`realesrgan-x4plus-anime-4b32f.onnx`, 4.9 MB) on DirectML (2.5s) and CPU (0.5s), tiled.
- Fast Lanczos (4x) and Fast Bicubic (2x) algorithmic modes (sub-100ms).
- Face restoration: SCRFD `det_10g.onnx` -> FFHQ-512 alignment -> `gfpgan_1.4.onnx` -> feathered paste-back.
- Clean session memory management: previous ONNX sessions explicitly deleted with `gc.collect()` to prevent DirectML TDR command recorder crashes (`887A0006`) on sequential model loads.
- Automated fallback to `CPUExecutionProvider` if DirectML raises any device error.
- `--selftest` (source and frozen), GUI start from the portable.

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
