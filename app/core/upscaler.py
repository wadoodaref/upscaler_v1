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

from .models_registry import ModelSpec, get_model, resolve_model_file
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


def _cpu_threads() -> int:
    """Physical-core count (hyper-threads hurt ONNX Runtime's matrix kernels)."""
    logical = os.cpu_count() or 4
    try:
        import ctypes
        from ctypes import wintypes

        size = wintypes.DWORD(0)
        ctypes.windll.kernel32.GetLogicalProcessorInformationEx(0, None, ctypes.byref(size))  # 0 = RelationProcessorCore
        buf = ctypes.create_string_buffer(size.value)
        if ctypes.windll.kernel32.GetLogicalProcessorInformationEx(0, buf, ctypes.byref(size)):
            off = cores = 0
            while off < size.value:
                cores += 1
                off += int.from_bytes(buf.raw[off + 4:off + 8], "little")   # record Size field
            if 0 < cores <= logical:
                return cores
    except Exception:                                              # noqa: BLE001
        pass
    return max(1, logical // 2) if logical >= 4 else logical


class UpscalerEngine:
    def __init__(self, models_dir: Path) -> None:
        self.models_dir = models_dir
        self.current_onnx_model: str | None = None
        self.onnx_session = None
        self.current_provider: str | None = None

    def _get_onnx_session(self, model_spec: ModelSpec, device_pref: str):
        target_path = resolve_model_file(model_spec, self.models_dir)
        if not target_path or not target_path.is_file():
            raise FileNotFoundError(
                f"Model file '{model_spec.filename}' not found in {self.models_dir}.\n"
                f"Please place the model in the models/ directory or choose Fast Algorithmic mode."
            )

        # "Auto": only the heavy Photo networks gain from the GPU (2-3x). The
        # small models run as fast on CPU, and DirectML adds 10-25 s of start-up
        # and kernel compilation per model, so they stay on CPU unless the user
        # picks a GPU explicitly.
        if device_pref == "auto" and model_spec.category != "photo":
            device_pref = "cpu"
        providers = resolve_onnx_providers(device_pref)
        active_provider = providers[0]

        if (
            self.onnx_session is not None
            and self.current_onnx_model == model_spec.id
            and self.current_provider == active_provider
        ):
            return self.onnx_session

        # Release previous session and garbage collect GPU buffers before allocating new session
        if self.onnx_session is not None:
            del self.onnx_session
            self.onnx_session = None
            import gc
            gc.collect()

        import onnxruntime as ort

        sess_opts = ort.SessionOptions()
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_opts.log_severity_level = 3
        if providers[0] == "DmlExecutionProvider":
            # DirectML does not support the memory-pattern optimisation and
            # hangs the GPU (887A0006) under parallel execution. This was the
            # cause of the DirectML "device hung" errors on this machine.
            sess_opts.enable_mem_pattern = False
            sess_opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        else:
            # Measured on a 4-core/8-thread CPU: physical cores beat all
            # logical threads (7.8 s vs 9.9 s per tile).
            sess_opts.intra_op_num_threads = _cpu_threads()

        log.info("Loading ONNX model '%s' with providers: %s", model_spec.id, providers)
        # An explicit device_id matters: without it DirectML picked a state
        # that hung on the Photo model, with it the same model runs cleanly.
        prov_opts = [{"device_id": 0} if p == "DmlExecutionProvider" else {} for p in providers]
        session = ort.InferenceSession(str(target_path), sess_options=sess_opts,
                                       providers=providers, provider_options=prov_opts)
        self.onnx_session = session
        self.current_onnx_model = model_spec.id
        self.current_provider = session.get_providers()[0]
        log.info("Active ONNX Provider: %s", self.current_provider)
        return session

    def _run_onnx_tiling(
        self,
        image: np.ndarray,
        model_spec: ModelSpec,
        device_pref: str,
        tile_size: int,
        progress_cb: Callable[[int, int], None] | None,
        is_cancelled: Callable[[], bool] | None,
    ) -> np.ndarray:
        session = self._get_onnx_session(model_spec, device_pref)
        input_name = session.get_inputs()[0].name

        def forward_tile(tile_bgr: np.ndarray) -> np.ndarray:
            rgb = cv2.cvtColor(tile_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            # Contiguous copy: a strided view of the transpose is what made
            # DirectML hang the GPU (887A0006) on the second tile.
            tensor = np.ascontiguousarray(np.transpose(rgb, (2, 0, 1))[np.newaxis, ...])  # 1, C, H, W
            out = session.run(None, {input_name: tensor})[0][0]
            out = np.clip(np.transpose(out, (1, 2, 0)), 0, 1.0) * 255.0
            return cv2.cvtColor(out.astype(np.uint8), cv2.COLOR_RGB2BGR)

        scale = model_spec.scale
        return process_tiles(
            img=image,
            scale=scale,
            tile_size=tile_size,
            tile_pad=10,           # Real-ESRGAN's own default; 16 cost ~10% more compute per tile
            forward_fn=forward_tile,
            progress_callback=progress_cb,
            is_cancelled=is_cancelled,
            fixed_shape=(self.current_provider == "DmlExecutionProvider"),
        )

    def upscale_onnx(
        self,
        image: np.ndarray,
        model_spec: ModelSpec,
        device_pref: str = "auto",
        tile_size: int = 256,
        progress_cb: Callable[[int, int], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> np.ndarray:
        try:
            return self._run_onnx_tiling(image, model_spec, device_pref, tile_size, progress_cb, is_cancelled)
        except Exception as e:
            if device_pref != "cpu":
                log.warning("ONNX execution failed on '%s' (%s). Retrying on CPUExecutionProvider fallback...", device_pref, e)
                if self.onnx_session is not None:
                    del self.onnx_session
                    self.onnx_session = None
                    self.current_onnx_model = None
                    import gc
                    gc.collect()
                return self._run_onnx_tiling(image, model_spec, "cpu", tile_size, progress_cb, is_cancelled)
            raise

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
        model_file = resolve_model_file(spec, self.models_dir)
        if engine_type == "onnx" or (engine_type == "auto" and model_file is not None):
            if model_file is not None:
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
