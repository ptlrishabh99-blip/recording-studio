"""ffmpeg-backed capture engine.

Handles four concerns:
  * Full-file recording (one continuous .mp4)
  * Segmented recording (fixed-length clips, e.g. 3 or 5 minutes each)
  * An optional overall duration limit ("recording timer")
  * Clipping a specific start/end range out of a finished (VOD) source,
    driven by the timeline selector in the UI (`start_seconds` +
    `duration_seconds` together)

Every recording is re-encoded to a standard H.264/AAC MP4 with libx264 and
`-vsync vfr`, so the output plays back reliably anywhere regardless of the
source's original codec, and still follows the source's natural, variable
frame timing instead of being forced to a constant fps. If the chosen
rendition isn't already 1080p, a scale filter is added to bring it there;
if it's already 1080p, the encode happens at that native resolution with
no scaling step.

This also means the same "Start recording" flow doubles as a "download
and convert" tool for finished (VOD) streams: point it at an `.m3u8` whose
playlist is already complete (ends with `#EXT-X-ENDLIST`) and ffmpeg races
through the existing segments as fast as your connection and CPU allow
instead of waiting in real time.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


class RecordingError(Exception):
    pass


def _bundled_ffmpeg_path() -> Optional[str]:
    """Look for an ffmpeg binary shipped alongside the packaged app.

    The installer builds (see packaging/) bundle a real ffmpeg binary next
    to the app executable, so end users never have to install ffmpeg
    themselves. This checks every place PyInstaller might have put it,
    for both the --onefile and --onedir/app-bundle layouts, before ever
    falling back to the system PATH.
    """
    exe_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    candidates = []

    if getattr(sys, "frozen", False):
        # --onefile: PyInstaller unpacks bundled binaries into a temp dir
        # exposed as sys._MEIPASS for the lifetime of the process.
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(os.path.join(meipass, exe_name))

        exe_dir = os.path.dirname(sys.executable)
        # --onedir (Windows build / Inno Setup install folder): ffmpeg.exe
        # sits right next to the app's own .exe.
        candidates.append(os.path.join(exe_dir, exe_name))
        # macOS .app bundle: sys.executable is Contents/MacOS/<app>, and
        # --add-binary drops ffmpeg into that same MacOS/ directory.
        candidates.append(os.path.join(exe_dir, "..", "Resources", exe_name))
    else:
        # Running from source (e.g. during development) — allow an
        # optional local vendor/ffmpeg(.exe) so `python app.py` can also
        # pick up a pre-fetched binary without touching PATH.
        here = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(here, "vendor", exe_name))

    for path in candidates:
        path = os.path.normpath(path)
        if os.path.isfile(path):
            return path
    return None


def find_ffmpeg() -> str:
    bundled = _bundled_ffmpeg_path()
    if bundled:
        return bundled
    path = shutil.which("ffmpeg")
    if not path:
        raise RecordingError(
            "ffmpeg was not found on your PATH.\n\n"
            "macOS:   brew install ffmpeg\n"
            "Windows: choco install ffmpeg   (or download a build from "
            "https://ffmpeg.org/download.html and add it to PATH)"
        )
    return path


@dataclass
class RecordingConfig:
    stream_url: str
    output_dir: str
    base_filename: str
    mode: str = "full"          # "full" | "segment"
    segment_seconds: int = 180  # 180 (3 min) or 300 (5 min) when mode == "segment"
    duration_seconds: Optional[float] = None  # overall recording timer, or clip length when clipping
    start_seconds: Optional[float] = None  # clip start offset into a VOD source, if clipping
    needs_scaling: bool = False  # add a scale-to-1080p filter (recording always re-encodes regardless)


class Recorder:
    def __init__(self, config: RecordingConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.output_path: Optional[str] = None
        self._stop_lock = threading.Lock()
        self._stopped = False

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _build_output_path(self) -> str:
        cfg = self.config
        os.makedirs(cfg.output_dir, exist_ok=True)
        safe_name = cfg.base_filename.strip() or "recording"
        stamped = f"{safe_name}_{self._timestamp()}"
        if cfg.mode == "segment":
            return os.path.join(cfg.output_dir, stamped + "_%03d.mp4")
        return os.path.join(cfg.output_dir, stamped + ".mp4")

    def build_command(self):
        cfg = self.config
        ffmpeg = find_ffmpeg()
        output_path = self._build_output_path()

        cmd = [ffmpeg, "-y"]
        if cfg.start_seconds:
            # An input-side -ss (before -i) lets ffmpeg's HLS demuxer skip
            # straight to the segment containing this timestamp instead of
            # fetching everything from the start of the playlist -- the
            # key to clipping a range out of a VOD without downloading the
            # whole thing first.
            cmd += ["-ss", f"{cfg.start_seconds:.3f}"]
        cmd += ["-i", cfg.stream_url]

        # Always re-encode to a standard, universally-playable H.264/AAC
        # MP4 -- never a raw `-c copy` remux of whatever codec the source
        # happens to use. Only add the scale filter when the source isn't
        # already at 1080p; otherwise this encodes at its native size.
        if cfg.needs_scaling:
            cmd += ["-vf", "scale=-2:1080"]
        cmd += [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-vsync", "vfr",
            "-c:a", "aac", "-b:a", "192k",
        ]

        if cfg.duration_seconds:
            cmd += ["-t", f"{cfg.duration_seconds:.3f}"]

        if cfg.mode == "segment":
            cmd += [
                "-f", "segment",
                "-segment_time", str(cfg.segment_seconds),
                "-reset_timestamps", "1",
            ]

        cmd += [output_path]
        return cmd, output_path

    def start(self) -> str:
        cmd, output_path = self.build_command()
        self.output_path = output_path
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self._stopped = False
        return output_path

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def stop(self, timeout: float = 10.0) -> None:
        """Ask ffmpeg to shut down cleanly (sending 'q', which lets it
        flush and finalize the mp4 container properly) before resorting
        to terminate/kill."""
        with self._stop_lock:
            if self._stopped or self.process is None:
                return
            self._stopped = True
            try:
                if self.process.stdin:
                    self.process.stdin.write("q")
                    self.process.stdin.flush()
            except Exception:
                pass
            try:
                self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()

    def readline(self) -> Optional[str]:
        """Non-blocking-ish single line read from ffmpeg's combined
        stdout/stderr, for surfacing progress/log info in the UI."""
        if not self.process or not self.process.stdout:
            return None
        line = self.process.stdout.readline()
        return line.rstrip("\n") if line else None
