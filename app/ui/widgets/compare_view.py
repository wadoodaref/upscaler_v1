"""Before / After interactive split comparison slider."""

from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (QColor, QFont, QKeyEvent, QMouseEvent, QPainter,
                           QPen, QPixmap)
from PySide6.QtWidgets import QSizePolicy, QWidget

from .. import theme
from .image_view import to_qimage


class CompareView(QWidget):
    dividerChanged = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._before: QPixmap | None = None
        self._after: QPixmap | None = None
        self._before_size = (0, 0)
        self._after_size = (0, 0)
        self._p = 0.5
        self._drag = False
        self._draw_rect = QRect()

        self.setMinimumSize(280, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip("Drag the divider or use Left/Right arrows to compare Before and After")

    def clear(self) -> None:
        self._before = None
        self._after = None
        self._before_size = (0, 0)
        self._after_size = (0, 0)
        self.update()

    def set_pair(self, before_bgr: np.ndarray, after_bgr: np.ndarray) -> None:
        self._before_size = (before_bgr.shape[1], before_bgr.shape[0])
        self._after_size = (after_bgr.shape[1], after_bgr.shape[0])

        ah, aw = after_bgr.shape[:2]
        # Align before to after's dimensions so both draw 1:1 on top of each other
        if before_bgr.shape[:2] != (ah, aw):
            before_aligned = cv2.resize(before_bgr, (aw, ah), interpolation=cv2.INTER_NEAREST)
        else:
            before_aligned = before_bgr

        self._before = QPixmap.fromImage(to_qimage(before_aligned))
        self._after = QPixmap.fromImage(to_qimage(after_bgr))
        self.update()

    @property
    def has_image(self) -> bool:
        return self._after is not None

    @property
    def divider(self) -> float:
        return self._p

    def set_divider(self, p: float) -> None:
        self._p = max(0.0, min(1.0, float(p)))
        self.dividerChanged.emit(self._p)
        self.update()

    def _fit_rect(self) -> QRect:
        if self._after is None:
            return QRect()
        avail = self.rect().adjusted(8, 8, -8, -8)
        scaled = self._after.size().scaled(avail.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = avail.x() + (avail.width() - scaled.width()) // 2
        y = avail.y() + (avail.height() - scaled.height()) // 2
        return QRect(QPoint(x, y), scaled)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(theme.BG_INPUT))

        if self._after is None or self._before is None:
            painter.setPen(QColor(theme.TEXT_DIM))
            font = QFont(painter.font())
            font.setPointSize(11)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No comparison image loaded")
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        r = self._draw_rect = self._fit_rect()

        # 1. Draw "After" (upscaled) as base
        painter.drawPixmap(r, self._after)

        # 2. Draw "Before" (original) clipped to left of split
        split_x = r.x() + int(round(r.width() * self._p))
        painter.save()
        painter.setClipRect(QRect(r.x(), r.y(), max(0, split_x - r.x()), r.height()))
        painter.drawPixmap(r, self._before)
        painter.restore()

        # 3. Draw divider line
        painter.setPen(QPen(QColor(0, 0, 0, 160), 4))
        painter.drawLine(split_x, r.top(), split_x, r.bottom())
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawLine(split_x, r.top(), split_x, r.bottom())

        # 4. Draw central knob
        cy = r.center().y()
        painter.setBrush(QColor(theme.ACCENT))
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawEllipse(QPoint(split_x, cy), 13, 13)

        # 5. Badges: "Original" on left, "Upscaled" on right
        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        painter.setFont(font)

        # Before label (top left)
        b_text = f"Original ({self._before_size[0]}×{self._before_size[1]})"
        metrics = painter.fontMetrics()
        b_rect = QRect(r.x() + 8, r.y() + 8, metrics.horizontalAdvance(b_text) + 12, metrics.height() + 6)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.drawRoundedRect(b_rect, 4, 4)
        painter.setPen(QColor(theme.TEXT))
        painter.drawText(b_rect, Qt.AlignmentFlag.AlignCenter, b_text)

        # After label (top right)
        a_text = f"Upscaled ({self._after_size[0]}×{self._after_size[1]})"
        a_w = metrics.horizontalAdvance(a_text) + 12
        a_rect = QRect(r.right() - a_w - 8, r.y() + 8, a_w, metrics.height() + 6)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.ACCENT))
        painter.drawRoundedRect(a_rect, 4, 4)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(a_rect, Qt.AlignmentFlag.AlignCenter, a_text)

    # -- mouse & keyboard interaction ----------------------------------------

    def _update_from_pos(self, x: int) -> None:
        if self._draw_rect.width() <= 0:
            return
        p = (x - self._draw_rect.x()) / self._draw_rect.width()
        self.set_divider(p)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._after is not None:
            self._drag = True
            self._update_from_pos(int(event.position().x()))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag:
            self._update_from_pos(int(event.position().x()))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = False

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Left:
            self.set_divider(self._p - 0.05)
        elif key == Qt.Key.Key_Right:
            self.set_divider(self._p + 0.05)
        elif key == Qt.Key.Key_Home:
            self.set_divider(0.0)
        elif key == Qt.Key.Key_End:
            self.set_divider(1.0)
        else:
            super().keyPressEvent(event)
