# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for HLS Capture Studio.

Builds a self-contained app (bundled Python interpreter + all pip
dependencies + a real ffmpeg binary) so end users never install Python or
ffmpeg themselves. Produces:

  * macOS:   dist/HLS Capture Studio.app
  * Windows: dist/HLS Capture Studio/HLS Capture Studio.exe  (+ support files)

Run via:  pyinstaller --clean --noconfirm packaging/hls_recorder.spec
(see .github/workflows/release.yml for the full, automated build).

Before running, drop a real ffmpeg binary at:
  vendor/ffmpeg        (macOS/Linux)
  vendor\\ffmpeg.exe    (Windows)
It gets bundled next to the app so it ships inside the installer. Building
without it still works (handy for a quick local test) but the resulting
app will fall back to a system-installed ffmpeg on PATH.
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(SPEC)), ".."))
VENDOR = os.path.join(ROOT, "vendor")
APP_NAME = "HLS Capture Studio"

ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
ffmpeg_path = os.path.join(VENDOR, ffmpeg_name)

binaries = []
if os.path.isfile(ffmpeg_path):
    binaries.append((ffmpeg_path, "."))
else:
    print(f"[hls_recorder.spec] WARNING: no bundled ffmpeg found at {ffmpeg_path} "
          f"-- building without one. The app will require ffmpeg on PATH at runtime.")

icon_ico = os.path.join(ROOT, "packaging", "icon.ico")
icon_icns = os.path.join(ROOT, "packaging", "icon.icns")

a = Analysis(
    [os.path.join(ROOT, "app.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_ico if sys.platform == "win32" and os.path.isfile(icon_ico) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=icon_icns if os.path.isfile(icon_icns) else None,
        bundle_identifier="com.hlscapturestudio.app",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": os.environ.get("APP_VERSION", "1.0.0"),
            "NSCameraUsageDescription": "Not used.",
            "NSMicrophoneUsageDescription": "Not used.",
        },
    )
