"""Single image preview pane with drag-and-drop support."""

from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (QColor, QDragEnterEvent, QDropEvent, QFont, QImage,
                           QPainter, QPixmap)
from PySide6.QtWidgets import QSizePolicy, QWidget

from .. import theme


def to_qimage(image_bgr: np.ndarray) -> QImage:
    """Convert an OpenCV BGR array to an independent QImage."""
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    rgb = np.ascontiguousarray(rgb)
    h, w, ch = rgb.shape
    return QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888).copy()


class ImageView(QWidget):
    fileDropped = Signal(str)

    def __init__(self, placeholder: str = "Drop image here or click Browse", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.placeholder = placeholder
        self._pixmap: QPixmap | None = None
        self._image_size = (0, 0)
        self._draw_rect = QRect()

        self.setAcceptDrops(True)
        self.setMinimumSize(280, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def clear(self) -> None:
        self._pixmap = None
        self._image_size = (0, 0)
        self.update()

    def set_image(self, image_bgr: np.ndarray | None) -> None:
        if image_bgr is None:
            self.clear()
            return
        self._image_size = (image_bgr.shape[1], image_bgr.shape[0])
        self._pixmap = QPixmap.fromImage(to_qimage(image_bgr))
        self.update()

    @property
    def has_image(self) -> bool:
        return self._pixmap is not None

    def _fit_rect(self) -> QRect:
        if self._pixmap is None:
            return QRect()
        avail = self.rect().adjusted(8, 8, -8, -8)
        scaled = self._pixmap.size().scaled(avail.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = avail.x() + (avail.width() - scaled.width()) // 2
        y = avail.y() + (avail.height() - scaled.height()) // 2
        return QRect(QPoint(x, y), scaled)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(theme.BG_INPUT))

        if self._pixmap is None:
            painter.setPen(QColor(theme.TEXT_DIM))
            font = QFont(painter.font())
            font.setPointSize(11)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.placeholder)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = self._draw_rect = self._fit_rect()
        painter.drawPixmap(r, self._pixmap)

        # Draw dimensions overlay badge in top-left
        badge_text = f"{self._image_size[0]} × {self._image_size[1]}"
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        metrics = painter.fontMetrics()
        bw = metrics.horizontalAdvance(badge_text) + 12
        bh = metrics.height() + 6
        badge_rect = QRect(r.x() + 8, r.y() + 8, bw, bh)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.drawRoundedRect(badge_rect, 4, 4)

        painter.setPen(QColor(theme.TEXT))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if urls:
            local_path = urls[0].toLocalFile()
            if local_path:
                self.fileDropped.emit(local_path)
                event.acceptProposedAction()
