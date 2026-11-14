# Project Plan: Image Upscaler Desktop v1

## Goal
Build an offline desktop application to upscale images and restore portrait faces on Windows, tailored for machines without high-end dedicated GPUs (optimized for CPU and integrated DirectML), with a modern dark UI matching `face_swap_v1`.

## Architecture
- **Language/Framework**: Python 3.14 + PySide6 (Qt Widgets)
- **Styling**: Sleek dark theme (`#16181d`, `#1d2027`, `#4c8dff` accent) matching `face_swap_v1`
- **Engines**:
  1. `ONNX Runtime` (`DmlExecutionProvider` for integrated/discrete GPUs via DirectX 12; `CPUExecutionProvider` for pure CPU fallback)
  2. `NCNN-Vulkan` (CLI sidecar for portable Vulkan execution)
  3. `Algorithmic CPU Engine` (High-order Lanczos4 & Bicubic with edge-preserving unsharp mask for instant execution)
  4. `GFPGAN v1.4` (Face restoration add-on for portraits)
- **Memory Management**: Linear-blended spatial tiling (200px, 256px, 400px) preventing Out-Of-Memory errors on low-RAM/low-VRAM PCs.
- **Workflow / UX**:
  - Interactive Before / After Split Slider (`CompareView`)
  - Batch queue with per-item progress, dimensions, and ETA
  - Drag-and-drop file ingestion
  - Settings persistence (`settings.json`)

## Phases
| # | Phase | Status |
|---|---|---|
| 1 | Scaffold: UI, engines, tiling, queue | Done (session 1) |
| 2 | Face restoration that actually runs (SCRFD + aligned GFPGAN), `--selftest` | Done (session 2) |
| 3 | Portable offline build in house layout, self-tested | Done (session 3) |
| 4 | Extra bundled models (x4plus photo, anime) | Open - needs the ONNX files; awaiting user decision on downloading them |
| 5 | NCNN-Vulkan sidecar | Open - code path exists, binary never fetched or tested |

## Acceptance criteria for the portable
- Only `Upscaler 1.exe` at the root; everything else under `app\`.
- Runs with no Python, no install, no network; models bundled.
- `app\Upscaler.exe --selftest` exits 0 (enforced by `build_portable.ps1`).
