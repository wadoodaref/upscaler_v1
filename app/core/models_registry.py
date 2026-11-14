"""Model registry, definitions, and download information."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelSpec:
    id: str
    name: str
    category: str              # "photo", "anime", "lightweight", "algorithmic"
    scale: int                 # 2, 4
    engine: str                # "onnx", "ncnn", "cpu"
    filename: str              # onnx or ncnn model name
    description: str
    download_url: str | None = None
    sha256: str | None = None


# Known models
MODELS: list[ModelSpec] = [
    ModelSpec(
        id="realesr-general-x4v3",
        name="Real-ESRGAN Compact (General v3)",
        category="lightweight",
        scale=4,
        engine="onnx",
        filename="realesr-general-x4v3.onnx",
        description="Recommended default. Lightweight, fast inference on CPU & integrated GPU.",
        download_url="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
    ),
    ModelSpec(
        id="realesrgan-x4plus",
        name="Real-ESRGAN Plus (Photo)",
        category="photo",
        scale=4,
        engine="onnx",
        filename="realesrgan-x4plus.onnx",
        description="Detailed photo upscaling. Heavier, best with GPU/DirectML.",
        download_url=None,
    ),
    ModelSpec(
        id="realesrgan-x4plus-anime",
        name="Real-ESRGAN Anime 6B",
        category="anime",
        scale=4,
        engine="onnx",
        filename="realesrgan-x4plus-anime.onnx",
        description="Sharp line art and color gradients for anime and illustrations.",
        download_url=None,
    ),
    ModelSpec(
        id="realesr-animevideov3",
        name="Real-ESRGAN Anime Compact (2x/4x)",
        category="anime",
        scale=4,
        engine="onnx",
        filename="realesr-animevideov3.onnx",
        description="Very fast anime upscaling suitable for low-spec PCs.",
        download_url=None,
    ),
    ModelSpec(
        id="fast-lanczos",
        name="Fast Lanczos + Edge Sharpener",
        category="algorithmic",
        scale=4,
        engine="cpu",
        filename="",
        description="Instant CPU fallback. No deep neural network, 0 VRAM, works on any PC.",
        download_url=None,
    ),
    ModelSpec(
        id="fast-bicubic",
        name="Fast Bicubic + Unsharp Mask",
        category="algorithmic",
        scale=2,
        engine="cpu",
        filename="",
        description="Instant 2x CPU enlargement with edge-preserving sharpening.",
        download_url=None,
    ),
]


def get_model(model_id: str) -> ModelSpec:
    for m in MODELS:
        if m.id == model_id:
            return m
    return MODELS[0]


def is_model_installed(spec: ModelSpec, models_dir: Path) -> bool:
    if spec.engine == "cpu":
        return True
    return (models_dir / spec.filename).is_file()
