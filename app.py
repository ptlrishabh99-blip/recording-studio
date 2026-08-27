"""Entry point: HLS Capture Studio.

A cross-platform (macOS / Windows) desktop app for recording HLS (.m3u8)
streams you have the rights to capture — records at 1080p (or the closest
available rendition) without forcing a fixed frame rate, supports full-file
or 3/5-minute segmented recording, an auto-stop timer, a live preview, and
lets you choose the output file name and save location.

Run with:  python app.py
Requires ffmpeg on PATH (see README.md).
"""
import sys

from PySide6.QtWidgets import QApplication

from main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
