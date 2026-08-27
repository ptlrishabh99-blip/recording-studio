"""Lightweight in-app stream preview.

Runs as its own QThread, pulling frames from the stream with OpenCV at a
reduced sampling rate (a few fps is plenty for a "does this look right"
preview) and handing them to the UI as QImages. This is intentionally a
separate connection from the ffmpeg recording process, so previewing does
not touch the file being written.
"""
from __future__ import annotations

import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage


class PreviewThread(QThread):
    frame_ready = Signal(QImage)
    error = Signal(str)
    finished_preview = Signal()

    def __init__(self, stream_url: str, target_fps: float = 6.0, parent=None):
        super().__init__(parent)
        self.stream_url = stream_url
        self.target_fps = max(target_fps, 0.5)
        self._running = False

    def run(self):
        self._running = True
        cap = cv2.VideoCapture(self.stream_url)
        if not cap.isOpened():
            self.error.emit("Could not open the stream for preview.")
            self.finished_preview.emit()
            return

        delay_ms = int(1000 / self.target_fps)
        while self._running:
            ok, frame = cap.read()
            if not ok:
                self.error.emit("Preview stream ended or the connection dropped.")
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
            self.frame_ready.emit(qimg)
            self.msleep(delay_ms)

        cap.release()
        self.finished_preview.emit()

    def stop(self):
        self._running = False
