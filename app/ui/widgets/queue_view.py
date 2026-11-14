"""Batch Queue view for multiple image upscaling."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from .. import theme


class QueueView(QWidget):
    itemSelected = Signal(str)
    removeRequested = Signal(int)
    clearRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Action bar above table
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        self.count_label = QLabel("Queue: 0 items")
        self.count_label.setObjectName("SubHeading")
        top_bar.addWidget(self.count_label)
        top_bar.addStretch()

        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.clicked.connect(self._on_remove)
        top_bar.addWidget(self.btn_remove)

        self.btn_clear = QPushButton("Clear All")
        self.btn_clear.clicked.connect(self.clearRequested)
        top_bar.addWidget(self.btn_clear)
        layout.addLayout(top_bar)

        # Queue table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Filename", "Input Dims", "Output Dims", "Status", "Time"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)

        self._paths: list[str] = []

    def set_items(self, items: list[dict]) -> None:
        self.table.setRowCount(len(items))
        self._paths = []
        for row, item in enumerate(items):
            path_str = str(item.get("input_path", ""))
            self._paths.append(path_str)
            name = Path(path_str).name

            in_dims = item.get("in_dims", "-")
            out_dims = item.get("out_dims", "-")
            status = item.get("status", "Pending")
            duration = item.get("time", "-")

            it_name = QTableWidgetItem(name)
            it_in = QTableWidgetItem(str(in_dims))
            it_out = QTableWidgetItem(str(out_dims))
            it_status = QTableWidgetItem(str(status))
            it_time = QTableWidgetItem(str(duration))

            # Style status
            if status == "Done":
                it_status.setForeground(Qt.GlobalColor.green)
            elif status == "Running":
                it_status.setForeground(Qt.GlobalColor.cyan)
            elif status == "Error":
                it_status.setForeground(Qt.GlobalColor.red)

            self.table.setItem(row, 0, it_name)
            self.table.setItem(row, 1, it_in)
            self.table.setItem(row, 2, it_out)
            self.table.setItem(row, 3, it_status)
            self.table.setItem(row, 4, it_time)

        self.count_label.setText(f"Queue: {len(items)} items")

    def _on_remove(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self._paths):
            self.removeRequested.emit(row)

    def _on_double_click(self, item: QTableWidgetItem) -> None:
        row = item.row()
        if 0 <= row < len(self._paths):
            self.itemSelected.emit(self._paths[row])
