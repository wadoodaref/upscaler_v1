"""Pipeline managing image IO, upscaling, optional face restoration, and saving."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from PIL import Image

from ..util.config import Settings
from .models_registry import get_model, is_model_installed
from .providers import resolve_onnx_providers
from .restorer import FaceRestorer
from .upscaler import UpscalerEngine

log = logging.getLogger(__name__)


@dataclass
class UpscaleJob:
    input_path: Path
    output_path: Path
    status: str = "pending"   # pending, running, completed, error, cancelled
    message: str = ""
    original_dims: tuple[int, int] = (0, 0)
    output_dims: tuple[int, int] = (0, 0)
    elapsed_seconds: float = 0.0


class UpscalePipeline:
    def __init__(self, settings: Settings, models_dir: Path) -> None:
        self.settings = settings
        self.models_dir = models_dir
        self.engine = UpscalerEngine(models_dir)
        # GFPGAN measured faster on CPU than on DirectML here (3.3 s vs 4.0 s per
        # face) and CPU leaves the GPU free; honour an explicit GPU choice only.
        restore_dev = "cpu" if settings.device in ("auto", "cpu") else settings.device
        self.restorer = FaceRestorer(models_dir, resolve_onnx_providers(restore_dev))

    def load_image(self, path: Path) -> np.ndarray:
        # Load through OpenCV with UTF-8/Windows wide-char path safety
        with open(path, "rb") as f:
            bytes_data = bytearray(f.read())
        arr = np.asarray(bytes_data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Could not decode image: {path}")
        return img

    @staticmethod
    def read_metadata(path: Path) -> tuple[bytes | None, bytes | None]:
        """EXIF and ICC profile of the source, or (None, None).

        cv2 applies the EXIF orientation while decoding, so the pixels are
        already upright; the copied EXIF gets Orientation=1 to avoid a second
        rotation in viewers.
        """
        try:
            with Image.open(path) as im:
                exif = im.getexif()
                icc = im.info.get("icc_profile")
                if not exif and not icc:
                    return None, None
                if 0x0112 in exif:
                    exif[0x0112] = 1
                return (exif.tobytes() if exif else None), icc
        except Exception as e:                                     # noqa: BLE001
            log.debug("No metadata read from %s: %s", path, e)
            return None, None

    def save_image(self, img_bgr: np.ndarray, out_path: Path, quality: int = 95,
                   source_path: Path | None = None) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        ext = out_path.suffix.lower()

        # Keep the photo's camera data / colour profile when asked to.
        if self.settings.preserve_exif and source_path is not None:
            exif, icc = self.read_metadata(source_path)
            if exif or icc:
                rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                kwargs: dict = {}
                if exif:
                    kwargs["exif"] = exif
                if icc:
                    kwargs["icc_profile"] = icc
                if ext in (".jpg", ".jpeg"):
                    kwargs.update(quality=quality, subsampling=0)
                elif ext == ".webp":
                    kwargs.update(quality=quality)
                try:
                    Image.fromarray(rgb).save(out_path, **kwargs)
                    return
                except Exception as e:                             # noqa: BLE001
                    log.warning("Saving with metadata failed (%s); saving without it", e)

        if ext in (".jpg", ".jpeg"):
            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        elif ext == ".webp":
            encode_params = [int(cv2.IMWRITE_WEBP_QUALITY), quality]
        else:
            encode_params = [int(cv2.IMWRITE_PNG_COMPRESSION), 4]

        success, enc = cv2.imencode(ext, img_bgr, encode_params)
        if not success:
            raise RuntimeError(f"Failed to encode image to {ext}")
        with open(out_path, "wb") as f:
            f.write(enc)

    def process_image(
        self,
        image_bgr: np.ndarray,
        progress_cb: Callable[[int, int], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> np.ndarray:
        # 1. Upscale. A 2x request on the 4x Photo model would compute 4x and
        # throw 3/4 of it away; use the dedicated 2x network when it is installed.
        model_id = self.settings.model
        if self.settings.scale == 2 and model_id == "realesrgan-x4plus":
            alt = get_model("realesrgan-x2plus")
            if alt.id == "realesrgan-x2plus" and is_model_installed(alt, self.models_dir):
                model_id = alt.id
        result = self.engine.upscale(
            image=image_bgr,
            model_id=model_id,
            engine_type=self.settings.engine,
            device_pref=self.settings.device,
            tile_size=self.settings.tile_size,
            progress_cb=progress_cb,
            is_cancelled=is_cancelled,
        )

        # The models are fixed 4x (or 2x) networks. When the user asks for a
        # smaller factor, reduce the result so the size matches the request.
        in_h, in_w = image_bgr.shape[:2]
        want_w, want_h = in_w * self.settings.scale, in_h * self.settings.scale
        if self.settings.scale in (2, 3, 4) and result.shape[1] != want_w:
            shrinking = result.shape[1] > want_w
            result = cv2.resize(result, (want_w, want_h),
                                interpolation=cv2.INTER_AREA if shrinking else cv2.INTER_LANCZOS4)

        # 2. Face restoration pass if enabled
        if self.settings.face_restoration and self.restorer.is_available:
            result = self.restorer.enhance_image_faces(result, blend=self.settings.face_restorer_blend)

        return result
