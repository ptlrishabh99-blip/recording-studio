from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QMainWindow, QLabel, QLineEdit, QPushButton, QFileDialog,
    QRadioButton, QButtonGroup, QCheckBox, QSpinBox, QVBoxLayout,
    QHBoxLayout, QGroupBox, QPlainTextEdit, QMessageBox, QFrame,
)

from hls_utils import resolve_stream, StreamProbeError
from recorder import Recorder, RecordingConfig, RecordingError
from preview import PreviewThread


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HLS Capture Studio")
        self.resize(880, 700)

        self.recorder: Recorder | None = None
        self.preview_thread: PreviewThread | None = None
        self.resolved_url: str | None = None
        self.needs_scaling = False

        self.elapsed_seconds = 0
        self.record_timer = QTimer(self)
        self.record_timer.setInterval(1000)
        self.record_timer.timeout.connect(self._tick)

        self.log_poll_timer = QTimer(self)
        self.log_poll_timer.setInterval(300)
        self.log_poll_timer.timeout.connect(self._poll_log)

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # --- Stream source ---
        source_box = QGroupBox("Stream source")
        source_layout = QVBoxLayout(source_box)

        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("HLS (.m3u8) URL:"))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://.../index.m3u8")
        url_row.addWidget(self.url_edit, 1)
        self.load_btn = QPushButton("Load stream")
        self.load_btn.clicked.connect(self.on_load_stream)
        url_row.addWidget(self.load_btn)
        source_layout.addLayout(url_row)

        self.stream_info_label = QLabel("No stream loaded yet.")
        self.stream_info_label.setWordWrap(True)
        source_layout.addWidget(self.stream_info_label)

        root.addWidget(source_box)

        # --- Preview ---
        preview_box = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_box)
        self.preview_label = QLabel("Preview will appear here after you load a stream.")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(320)
        self.preview_label.setFrameShape(QFrame.Shape.Box)
        preview_layout.addWidget(self.preview_label)
        root.addWidget(preview_box, 1)

        # --- Recording options ---
        options_box = QGroupBox("Recording options")
        options_layout = QVBoxLayout(options_box)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self.mode_group = QButtonGroup(self)
        self.radio_full = QRadioButton("Full file")
        self.radio_3min = QRadioButton("3-minute clips")
        self.radio_5min = QRadioButton("5-minute clips")
        self.radio_full.setChecked(True)
        for i, rb in enumerate((self.radio_full, self.radio_3min, self.radio_5min)):
            self.mode_group.addButton(rb, i)
            mode_row.addWidget(rb)
        mode_row.addStretch(1)
        options_layout.addLayout(mode_row)

        timer_row = QHBoxLayout()
        self.timer_checkbox = QCheckBox("Stop recording automatically after")
        self.timer_spin = QSpinBox()
        self.timer_spin.setRange(1, 24 * 60)
        self.timer_spin.setValue(30)
        self.timer_spin.setSuffix(" min")
        self.timer_spin.setEnabled(False)
        self.timer_checkbox.toggled.connect(self.timer_spin.setEnabled)
        timer_row.addWidget(self.timer_checkbox)
        timer_row.addWidget(self.timer_spin)
        timer_row.addStretch(1)
        options_layout.addLayout(timer_row)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("File name:"))
        self.filename_edit = QLineEdit("recording")
        name_row.addWidget(self.filename_edit, 1)
        options_layout.addLayout(name_row)

        loc_row = QHBoxLayout()
        loc_row.addWidget(QLabel("Save to:"))
        self.location_edit = QLineEdit(os.path.expanduser("~"))
        loc_row.addWidget(self.location_edit, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.on_browse)
        loc_row.addWidget(browse_btn)
        options_layout.addLayout(loc_row)

        root.addWidget(options_box)

        # --- Controls ---
        controls_row = QHBoxLayout()
        self.start_btn = QPushButton("Start recording")
        self.start_btn.clicked.connect(self.on_start)
        self.start_btn.setEnabled(False)
        self.stop_btn = QPushButton("Stop recording")
        self.stop_btn.clicked.connect(self.on_stop)
        self.stop_btn.setEnabled(False)
        self.status_label = QLabel("Idle.")
        controls_row.addWidget(self.start_btn)
        controls_row.addWidget(self.stop_btn)
        controls_row.addWidget(self.status_label, 1)
        root.addLayout(controls_row)

        # --- Log ---
        log_box = QGroupBox("Log")
        log_layout = QVBoxLayout(log_box)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        log_layout.addWidget(self.log_view)
        root.addWidget(log_box)

    # ------------------------------------------------------------ actions
    def on_browse(self):
        path = QFileDialog.getExistingDirectory(self, "Choose save location", self.location_edit.text())
        if path:
            self.location_edit.setText(path)

    def on_load_stream(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Enter an HLS (.m3u8) URL first.")
            return

        self.load_btn.setEnabled(False)
        self.stream_info_label.setText("Probing stream...")
        try:
            resolved_url, variant, all_variants = resolve_stream(url, target_height=1080)
        except StreamProbeError as exc:
            QMessageBox.critical(self, "Could not load stream", str(exc))
            self.stream_info_label.setText("Failed to load stream.")
            self.load_btn.setEnabled(True)
            return
        finally:
            self.load_btn.setEnabled(True)

        self.resolved_url = resolved_url
        if variant and variant.height and variant.height != 1080:
            self.needs_scaling = True
            info = (
                f"Closest available rendition: {variant.label()}.\n"
                f"Source has no native 1080p rendition, so recording will "
                f"scale to 1080p and re-encode to H.264/AAC MP4 while "
                f"keeping the source's variable frame timing."
            )
        elif variant:
            self.needs_scaling = False
            info = (
                f"Selected 1080p rendition: {variant.label()}. Recording "
                f"will re-encode to a standard H.264/AAC MP4 at the "
                f"source's native 1080p resolution."
            )
        else:
            self.needs_scaling = False
            info = (
                "Single-rendition stream (no adaptive variants "
                "advertised). Recording will re-encode to a standard "
                "H.264/AAC MP4 at the source's native resolution and "
                "frame rate."
            )

        if all_variants:
            info += "\nAll available renditions: " + "; ".join(v.label() for v in all_variants)

        self.stream_info_label.setText(info)
        self.start_btn.setEnabled(True)
        self._start_preview(resolved_url)
        self._log(f"Loaded stream: {resolved_url}")

    def _start_preview(self, url: str):
        self._stop_preview()
        self.preview_thread = PreviewThread(url)
        self.preview_thread.frame_ready.connect(self._on_preview_frame)
        self.preview_thread.error.connect(lambda msg: self._log(f"[preview] {msg}"))
        self.preview_thread.start()

    def _stop_preview(self):
        if self.preview_thread:
            self.preview_thread.stop()
            self.preview_thread.wait(2000)
            self.preview_thread = None

    def _on_preview_frame(self, qimg):
        pixmap = QPixmap.fromImage(qimg).scaled(
            self.preview_label.width(), self.preview_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(pixmap)

    def on_start(self):
        if not self.resolved_url:
            return

        mode = "full"
        segment_seconds = 180
        if self.radio_3min.isChecked():
            mode, segment_seconds = "segment", 180
        elif self.radio_5min.isChecked():
            mode, segment_seconds = "segment", 300

        duration_seconds = None
        if self.timer_checkbox.isChecked():
            duration_seconds = self.timer_spin.value() * 60

        config = RecordingConfig(
            stream_url=self.resolved_url,
            output_dir=self.location_edit.text().strip() or os.path.expanduser("~"),
            base_filename=self.filename_edit.text().strip() or "recording",
            mode=mode,
            segment_seconds=segment_seconds,
            duration_seconds=duration_seconds,
            needs_scaling=self.needs_scaling,
        )

        self.recorder = Recorder(config)
        try:
            output_path = self.recorder.start()
        except RecordingError as exc:
            QMessageBox.critical(self, "Could not start recording", str(exc))
            self.recorder = None
            return

        self._log(f"Recording started -> {output_path}")
        self.elapsed_seconds = 0
        self.record_timer.start()
        self.log_poll_timer.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.load_btn.setEnabled(False)
        self._update_status()

    def on_stop(self):
        self._finish_recording(user_initiated=True)

    def _finish_recording(self, user_initiated: bool):
        if self.recorder:
            self.recorder.stop()
            self._log("Recording stopped." if user_initiated else "Recording timer elapsed; stopping.")
        self.record_timer.stop()
        self.log_poll_timer.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.load_btn.setEnabled(True)
        self.status_label.setText("Idle.")

    def _tick(self):
        self.elapsed_seconds += 1
        cfg = self.recorder.config if self.recorder else None
        if cfg and cfg.duration_seconds and self.elapsed_seconds >= cfg.duration_seconds:
            self._finish_recording(user_initiated=False)
            return
        if self.recorder and not self.recorder.is_running():
            self._log("ffmpeg process ended.")
            self._finish_recording(user_initiated=False)
            return
        self._update_status()

    def _update_status(self):
        mins, secs = divmod(self.elapsed_seconds, 60)
        hrs, mins = divmod(mins, 60)
        text = f"Recording... {hrs:02d}:{mins:02d}:{secs:02d}"
        if self.recorder and self.recorder.config.duration_seconds:
            total = self.recorder.config.duration_seconds
            remaining = max(total - self.elapsed_seconds, 0)
            rmins, rsecs = divmod(remaining, 60)
            rhrs, rmins = divmod(rmins, 60)
            text += f"  (auto-stop in {rhrs:02d}:{rmins:02d}:{rsecs:02d})"
        self.status_label.setText(text)

    def _poll_log(self):
        if not self.recorder:
            return
        line = self.recorder.readline()
        if line:
            self._log(line)

    def _log(self, text: str):
        self.log_view.appendPlainText(text)

    def closeEvent(self, event):
        self._stop_preview()
        if self.recorder and self.recorder.is_running():
            self.recorder.stop()
        super().closeEvent(event)
