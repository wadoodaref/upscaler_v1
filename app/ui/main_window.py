"""Main Window for Image Upscaler Desktop."""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout,
                               QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QMainWindow, QMessageBox, QProgressBar,
                               QPushButton, QScrollArea, QSlider, QSpinBox,
                               QTabWidget, QVBoxLayout, QWidget)

from ..core import models_registry as registry
from ..core import providers
from ..core.pipeline import UpscaleJob, UpscalePipeline
from ..util.config import (APP_NAME, APP_VERSION, IMAGE_EXTS, MODELS_DIR,
                           OUTPUT_DIR, Settings, is_image)
from . import theme
from .eta import Eta
from .widgets.compare_view import CompareView
from .widgets.image_view import ImageView
from .widgets.queue_view import QueueView

log = logging.getLogger(__name__)


def make_panel(title: str, subtitle: str = "") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Panel")
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(12, 10, 12, 12)
    outer.setSpacing(8)

    heading = QLabel(title)
    heading.setObjectName("Heading")
    outer.addWidget(heading)

    if subtitle:
        sub = QLabel(subtitle)
        sub.setObjectName("SubHeading")
        sub.setWordWrap(True)
        outer.addWidget(sub)

    return frame, outer


class WorkerSignals(QObject):
    progress = Signal(int, int, str)               # current, total, message
    job_finished = Signal(object, object)          # UpscaleJob, output_bgr
    batch_finished = Signal()
    error = Signal(str)


