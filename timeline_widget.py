"""A draggable dual-handle timeline for selecting a clip range.

Used to trim a finished (VOD) stream before downloading: shown once a
loaded stream's total duration is known, letting you drag a start and
end handle across the full length instead of typing in timestamps.
Pure Qt painting/mouse-event widget -- no external dependencies beyond
PySide6.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

_HANDLE_RADIUS = 8
_TRACK_HEIGHT = 6
_MIN_SELECTION_SECONDS = 1.0


def format_hhmmss(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    hrs, rem = divmod(seconds, 3600)
    mins, secs = divmod(rem, 60)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"


class ClipTimeline(QWidget):
    """Horizontal timeline with two draggable handles marking a clip's
    start and end. Dragging inside the highlighted range (not on either
    handle) moves both handles together, preserving the selection's
    length, so repositioning a clip doesn't require resizing it first.
    """

    rangeChanged = Signal(float, float)  # (start_seconds, end_seconds)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._duration = 0.0
        self._start = 0.0
        self._end = 0.0
        self._drag_mode: Optional[str] = None  # "start" | "end" | "range" | None
        self._drag_anchor_x = 0
        self._drag_anchor_start = 0.0
        self._drag_anchor_end = 0.0
        self.setMinimumHeight(56)
        self.setMouseTracking(True)
        self.setEnabled(False)

    # ------------------------------------------------------------ public
    def set_duration(self, seconds: float):
        self._duration = max(seconds, 0.0)
        self._start = 0.0
        self._end = self._duration
        self.setEnabled(self._duration > 0)
        self.update()
        self.rangeChanged.emit(self._start, self._end)

    @property
    def start_seconds(self) -> float:
        return self._start

    @property
    def end_seconds(self) -> float:
        return self._end

    @property
    def duration_seconds(self) -> float:
        return self._duration

    # ------------------------------------------------------------- paint
    def _track_rect(self) -> QRect:
        margin = _HANDLE_RADIUS + 2
        y = self.height() // 2 - _TRACK_HEIGHT // 2
        return QRect(margin, y, max(self.width() - 2 * margin, 1), _TRACK_HEIGHT)

    def _seconds_to_x(self, seconds: float) -> int:
        track = self._track_rect()
        if self._duration <= 0:
            return track.left()
        frac = max(0.0, min(1.0, seconds / self._duration))
        return track.left() + int(frac * track.width())

    def _x_to_seconds(self, x: int) -> float:
        track = self._track_rect()
        if track.width() <= 0 or self._duration <= 0:
            return 0.0
        frac = (x - track.left()) / track.width()
        frac = max(0.0, min(1.0, frac))
        return frac * self._duration

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track = self._track_rect()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(210, 210, 210))
        painter.drawRoundedRect(track, 3, 3)

        if self._duration > 0:
            x0 = self._seconds_to_x(self._start)
            x1 = self._seconds_to_x(self._end)
            sel_rect = QRect(x0, track.top(), max(x1 - x0, 1), track.height())
            painter.setBrush(QColor(66, 133, 244))
            painter.drawRoundedRect(sel_rect, 3, 3)

            for x in (x0, x1):
                painter.setBrush(QColor(255, 255, 255))
                painter.setPen(QColor(66, 133, 244))
                painter.drawEllipse(
                    x - _HANDLE_RADIUS, track.center().y() - _HANDLE_RADIUS,
                    _HANDLE_RADIUS * 2, _HANDLE_RADIUS * 2,
                )

        painter.setPen(QColor(90, 90, 90))
        label = (
            f"Clip: {format_hhmmss(self._start)} → {format_hhmmss(self._end)}"
            f"  ({format_hhmmss(self._end - self._start)} long)"
            if self._duration > 0 else "Load a finished stream to enable clip selection."
        )
        painter.drawText(self.rect().adjusted(0, self.height() - 18, 0, 0),
                          Qt.AlignmentFlag.AlignHCenter, label)

    # --------------------------------------------------------------- mouse
    def _handle_at(self, x: int) -> Optional[str]:
        if self._duration <= 0:
            return None
        x0 = self._seconds_to_x(self._start)
        x1 = self._seconds_to_x(self._end)
        if abs(x - x0) <= _HANDLE_RADIUS + 3:
            return "start"
        if abs(x - x1) <= _HANDLE_RADIUS + 3:
            return "end"
        if x0 < x < x1:
            return "range"
        return None

    def mousePressEvent(self, event: QMouseEvent):
        if not self.isEnabled():
            return
        x = int(event.position().x())
        self._drag_mode = self._handle_at(x)
        self._drag_anchor_x = x
        self._drag_anchor_start = self._start
        self._drag_anchor_end = self._end

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.isEnabled() or self._drag_mode is None:
            return
        x = int(event.position().x())
        seconds = self._x_to_seconds(x)

        if self._drag_mode == "start":
            self._start = min(seconds, self._end - _MIN_SELECTION_SECONDS)
            self._start = max(self._start, 0.0)
        elif self._drag_mode == "end":
            self._end = max(seconds, self._start + _MIN_SELECTION_SECONDS)
            self._end = min(self._end, self._duration)
        elif self._drag_mode == "range":
            dx_seconds = self._x_to_seconds(x) - self._x_to_seconds(self._drag_anchor_x)
            width = self._drag_anchor_end - self._drag_anchor_start
            new_start = self._drag_anchor_start + dx_seconds
            new_start = max(0.0, min(new_start, self._duration - width))
            self._start = new_start
            self._end = new_start + width

        self.update()
        self.rangeChanged.emit(self._start, self._end)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_mode = None
