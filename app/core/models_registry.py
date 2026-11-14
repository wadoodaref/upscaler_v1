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
    filenames: tuple[str, ...] # Primary filename and alternate aliases
    description: str
    sha256: str | None = None
    download_url: str | None = None

    @property
    def filename(self) -> str:
        return self.filenames[0]


# Verified Models
MODELS: list[ModelSpec] = [
    ModelSpec(
        id="realesr-general-x4v3",
        name="Real-ESRGAN Compact (General v3)",
        category="lightweight",
        scale=4,
        engine="onnx",
        filenames=("realesr-general-x4v3.onnx",),
        description="Recommended default. Lightweight (4.6 MB), fast on CPU & integrated GPU.",
        sha256="1940a93ee08283a0a7286183186357b1688fe9fa8ede74604b424586aaddf112",
        download_url="https://huggingface.co/CoderViking/realesr-general-x4v3-onnx/resolve/main/realesr-general-x4v3.onnx",
    ),
    ModelSpec(
        id="realesrgan-x4plus",
        name="Real-ESRGAN Plus (Photo)",
        category="photo",
        scale=4,
        engine="onnx",
        filenames=("real_esrgan_x4.onnx", "realesrgan-x4plus.onnx"),
        description="Full RRDBNet photo super-resolution (66.3 MB) from FaceFusion / Real-ESRGAN.",
        sha256="afa7fa42eed0315a3d7b2a54e79e4e44a672d3c0889c2828c4f84c9ab91edb0b",
        download_url="https://huggingface.co/facefusion/models-3.0.0/resolve/main/real_esrgan_x4.onnx",
    ),
    ModelSpec(
        id="realesrgan-x4plus-anime-6b",
        name="Real-ESRGAN Anime 6B",
        category="anime",
        scale=4,
        engine="onnx",
        filenames=("RealESRGAN_x4plus_anime_6B.onnx", "realesrgan-x4plus-anime.onnx"),
        description="High fidelity anime and illustration upscaler (17.1 MB) from deepghs.",
        sha256="2648cab4c4343541c1aa291c6754e9e8edbe7a813fffc2a677423dd12cb6b7f7",
        download_url="https://huggingface.co/deepghs/imgutils-models/resolve/main/real_esrgan/RealESRGAN_x4plus_anime_6B.onnx",
    ),
    ModelSpec(
        id="realesrgan-x4plus-anime-4b",
        name="Real-ESRGAN Anime Ultra-Light (4B32F)",
        category="anime",
        scale=4,
        engine="onnx",
        filenames=("RealESRGAN_x4plus_anime_4B32F.onnx", "realesrgan-x4plus-anime-4b32f.onnx"),
        description="Ultra-fast compact anime model (4.9 MB) from deepghs for low-end hardware.",
        sha256="2208c7ae8db793330abf1248fbce15585ad317e921c456265572836b92926c9a",
        download_url="https://huggingface.co/deepghs/imgutils-models/resolve/main/real_esrgan/RealESRGAN_x4plus_anime_4B32F.onnx",
    ),
    ModelSpec(
        id="fast-lanczos",
        name="Fast Lanczos + Edge Sharpener",
        category="algorithmic",
        scale=4,
        engine="cpu",
        filenames=(),
        description="Instant CPU fallback. No deep neural network, 0 VRAM, works on any PC.",
        download_url=None,
    ),
    ModelSpec(
        id="fast-bicubic",
        name="Fast Bicubic + Unsharp Mask",
        category="algorithmic",
        scale=2,
        engine="cpu",
        filenames=(),
        description="Instant 2x CPU enlargement with edge-preserving sharpening.",
        download_url=None,
    ),
]


def get_model(model_id: str) -> ModelSpec:
    for m in MODELS:
        if m.id == model_id:
            return m
    return MODELS[0]


def resolve_model_file(spec: ModelSpec, models_dir: Path) -> Path | None:
    for fname in spec.filenames:
        candidate = models_dir / fname
        if candidate.is_file():
            return candidate
    return None


def is_model_installed(spec: ModelSpec, models_dir: Path) -> bool:
    if spec.engine == "cpu":
        return True
    return resolve_model_file(spec, models_dir) is not None
