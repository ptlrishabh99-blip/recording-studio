# HLS Capture Studio

A small cross-platform (macOS / Windows) desktop app for recording HLS
(`.m3u8`) streams **you have the rights to capture** — your own OBS/live
setup, a licensed feed, a personal IP camera, and similar. It targets
1080p (or the closest available rendition) without forcing a fixed frame
rate, and supports:

- Full-file recording, or fixed-length clips (3 min / 5 min)
- Also works as a download-and-convert tool for a stream that's already
  over: point it at a finished (VOD) `.m3u8` and it races through the
  existing segments instead of waiting in real time
- For finished (VOD) streams, a draggable clip timeline lets you trim to
  just a range instead of downloading the whole thing — ffmpeg seeks
  straight to that range rather than fetching the full stream first
- Always converts to a standard, universally-playable H.264/AAC MP4,
  regardless of the source's original codec
- An optional auto-stop recording timer
- A live preview pane so you can confirm you're pointed at the right feed
- Custom output file name and save-location picker
- Runs unmodified on macOS and Windows (PySide6 + ffmpeg)

**Only use this to record streams you're authorized to capture.** It does
not target, bypass protections for, or hardcode any particular streaming
service.

> **Just want to use the app, not develop it?** Grab the one-click
> installer for your OS instead of following the steps below — see
> [One-click installers](#one-click-installers-recommended-for-non-developers).
> It bundles Python and ffmpeg for you, so there's nothing else to
> install.

## How it works

- `hls_utils.py` fetches the `.m3u8` playlist. If it's a master playlist
  (adaptive bitrate), it parses the `#EXT-X-STREAM-INF` renditions and
  picks the one closest to 1080p — exact match preferred, otherwise the
  highest rendition at or below 1080p. It also probes the chosen media
  playlist for `#EXT-X-ENDLIST` (a finished/VOD stream) and, when present,
  sums every `#EXTINF` entry to get the stream's total duration — that's
  what drives the clip timeline.
- `timeline_widget.py` is a small self-contained Qt widget: a horizontal
  bar with two draggable handles marking a clip's start and end, used
  only once a loaded stream turns out to be a finished VOD with a known
  duration. Dragging inside the selected range (not on a handle) moves
  both handles together instead of resizing.
- `recorder.py` builds and runs the ffmpeg command. Every recording is
  re-encoded with `libx264`/`aac` and `-vsync vfr` (so the output still
  follows the source's natural, variable frame timing instead of being
  forced to a constant fps) into a standard MP4 — never a raw `-c copy`
  remux of whatever codec the source happens to use. A scale filter is
  added only when the chosen rendition isn't already 1080p; otherwise it
  encodes at that native resolution.
- `preview.py` runs a separate low-fps OpenCV read of the stream just for
  the on-screen preview, so it doesn't interfere with the recording
  process.
- `main_window.py` / `app.py` wire it all into a PySide6 GUI.

## Setup (running from source, for development)

### 1. Install ffmpeg

- **macOS:** `brew install ffmpeg`
- **Windows:** `choco install ffmpeg` (or download a build from
  https://ffmpeg.org/download.html and add its `bin` folder to your PATH)

Verify with `ffmpeg -version` in a terminal.

### 2. Install Python dependencies

Requires Python 3.10+.

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run it

```bash
python app.py
```

1. Paste the `.m3u8` URL and click **Load stream** — it'll report the
   detected rendition(s) and start the preview.
2. Choose **Full file**, **3-minute clips**, or **5-minute clips**.
3. Optionally check the auto-stop timer and set a duration.
4. Set the file name and save location.
5. Click **Start recording** / **Stop recording**.

Segmented recordings are written as `<name>_<timestamp>_001.mp4`,
`_002.mp4`, etc. Full recordings are written as `<name>_<timestamp>.mp4`.

## Running tests

```bash
python -m pytest test_hls_utils.py -q
# or, without pytest installed:
python test_hls_utils.py
```

## One-click installers (recommended for non-developers)

This repo can build a real macOS `.dmg` and Windows `Setup.exe` that each
bundle Python *and* ffmpeg inside them — download, double-click, done,
nothing else to install. A GitHub Actions workflow builds both
automatically (a Mac app has to be built on a Mac, a Windows exe on
Windows — that's a platform constraint, which is why this uses GitHub's
own Mac/Windows runners rather than trying to cross-compile).

See [`BUILD.md`](BUILD.md) for the full one-time setup and how to cut a
release; short version, from a repo you've pushed to GitHub:

```bash
git tag v1.0.0 && git push origin v1.0.0
```

...then grab `HLS-Capture-Studio-mac.dmg` and
`HLS-Capture-Studio-Setup-*.exe` from the repo's Releases page a few
minutes later.

## Packaging manually (for developers)

Use [PyInstaller](https://pyinstaller.org/) directly for a one-off local
build. `packaging/hls_recorder.spec` also bundles a `vendor/ffmpeg(.exe)`
binary into the build if you drop one there first — see `BUILD.md`'s
"Building locally instead" section for the full per-OS steps.

```bash
pip install pyinstaller
pyinstaller --clean --noconfirm packaging/hls_recorder.spec
```

**macOS** (run on a Mac) produces `dist/HLS Capture Studio.app`.
**Windows** (run on Windows) produces
`dist/HLS Capture Studio/HLS Capture Studio.exe`.

PyInstaller builds are platform-specific — build the macOS bundle on a Mac
and the Windows build on Windows (or use the CI workflow above, which
does exactly that for you).

## Known limitations / things to extend

- The preview pulls its own connection to the stream (via OpenCV) rather
  than tapping the ffmpeg recording process, so on a bandwidth-constrained
  connection you may want to disable it while recording (stop the app,
  or add a "pause preview during recording" toggle — the `PreviewThread`
  in `preview.py` already exposes `.stop()`).
- There's no retry/reconnect logic if the source stream drops mid-recording
  — ffmpeg will exit and the app will report "ffmpeg process ended." Add
  reconnect logic in `main_window.py`'s `_tick`/`_finish_recording` if you
  need that for long unattended recordings.
- Because every recording is re-encoded rather than stream-copied, it's
  CPU-bound: a long finished (VOD) stream downloads faster than real
  time, but not instantly, and a slower machine may fall behind a fast
  live stream at very high resolutions. `-preset veryfast` is chosen for
  a reasonable speed/quality balance; trade some encode speed for a
  smaller file by changing the `-preset`/`-crf` values in
  `recorder.py`'s `build_command`.
- A finished (VOD) stream now gets its own clip timeline (see above), but
  the elapsed-time display during the download still counts up like a
  stopwatch rather than showing real download progress (e.g. "record
  350/3600 of the source's segments") — the live preview also still
  tries to start for a VOD the same as for a live stream, which is
  pointless once the stream has ended. A progress bar driven by ffmpeg's
  own progress output (`-progress pipe:1`, parsed in `recorder.py`'s
  `readline`) would be a good next step.
