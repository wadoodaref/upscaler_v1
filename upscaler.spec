# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the portable one-folder Image Upscaler build.

Driven by build_portable.ps1.
"""

import os

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

# build_portable.ps1 -Console sets this. A console build is the only practical
# way to see a startup traceback, since a windowed exe has nowhere to print.
CONSOLE = os.environ.get("UPSCALER_CONSOLE", "0") == "1"

hidden = collect_submodules("app") + ["cv2"]

# The DirectML provider DLLs sit next to the onnxruntime package and are
# loaded dynamically; make sure they travel with the app.
binaries = collect_dynamic_libs("onnxruntime")

datas = []

a = Analysis(
    ["launch.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    # The build venv is shared with face_swap_v1; keep its heavy packages and
    # the unused Qt modules out of this app.
    excludes=["tkinter", "matplotlib", "scipy", "skimage", "insightface",
              "torch", "onnx", "sympy", "pandas", "IPython", "imageio",
              "imageio_ffmpeg",
              "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtQuick",
              "PySide6.QtQuick3D", "PySide6.QtQml", "PySide6.QtPdf",
              "PySide6.QtCharts", "PySide6.QtDataVisualization",
              "PySide6.QtNetwork", "PySide6.QtSql", "PySide6.QtTest",
              "PySide6.QtOpenGL", "PySide6.QtDesigner"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Upscaler",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,             # UPX-compressed ONNX Runtime DLLs fail to load
    console=CONSOLE,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Upscaler",
)
