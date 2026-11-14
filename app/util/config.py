"""Configuration, paths, and persistent settings."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

APP_NAME = "Image Upscaler v1"
APP_VERSION = "1.0.0"

ROOT = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = ROOT / "models"
OUTPUT_DIR = ROOT / "output"
SETTINGS_FILE = ROOT / "settings.json"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}


def is_image(path: Path | str) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTS


@dataclass
class Settings:
    engine: str = "auto"                    # "auto", "onnx", "ncnn", "fast_cpu"
    model: str = "realesr-general-x4v3"      # default fast compact model
    device: str = "auto"                    # "auto", "directml", "cuda", "cpu"
    scale: int = 4                          # 2, 3, 4
    tile_size: int = 256                    # 0=no tile, 128, 200, 256, 400
    face_restoration: bool = False
    face_restorer: str = "gfpgan_1.4"
    face_restorer_blend: float = 0.8
    output_dir: str = str(OUTPUT_DIR)
    output_format: str = "png"              # "png", "jpg", "webp"
    jpg_quality: int = 95
    preserve_exif: bool = True
    divider_pos: float = 0.5
    last_input_dir: str = str(ROOT)

    @classmethod
    def load(cls) -> Settings:
        if not SETTINGS_FILE.is_file():
            return cls()
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception as e:
            log.warning("Could not load settings from %s (%s); using defaults", SETTINGS_FILE, e)
            return cls()

    def save(self) -> None:
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
        except Exception as e:
            log.warning("Failed saving settings to %s: %s", SETTINGS_FILE, e)
