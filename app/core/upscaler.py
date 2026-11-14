"""Core Upscaling Engine supporting ONNX Runtime (DirectML/CPU), NCNN-Vulkan, and Fast Algorithmic CPU."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from .models_registry import ModelSpec, get_model
from .providers import CPU_PROVIDER, find_ncnn_executable, resolve_onnx_providers
from .tiler import process_tiles

log = logging.getLogger(__name__)


def unsharp_mask(image: np.ndarray, sigma: float = 1.0, strength: float = 1.3, threshold: int = 3) -> np.ndarray:
    """Enhance edges and fine texture after interpolation."""
    blurred = cv2.GaussianBlur(image, (0, 0), sigma)
    diff = cv2.absdiff(image, blurred)
    mask = diff > threshold
    sharpened = image.astype(np.float32) + strength * (image.astype(np.float32) - blurred.astype(np.float32))
    sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)
    return np.where(mask, sharpened, image)


def upscale_algorithmic(
    image: np.ndarray,
    scale: int = 4,
    method: str = "lanczos",
    progress_cb: Callable[[int, int], None] | None = None,
) -> np.ndarray:
    """High-quality CPU-native upscaling using advanced interpolation and unsharp masking.
    Zero external dependencies, instant execution on any low-end CPU.
    """
    h, w = image.shape[:2]
    interp = cv2.INTER_LANCZOS4 if method == "lanczos" else cv2.INTER_CUBIC

    if progress_cb:
        progress_cb(1, 3)

    # Step 1: High-order spatial interpolation
    scaled = cv2.resize(image, (w * scale, h * scale), interpolation=interp)

    if progress_cb:
        progress_cb(2, 3)

    # Step 2: Edge-preserving sharpening pass
    enhanced = unsharp_mask(scaled, sigma=1.2, strength=0.8, threshold=2)

    if progress_cb:
        progress_cb(3, 3)

    return enhanced


class UpscalerEngine:
    def __init__(self, models_dir: Path) -> None:
        self.models_dir = models_dir
        self.current_onnx_model: str | None = None
        self.onnx_session = None
        self.current_provider: str | None = None

    def _get_onnx_session(self, model_spec: ModelSpec, device_pref: str):
        target_path = self.models_dir / model_spec.filename
        if not target_path.is_file():
            raise FileNotFoundError(
                f"Model file '{model_spec.filename}' not found in {self.models_dir}.\n"
                f"Please place the model in the models/ directory or choose Fast Algorithmic mode."
            )

        providers = resolve_onnx_providers(device_pref)
        active_provider = providers[0]

        if (
            self.onnx_session is not None
            and self.current_onnx_model == model_spec.id
            and self.current_provider == active_provider
        ):
            return self.onnx_session

        import onnxruntime as ort

        sess_opts = ort.SessionOptions()
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_opts.intra_op_num_threads = max(1, os.cpu_count() or 4)

        log.info("Loading ONNX model '%s' with providers: %s", model_spec.id, providers)
        session = ort.InferenceSession(str(target_path), sess_options=sess_opts, providers=providers)
        self.onnx_session = session
        self.current_onnx_model = model_spec.id
        self.current_provider = session.get_providers()[0]
        log.info("Active ONNX Provider: %s", self.current_provider)
        return session

    def upscale_onnx(
        self,
        image: np.ndarray,
        model_spec: ModelSpec,
        device_pref: str = "auto",
        tile_size: int = 256,
        progress_cb: Callable[[int, int], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> np.ndarray:
        session = self._get_onnx_session(model_spec, device_pref)
        input_name = session.get_inputs()[0].name

        def forward_tile(tile_bgr: np.ndarray) -> np.ndarray:
            rgb = cv2.cvtColor(tile_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            tensor = np.transpose(rgb, (2, 0, 1))[np.newaxis, ...]  # 1, C, H, W
            out = session.run(None, {input_name: tensor})[0][0]
            out = np.clip(np.transpose(out, (1, 2, 0)), 0, 1.0) * 255.0
            return cv2.cvtColor(out.astype(np.uint8), cv2.COLOR_RGB2BGR)

        scale = model_spec.scale
        return process_tiles(
            img=image,
            scale=scale,
            tile_size=tile_size,
            tile_pad=16,
            forward_fn=forward_tile,
            progress_callback=progress_cb,
            is_cancelled=is_cancelled,
        )

    def upscale_ncnn_cli(
        self,
        image: np.ndarray,
        model_spec: ModelSpec,
        tile_size: int = 200,
        gpu_id: int = 0,
        progress_cb: Callable[[int, int], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> np.ndarray:
        ncnn_exe = find_ncnn_executable(self.models_dir)
        if not ncnn_exe:
            raise FileNotFoundError("realesrgan-ncnn-vulkan.exe was not found.")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_in = Path(tmpdir) / "input.png"
            tmp_out = Path(tmpdir) / "output.png"
            cv2.imwrite(str(tmp_in), image)

            model_name = model_spec.id
            cmd = [
                str(ncnn_exe),
                "-i", str(tmp_in),
                "-o", str(tmp_out),
                "-s", str(model_spec.scale),
                "-n", model_name,
                "-t", str(tile_size if tile_size > 0 else 0),
                "-g", str(gpu_id),
            ]

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

            percent_re = re.compile(r"(\d+(?:\.\d+)?)%")
            while True:
                if is_cancelled and is_cancelled():
                    proc.terminate()
                    raise InterruptedError("Cancelled by user")

                line = proc.stdout.readline() if proc.stdout else ""
                if not line and proc.poll() is not None:
                    break
                if line:
                    m = percent_re.search(line)
                    if m and progress_cb:
                        pct = int(float(m.group(1)))
                        progress_cb(pct, 100)

            proc.wait()
            if proc.returncode != 0 or not tmp_out.is_file():
                raise RuntimeError(f"NCNN process failed with exit code {proc.returncode}")

            return cv2.imread(str(tmp_out))

    def upscale(
        self,
        image: np.ndarray,
        model_id: str,
        engine_type: str = "auto",
        device_pref: str = "auto",
        tile_size: int = 256,
        progress_cb: Callable[[int, int], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> np.ndarray:
        spec = get_model(model_id)

        # 1. Explicit Algorithmic / Fast CPU mode
        if spec.category == "algorithmic" or engine_type == "fast_cpu":
            method = "lanczos" if "lanczos" in model_id else "cubic"
            return upscale_algorithmic(image, scale=spec.scale, method=method, progress_cb=progress_cb)

        # 2. Check if ONNX model is available locally
        model_file = self.models_dir / spec.filename
        if engine_type == "onnx" or (engine_type == "auto" and model_file.is_file()):
            if model_file.is_file():
                return self.upscale_onnx(
                    image=image,
                    model_spec=spec,
                    device_pref=device_pref,
                    tile_size=tile_size,
                    progress_cb=progress_cb,
                    is_cancelled=is_cancelled,
                )

        # 3. NCNN Vulkan
        ncnn_exe = find_ncnn_executable(self.models_dir)
        if engine_type == "ncnn" or (engine_type == "auto" and ncnn_exe):
            if ncnn_exe:
                gpu_id = -1 if device_pref == "cpu" else 0
                return self.upscale_ncnn_cli(
                    image=image,
                    model_spec=spec,
                    tile_size=tile_size,
                    gpu_id=gpu_id,
                    progress_cb=progress_cb,
                    is_cancelled=is_cancelled,
                )

        # 4. Graceful Fallback if model files are not yet on disk: run Fast Lanczos
        log.warning("No neural model file found for '%s'; falling back to Fast Lanczos upscaler.", model_id)
        return upscale_algorithmic(image, scale=spec.scale, method="lanczos", progress_cb=progress_cb)
