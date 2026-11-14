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


def main() -> int:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION}")
    parser.add_argument("--doctor", action="store_true", help="Print hardware diagnostics and exit")
    args = parser.parse_args()

    setup_logging(ROOT / "upscaler.log")

    if args.doctor:
        run_doctor()
        return 0

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
