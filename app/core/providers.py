"""Hardware and execution provider detection (ONNX Runtime & Vulkan CLI)."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

CPU_PROVIDER = "CPUExecutionProvider"
DML_PROVIDER = "DmlExecutionProvider"
CUDA_PROVIDER = "CUDAExecutionProvider"


def get_available_onnx_providers() -> list[str]:
    try:
        import onnxruntime as ort
        return list(ort.get_available_providers())
    except Exception as e:
        log.warning("Could not query ONNX Runtime providers: %s", e)
        return [CPU_PROVIDER]


def resolve_onnx_providers(preference: str = "auto") -> list[str]:
    """Return provider list in priority order based on user selection."""
    have = set(get_available_onnx_providers())
    chain: list[str] = []

    pref = preference.lower()
    if pref == "cpu":
        return [CPU_PROVIDER]

    if pref in ("auto", "gpu", "directml", "cuda"):
        # Prefer CUDA if present and specifically requested or available, otherwise DirectML
        if pref in ("auto", "cuda") and CUDA_PROVIDER in have:
            chain.append(CUDA_PROVIDER)
        elif pref in ("auto", "directml", "gpu") and DML_PROVIDER in have:
            chain.append(DML_PROVIDER)
        elif DML_PROVIDER in have:
            chain.append(DML_PROVIDER)

    if CPU_PROVIDER not in chain:
        chain.append(CPU_PROVIDER)
    return chain


def find_ncnn_executable(models_dir: Path) -> Path | None:
    """Check if realesrgan-ncnn-vulkan.exe exists in models/bin or on PATH."""
    candidates = [
        models_dir / "bin" / "realesrgan-ncnn-vulkan.exe",
        models_dir / "realesrgan-ncnn-vulkan.exe",
        models_dir / "realesrgan-ncnn-vulkan",
    ]
    for c in candidates:
        if c.is_file():
            return c

    which = shutil.which("realesrgan-ncnn-vulkan")
    if which:
        return Path(which)
    return None


def get_system_summary(models_dir: Path) -> dict:
    ort_providers = get_available_onnx_providers()
    ncnn_exe = find_ncnn_executable(models_dir)

    has_dml = DML_PROVIDER in ort_providers
    has_cuda = CUDA_PROVIDER in ort_providers
    has_ncnn = ncnn_exe is not None

    recommended_engine = "onnx" if (has_dml or has_cuda) else ("ncnn" if has_ncnn else "fast_cpu")

    return {
        "ort_providers": ort_providers,
        "has_directml": has_dml,
        "has_cuda": has_cuda,
        "ncnn_executable": str(ncnn_exe) if ncnn_exe else None,
        "recommended_engine": recommended_engine,
        "recommended_provider": DML_PROVIDER if has_dml else (CUDA_PROVIDER if has_cuda else CPU_PROVIDER),
    }