class UpscaleWorker(QThread):
    def __init__(self, pipeline: UpscalePipeline, jobs: list[UpscaleJob], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.pipeline = pipeline
        self.jobs = jobs
        self.signals = WorkerSignals()
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self) -> None:
        total_jobs = len(self.jobs)
        for idx, job in enumerate(self.jobs):
            if self._cancelled:
                job.status = "Cancelled"
                break

            job.status = "Running"
            start_t = time.time()
            self.signals.progress.emit(0, 100, f"Processing {job.input_path.name} ({idx+1}/{total_jobs})...")

            try:
                img_in = self.pipeline.load_image(job.input_path)
                h, w = img_in.shape[:2]
                job.original_dims = (w, h)

                def tile_cb(cur: int, tot: int) -> None:
                    pct = int((cur / max(1, tot)) * 100)
                    self.signals.progress.emit(pct, 100, f"Tile {cur}/{tot} ({pct}%)")

                result_bgr = self.pipeline.process_image(
                    image_bgr=img_in,
                    progress_cb=tile_cb,
                    is_cancelled=self.is_cancelled,
                )

                rh, rw = result_bgr.shape[:2]
                job.output_dims = (rw, rh)

                # Save to disk
                self.pipeline.save_image(result_bgr, job.output_path, quality=self.pipeline.settings.jpg_quality)
                job.elapsed_seconds = time.time() - start_t
                job.status = "Done"

                self.signals.job_finished.emit(job, result_bgr)

            except InterruptedError:
                job.status = "Cancelled"
                break

            except Exception as e:
                log.exception("Error processing %s", job.input_path)
                job.status = "Error"
                job.message = str(e)
                self.signals.error.emit(f"Failed processing {job.input_path.name}: {e}")

        self.signals.batch_finished.emit()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1280, 820)
        self.setStyleSheet(theme.STYLESHEET)

        self.settings = Settings.load()
        self.pipeline = UpscalePipeline(self.settings, MODELS_DIR)

        self.current_input_path: Path | None = None
        self.current_input_bgr: np.ndarray | None = None
        self.current_output_bgr: np.ndarray | None = None

        self.queue_jobs: list[UpscaleJob] = []
        self.worker: UpscaleWorker | None = None
        self.eta: Eta | None = None

        self._build_ui()
        self._refresh_hardware_status()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(14)

        # ================= LEFT SIDEBAR (Controls) =================
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedWidth(400)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        controls_container = QWidget()
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setContentsMargins(0, 0, 8, 0)
        controls_layout.setSpacing(10)

        # 1. Input Panel
        p_in, l_in = make_panel("1. Input Image", "Select a photo or drag & drop onto the preview")
        btn_row_in = QHBoxLayout()
        self.btn_browse_file = QPushButton("Browse Image...")
        self.btn_browse_file.clicked.connect(self._on_browse_file)
        self.btn_browse_folder = QPushButton("Add Folder...")
        self.btn_browse_folder.clicked.connect(self._on_browse_folder)
        btn_row_in.addWidget(self.btn_browse_file)
        btn_row_in.addWidget(self.btn_browse_folder)
        l_in.addLayout(btn_row_in)

        self.lbl_input_path = QLabel("No image selected")
        self.lbl_input_path.setObjectName("SubHeading")
        self.lbl_input_path.setWordWrap(True)
        l_in.addWidget(self.lbl_input_path)
        controls_layout.addWidget(p_in)

        # 2. Hardware & Engine Panel
        p_hw, l_hw = make_panel("2. Engine & Hardware", "Acceleration provider and execution mode")
        hw_form = QFormLayout()
        hw_form.setSpacing(8)

        self.combo_engine = QComboBox()
        self.combo_engine.addItems([
            "Auto (Best Available)",
            "ONNX Runtime (DirectML / CPU)",
            "NCNN Vulkan (CLI Sidecar)",
            "Fast CPU (Algorithmic / No GPU)",
        ])
        engine_idx = {"auto": 0, "onnx": 1, "ncnn": 2, "fast_cpu": 3}.get(self.settings.engine, 0)
        self.combo_engine.setCurrentIndex(engine_idx)
        self.combo_engine.currentIndexChanged.connect(self._on_engine_changed)
        hw_form.addRow("Engine:", self.combo_engine)

        self.combo_device = QComboBox()
        self.combo_device.addItems([
            "Auto (Detect Best)",
            "DirectML (Any Windows GPU / iGPU)",
            "CUDA (NVIDIA only)",
            "CPU (Multi-Threaded)",
        ])
        dev_idx = {"auto": 0, "directml": 1, "cuda": 2, "cpu": 3}.get(self.settings.device, 0)
        self.combo_device.setCurrentIndex(dev_idx)
        self.combo_device.currentIndexChanged.connect(self._on_device_changed)
        hw_form.addRow("Device:", self.combo_device)

        l_hw.addLayout(hw_form)
        self.lbl_hw_status = QLabel("Detecting hardware...")
        self.lbl_hw_status.setObjectName("SubHeading")
        l_hw.addWidget(self.lbl_hw_status)
        controls_layout.addWidget(p_hw)

        # 3. Model & Quality Settings Panel
        p_mod, l_mod = make_panel("3. Model & Quality", "Choose upscaling model and tiling size")
        mod_form = QFormLayout()
        mod_form.setSpacing(8)

        self.combo_model = QComboBox()
        # Offline app: only offer models whose weights are actually on disk.
        # A listed-but-missing model would silently run as plain Lanczos.
        for m in registry.MODELS:
            if registry.is_model_installed(m, MODELS_DIR):
                self.combo_model.addItem(f"{m.name} ({m.scale}x)", m.id)
        # Select current model
        idx = max(0, self.combo_model.findData(self.settings.model))
        self.combo_model.setCurrentIndex(idx)
        self.settings.model = self.combo_model.itemData(idx)
        self.combo_model.currentIndexChanged.connect(self._on_model_changed)
        mod_form.addRow("Model:", self.combo_model)

        self.combo_scale = QComboBox()
        self.combo_scale.addItems(["4x", "2x"])
        self.combo_scale.setCurrentText(f"{self.settings.scale}x")
        self.combo_scale.currentTextChanged.connect(self._on_scale_changed)
        mod_form.addRow("Scale:", self.combo_scale)

        self.combo_tile = QComboBox()
        self.combo_tile.addItems([
            "256 px (Recommended for Low VRAM & CPU)",
            "200 px (Ultra-Safe Low RAM)",
            "400 px (Faster on 4GB+ GPUs)",
            "No Tiling (Full Image)",
        ])
        tile_map = {256: 0, 200: 1, 400: 2, 0: 3}
        self.combo_tile.setCurrentIndex(tile_map.get(self.settings.tile_size, 0))
        self.combo_tile.currentIndexChanged.connect(self._on_tile_changed)
        mod_form.addRow("Tiling:", self.combo_tile)

        l_mod.addLayout(mod_form)

        # Face restoration checkbox
        self.chk_face_restore = QCheckBox("Enable Face Restoration (GFPGAN)")
        self.chk_face_restore.setChecked(self.settings.face_restoration)
        self.chk_face_restore.toggled.connect(self._on_face_restore_toggled)
        l_mod.addWidget(self.chk_face_restore)

        self.lbl_face_status = QLabel("")
        self.lbl_face_status.setObjectName("SubHeading")
        l_mod.addWidget(self.lbl_face_status)
        self._update_face_restorer_ui()

        controls_layout.addWidget(p_mod)

        # 4. Output Panel
        p_out, l_out = make_panel("4. Output Destination", "Format, quality, and directory")
        out_form = QFormLayout()
        out_form.setSpacing(8)

        self.combo_format = QComboBox()
        self.combo_format.addItems(["PNG (Lossless)", "JPG", "WEBP"])
        fmt_map = {"png": 0, "jpg": 1, "webp": 2}
        self.combo_format.setCurrentIndex(fmt_map.get(self.settings.output_format, 0))
        self.combo_format.currentIndexChanged.connect(self._on_format_changed)
        out_form.addRow("Format:", self.combo_format)

        # Quality slider
        self.slider_quality = QSlider(Qt.Orientation.Horizontal)
        self.slider_quality.setRange(50, 100)
        self.slider_quality.setValue(self.settings.jpg_quality)
        self.lbl_quality_val = QLabel(f"{self.settings.jpg_quality}%")
        self.slider_quality.valueChanged.connect(self._on_quality_changed)
        q_row = QHBoxLayout()
        q_row.addWidget(self.slider_quality)
        q_row.addWidget(self.lbl_quality_val)
        out_form.addRow("Quality:", q_row)
        l_out.addLayout(out_form)

        # Output folder row
        dir_row = QHBoxLayout()
        self.txt_out_dir = QLineEdit(self.settings.output_dir)
        self.txt_out_dir.setReadOnly(True)
        self.btn_browse_out = QPushButton("...")
        self.btn_browse_out.setFixedWidth(36)
        self.btn_browse_out.clicked.connect(self._on_browse_output_dir)
        self.btn_open_out = QPushButton("Open Folder")
        self.btn_open_out.clicked.connect(self._on_open_output_folder)
        dir_row.addWidget(self.txt_out_dir)
        dir_row.addWidget(self.btn_browse_out)
        dir_row.addWidget(self.btn_open_out)
        l_out.addLayout(dir_row)
        controls_layout.addWidget(p_out)

        # 5. Actions Panel
        p_act, l_act = make_panel("Execution")
        btn_action_row = QHBoxLayout()
        self.btn_start = QPushButton("Start Upscale")
        self.btn_start.setObjectName("Primary")
        self.btn_start.clicked.connect(self._on_start_upscale)
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("Danger")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop_upscale)
        btn_action_row.addWidget(self.btn_start)
        btn_action_row.addWidget(self.btn_stop)
        l_act.addLayout(btn_action_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        l_act.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Ready")
        self.lbl_status.setObjectName("SubHeading")
        l_act.addWidget(self.lbl_status)

        self.lbl_eta = QLabel("")
        self.lbl_eta.setObjectName("SubHeading")
        l_act.addWidget(self.lbl_eta)

        controls_layout.addWidget(p_act)
        controls_layout.addStretch()

        scroll_area.setWidget(controls_container)
        root_layout.addWidget(scroll_area)

        # ================= RIGHT TABS / PREVIEW VIEWPORT =================
        self.tabs = QTabWidget()

        # Tab 1: Interactive Split Comparison View
        self.compare_view = CompareView()
        self.compare_view.set_divider(self.settings.divider_pos)
        self.compare_view.dividerChanged.connect(self._on_divider_changed)
        self.tabs.addTab(self.compare_view, "Before / After Split")

        # Tab 2: Single Preview / Drop Area
        self.image_view = ImageView("Drop an image here to load and upscale")
        self.image_view.fileDropped.connect(self.load_input_file)
        self.tabs.addTab(self.image_view, "Source Preview")

        # Tab 3: Batch Queue
        self.queue_view = QueueView()
        self.queue_view.itemSelected.connect(self._on_queue_item_selected)
        self.queue_view.removeRequested.connect(self._on_queue_remove)
        self.queue_view.clearRequested.connect(self._on_queue_clear)
        self.tabs.addTab(self.queue_view, "Batch Queue (0)")

        root_layout.addWidget(self.tabs, stretch=1)

    # -- Hardware & Model Logic ----------------------------------------------

    def _refresh_hardware_status(self) -> None:
        summary = providers.get_system_summary(MODELS_DIR)
        parts = []
        if summary["has_directml"]:
            parts.append("DirectML (GPU) OK")
        if summary["has_cuda"]:
            parts.append("CUDA OK")
        if summary["ncnn_executable"]:
            parts.append("NCNN Vulkan OK")
        parts.append("CPU Vectorized OK")
        self.lbl_hw_status.setText(" | ".join(parts))

    def _update_face_restorer_ui(self) -> None:
        if self.pipeline.restorer.is_available:
            self.lbl_face_status.setText("Face detector + GFPGAN v1.4 ready.")
            self.lbl_face_status.setStyleSheet(f"color: {theme.OK};")
            self.chk_face_restore.setEnabled(True)
        else:
            missing = ", ".join(self.pipeline.restorer.missing)
            self.lbl_face_status.setText(f"Missing in models folder: {missing}")
            self.lbl_face_status.setStyleSheet(f"color: {theme.WARN};")
            self.chk_face_restore.setEnabled(False)

    # -- User Event Handlers -------------------------------------------------

    def _on_engine_changed(self, idx: int) -> None:
        engines = ["auto", "onnx", "ncnn", "fast_cpu"]
        self.settings.engine = engines[idx]
        self.settings.save()

    def _on_device_changed(self, idx: int) -> None:
        devices = ["auto", "directml", "cuda", "cpu"]
        self.settings.device = devices[idx]
        self.settings.save()

    def _on_model_changed(self, idx: int) -> None:
        model_id = self.combo_model.itemData(idx)
        if model_id:
            self.settings.model = model_id
            spec = registry.get_model(model_id)
            self.combo_scale.setCurrentText(f"{spec.scale}x")
            self.settings.save()

    def _on_scale_changed(self, text: str) -> None:
        self.settings.scale = int(text.replace("x", ""))
        self.settings.save()

    def _on_tile_changed(self, idx: int) -> None:
        tiles = [256, 200, 400, 0]
        self.settings.tile_size = tiles[idx]
        self.settings.save()

    def _on_face_restore_toggled(self, checked: bool) -> None:
        self.settings.face_restoration = checked
        self.settings.save()

    def _on_format_changed(self, idx: int) -> None:
        fmts = ["png", "jpg", "webp"]
        self.settings.output_format = fmts[idx]
        self.slider_quality.setEnabled(fmts[idx] in ("jpg", "webp"))
        self.settings.save()

    def _on_quality_changed(self, val: int) -> None:
        self.settings.jpg_quality = val
        self.lbl_quality_val.setText(f"{val}%")
        self.settings.save()

    def _on_divider_changed(self, pos: float) -> None:
        self.settings.divider_pos = pos
        self.settings.save()

    def _on_browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image to Upscale",
            self.settings.last_input_dir,
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tiff)",
        )
        if path:
            self.load_input_file(path)

    def _on_browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Folder with Images", self.settings.last_input_dir)
        if not folder:
            return
        folder_path = Path(folder)
        images = [p for p in folder_path.iterdir() if is_image(p)]
        if not images:
            QMessageBox.information(self, "No Images Found", f"No supported images found in:\n{folder}")
            return

        for p in images:
            self._enqueue_file(p)

        self._sync_queue_view()
        self.tabs.setCurrentIndex(2)  # Switch to Queue tab
        self.lbl_status.setText(f"Added {len(images)} images to queue.")

    def _on_browse_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.settings.output_dir)
        if folder:
            self.settings.output_dir = folder
            self.txt_out_dir.setText(folder)
            self.settings.save()

    def _on_open_output_folder(self) -> None:
        out_p = Path(self.settings.output_dir)
        out_p.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(out_p))
        else:
            subprocess.Popen(["xdg-open", str(out_p)])

    # -- Queue & Input Management -------------------------------------------

    def load_input_file(self, path_str: str) -> None:
        p = Path(path_str)
        if not p.is_file() or not is_image(p):
            return

        self.current_input_path = p
        self.settings.last_input_dir = str(p.parent)
        self.settings.save()

        try:
            img = self.pipeline.load_image(p)
            self.current_input_bgr = img
            self.current_output_bgr = None

            self.lbl_input_path.setText(f"{p.name} ({img.shape[1]}×{img.shape[0]})")
            self.image_view.set_image(img)
            self.compare_view.clear()

            # Also ensure it's in the queue
            if not any(j.input_path == p for j in self.queue_jobs):
                self._enqueue_file(p)
                self._sync_queue_view()

            self.tabs.setCurrentIndex(1)  # View source
            self.lbl_status.setText(f"Loaded: {p.name}")
        except Exception as e:
            QMessageBox.warning(self, "Error Loading Image", str(e))

    def _enqueue_file(self, p: Path) -> None:
        ext = f".{self.settings.output_format}"
        out_name = f"{p.stem}_upscaled_{self.settings.scale}x{ext}"
        out_path = Path(self.settings.output_dir) / out_name
        self.queue_jobs.append(UpscaleJob(input_path=p, output_path=out_path))

    def _sync_queue_view(self) -> None:
        items = []
        for j in self.queue_jobs:
            items.append({
                "input_path": str(j.input_path),
                "in_dims": f"{j.original_dims[0]}×{j.original_dims[1]}" if j.original_dims[0] > 0 else "-",
                "out_dims": f"{j.output_dims[0]}×{j.output_dims[1]}" if j.output_dims[0] > 0 else "-",
                "status": j.status,
                "time": f"{j.elapsed_seconds:.1f}s" if j.elapsed_seconds > 0 else "-",
            })
        self.queue_view.set_items(items)
        self.tabs.setTabText(2, f"Batch Queue ({len(self.queue_jobs)})")

    def _on_queue_item_selected(self, path_str: str) -> None:
        self.load_input_file(path_str)

    def _on_queue_remove(self, row: int) -> None:
        if 0 <= row < len(self.queue_jobs):
            self.queue_jobs.pop(row)
            self._sync_queue_view()

    def _on_queue_clear(self) -> None:
        self.queue_jobs.clear()
        self._sync_queue_view()

    # -- Processing Execution ------------------------------------------------

    def _on_start_upscale(self) -> None:
        pending_jobs = [j for j in self.queue_jobs if j.status in ("pending", "Error", "Cancelled")]
        if not pending_jobs:
            if self.current_input_path:
                self._enqueue_file(self.current_input_path)
                pending_jobs = [self.queue_jobs[-1]]
            else:
                QMessageBox.information(self, "No Images", "Please select an image or add items to the queue first.")
                return

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self.eta = Eta(len(pending_jobs))

        self.worker = UpscaleWorker(self.pipeline, pending_jobs)
        self.worker.signals.progress.connect(self._on_worker_progress)
        self.worker.signals.job_finished.connect(self._on_worker_job_finished)
        self.worker.signals.batch_finished.connect(self._on_worker_batch_finished)
        self.worker.signals.error.connect(self._on_worker_error)
        self.worker.start()

    def _on_stop_upscale(self) -> None:
        if self.worker:
            self.lbl_status.setText("Cancelling...")
            self.worker.cancel()

    def _on_worker_progress(self, cur: int, tot: int, msg: str) -> None:
        self.progress_bar.setValue(cur)
        self.lbl_status.setText(msg)
        if self.eta:
            self.lbl_eta.setText(self.eta.formatted_status())

    def _on_worker_job_finished(self, job: UpscaleJob, out_bgr: np.ndarray) -> None:
        self._sync_queue_view()
        if self.eta:
            self.eta.update(self.eta.done + 1)
            self.lbl_eta.setText(self.eta.formatted_status())

        # If this finished job matches the currently inspected image, update CompareView!
        if self.current_input_path and job.input_path == self.current_input_path and self.current_input_bgr is not None:
            self.current_output_bgr = out_bgr
            self.compare_view.set_pair(self.current_input_bgr, out_bgr)
            self.tabs.setCurrentIndex(0)  # Show Split comparison
        elif self.current_input_bgr is None:
            img_in = self.pipeline.load_image(job.input_path)
            self.current_input_bgr = img_in
            self.current_output_bgr = out_bgr
            self.compare_view.set_pair(img_in, out_bgr)
            self.tabs.setCurrentIndex(0)

    def _on_worker_batch_finished(self) -> None:
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setValue(100)
        failed = sum(1 for j in self.queue_jobs if j.status == "Error")
        cancelled = sum(1 for j in self.queue_jobs if j.status == "Cancelled")
        if failed:
            self.lbl_status.setText(f"Finished with {failed} failed image(s) - see upscaler.log")
        elif cancelled:
            self.lbl_status.setText("Stopped.")
        else:
            self.lbl_status.setText("All upscaling completed successfully!")
        self._sync_queue_view()
        self.worker = None

    def _on_worker_error(self, err_msg: str) -> None:
        self.lbl_status.setText(f"Error: {err_msg}")
