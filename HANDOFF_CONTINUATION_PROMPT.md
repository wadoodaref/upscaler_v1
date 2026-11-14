# Handoff - Image Upscaler Desktop v1

Authoritative current state. Updated 2026-11-14 (session 3). Read
`general_rules_read_first_v7.md` first, then the tail of `chat.md`.

## State
- Python 3.14 + PySide6 desktop app, offline. Works from source (`.\run.ps1`)
  and as a portable build (`.\build_portable.ps1`).
- Portable deliverable on DR-WADOOD-HP15 as of 2026-11-14:
  `E:\projects\1output\UPSCALER_V1_PORTABLE` (676 MB) - `Upscaler 1.exe` at the
  root, everything else in `app\`. Built and self-tested.
- There is no local `.venv`; `run.ps1` and `build_portable.ps1` fall back to
  `E:\projects\face_swap_v1\.venv` (this machine only). PyInstaller 6.22.3 is
  installed there.

## What works (verified)
- Real-ESRGAN Compact (`realesr-general-x4v3.onnx`) on DirectML and CPU, tiled.
- Fast Lanczos / Fast Bicubic.
- Face restoration: SCRFD `det_10g.onnx` -> FFHQ-512 alignment -> `gfpgan_1.4.onnx`
  -> feathered paste-back. Checked on a 6-person photo.
- `--selftest` (source and frozen), GUI start from the portable.

## Not done / not verified
- `realesrgan-x4plus`, `realesrgan-x4plus-anime`, `realesr-animevideov3`: in the
  registry but the ONNX files are not on this machine, so the UI hides them.
  The URLs in `fetch_models.ps1` for these are unverified guesses from session 1.
- NCNN-Vulkan engine: never run; no binary on disk.
- No click-through GUI test of a full upscale in the portable (the pipeline is
  covered by `--selftest`, the window only by a start/close check).
- No app icon. Window title reads "Image Upscaler v1 v1.0.0" (duplicate "v1").
- `preserve_exif` setting exists but nothing implements it.

## Rules of thumb for this project
- After every app change: `.\build_portable.ps1` (user tests in the portable).
- Portable always carries its models; root holds only the launcher exe.
- OpenCV here is 5.0.0: no `CascadeClassifier`, do not reintroduce Haar code.
