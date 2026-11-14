"""Application entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import providers
from .util.config import APP_NAME, APP_VERSION, MODELS_DIR, ROOT
from .util.logging_setup import setup_logging


def run_doctor() -> None:
    print(f"=== {APP_NAME} v{APP_VERSION} Hardware Doctor ===")
    summary = providers.get_system_summary(MODELS_DIR)
    print(f"DirectML (DirectX 12 GPU): {'Available' if summary['has_directml'] else 'Not available'}")
    print(f"CUDA (NVIDIA):             {'Available' if summary['has_cuda'] else 'Not available'}")
    print(f"NCNN Vulkan Executable:    {summary['ncnn_executable'] or 'Not found in models/'}")
    print(f"Available ONNX Providers:  {summary['ort_providers']}")
    print(f"Recommended Engine:        {summary['recommended_engine']}")
    print(f"Recommended Provider:      {summary['recommended_provider']}")
    print("==================================================")


def run_selftest() -> int:
    """Headless end-to-end check, used to verify a portable build.

    Runs every installed model once on a small synthetic picture, loads the
    face restorer, and writes selftest.json next to the app. The windowed exe
    has no console, so the file (and the exit code) is the result.
    """
    import json
    import logging
    import time

    import cv2
    import numpy as np

    from .core import models_registry as registry
    from .core.pipeline import UpscalePipeline
    from .util.config import Settings

    log = logging.getLogger("selftest")
    report: dict = {"root": str(ROOT), "frozen": bool(getattr(sys, "frozen", False)),
                    "providers": providers.get_available_onnx_providers(), "models": {}, "ok": True}
    rng = np.random.default_rng(0)
    img = cv2.GaussianBlur(rng.integers(0, 255, (96, 128, 3), dtype=np.uint8), (0, 0), 2)

    for device in ("auto", "cpu"):
        for spec in registry.MODELS:
            if not registry.is_model_installed(spec, MODELS_DIR):
                continue
            key = f"{spec.id}@{device}"
            try:
                s = Settings(model=spec.id, device=device, scale=spec.scale, tile_size=64)
                pipe = UpscalePipeline(s, MODELS_DIR)
                t0 = time.time()
                out = pipe.process_image(img)
                want = (img.shape[0] * spec.scale, img.shape[1] * spec.scale)
                good = out.shape[:2] == want and float(out.std()) > 1.0
                report["models"][key] = {"ok": good, "shape": list(out.shape), "seconds": round(time.time() - t0, 2),
                                         "provider": pipe.engine.current_provider or "algorithmic"}
                report["ok"] &= good
            except Exception as e:                                 # noqa: BLE001
                log.exception("selftest %s failed", key)
                report["models"][key] = {"ok": False, "error": str(e)}
                report["ok"] = False

    try:
        pipe = UpscalePipeline(Settings(device="cpu"), MODELS_DIR)
        face = cv2.resize(img, (512, 512))
        restored = pipe.restorer.restore_face_crop(face)
        faces = pipe.restorer.detect_faces(face)          # noise: must run, finds none
        whole = pipe.restorer.enhance_image_faces(face)
        report["face_restorer"] = {"ok": restored.shape == (512, 512, 3) and whole.shape == face.shape,
                                   "available": pipe.restorer.is_available,
                                   "faces_in_noise": len(faces)}
        report["ok"] &= pipe.restorer.is_available
        report["ok"] &= report["face_restorer"]["ok"]
    except Exception as e:                                         # noqa: BLE001
        log.exception("selftest face restorer failed")
        report["face_restorer"] = {"ok": False, "error": str(e)}
        report["ok"] = False

    (ROOT / "selftest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log.info("selftest %s", "PASSED" if report["ok"] else "FAILED")
    return 0 if report["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION}")
    parser.add_argument("--doctor", action="store_true", help="Print hardware diagnostics and exit")
    parser.add_argument("--selftest", action="store_true", help="Run a headless end-to-end check and exit")
    args = parser.parse_args()

    setup_logging(ROOT / "upscaler.log")

    if args.doctor:
        run_doctor()
        return 0

    if args.selftest:
        return run_selftest()

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from .ui.main_window import MainWindow

    # High DPI scaling settings
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
