"""Top-level entry point for frozen (PyInstaller) builds.

PyInstaller runs its entry script as ``__main__`` with no package context, so
freezing ``app/main.py`` directly makes every relative import in it fail before
logging is configured. Importing ``app.main`` from a top-level script keeps
``__package__`` intact. Running from source uses ``python -m app.main``.
"""

from __future__ import annotations

import sys


def _report_fatal(exc: BaseException) -> None:
    """Surface a startup failure even when there is no console attached."""
    import traceback

    detail = "".join(traceback.format_exception(exc))
    if sys.stderr is not None:
        print(detail, file=sys.stderr)

    try:
        from pathlib import Path

        root = Path(sys.executable).resolve().parent \
            if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        (root / "startup_error.log").write_text(detail, encoding="utf-8")
    except Exception:
        pass

    if "--selftest" in sys.argv[1:]:
        return                      # headless run: never block on a dialog

    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            f"Image Upscaler could not start.\n\n{exc}\n\n"
            "Details were written to startup_error.log next to the program.",
            "Image Upscaler - startup error",
            0x10,
        )
    except Exception:
        pass


if __name__ == "__main__":
    try:
        from app.main import main

        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as exc:                              # noqa: BLE001
        _report_fatal(exc)
        sys.exit(1)
