# Building the one-click Mac + Windows installers

This turns HLS Capture Studio into two real installers — a macOS `.dmg`
and a Windows `Setup.exe` — that each bundle Python and ffmpeg inside
them. An end user just downloads the file for their OS, runs it, and the
app launches with nothing else to install.

Building a macOS app has to happen on a Mac, and building a Windows exe
has to happen on Windows — that's an OS constraint, not a tooling choice.
The `.github/workflows/release.yml` workflow in this repo does both for
you automatically on GitHub's own macOS and Windows runners, so you don't
need either machine yourself.

## One-time setup

1. Push this project to a GitHub repository (public or private both
   work — private repos on a free account still get free Actions
   minutes for this).

   ```bash
   git init
   git add .
   git commit -m "HLS Capture Studio"
   git branch -M main
   git remote add origin https://github.com/<you>/<repo>.git
   git push -u origin main
   ```

2. That's it — no secrets or accounts to configure. The workflow only
   uses tools already available on GitHub's hosted runners (Homebrew,
   Chocolatey, PyInstaller, Inno Setup).

## Building a release

Tag a version and push the tag — this is what triggers the build *and*
publishes a GitHub Release with both installers attached:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Then:

1. Go to your repo's **Actions** tab and watch the "Build installers"
   workflow run (takes roughly 5–10 minutes — most of it is installing
   ffmpeg and PyInstaller on each runner).
2. When it finishes, go to the **Releases** page of your repo. You'll
   find:
   - `HLS-Capture-Studio-mac.dmg`
   - `HLS-Capture-Studio-Setup-1.0.0.exe`

Anyone you send those two files to can now just double-click and go —
no Python, no ffmpeg, no terminal.

### Building without tagging a release

You can also trigger the same build from **Actions → Build installers →
Run workflow** at any time (no tag needed). That run's installers show up
under the workflow run's **Artifacts** section instead of a Release —
handy for testing a change before you cut a real version.

## What end users see

- **macOS:** open the `.dmg`, drag "HLS Capture Studio" into
  `Applications`, launch it. Since the app isn't code-signed/notarized
  (that requires a paid Apple Developer account), the first launch will
  be blocked by Gatekeeper — right-click the app → **Open** → **Open**
  gets past that one-time warning.
- **Windows:** run `HLS-Capture-Studio-Setup-*.exe`. It installs
  per-user (no admin prompt), adds a Start Menu entry and optional
  desktop icon, and offers to launch the app when done. Since the
  installer isn't code-signed either, Windows SmartScreen will show an
  "unrecognized app" warning the first time — **More info** → **Run
  anyway** gets past it.

Neither warning means anything is broken; it's just what unsigned
installers look like. If you want those warnings gone entirely, you'd
need an Apple Developer ID ($99/yr, for notarization) and a Windows code
signing certificate — both optional add-ons to this same pipeline, not
required for it to work.

## Building locally instead (optional)

If you do have both a Mac and a Windows machine handy and would rather
not use GitHub Actions:

**macOS**

```bash
brew install ffmpeg
mkdir -p vendor && cp "$(brew --prefix ffmpeg)/bin/ffmpeg" vendor/ffmpeg
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt pyinstaller
pyinstaller --clean --noconfirm packaging/hls_recorder.spec
# -> dist/HLS Capture Studio.app
```

**Windows** (PowerShell)

```powershell
choco install ffmpeg -y
mkdir vendor
Copy-Item (Get-Command ffmpeg).Source vendor\ffmpeg.exe
python -m venv venv; venv\Scripts\activate
pip install -r requirements.txt pyinstaller
pyinstaller --clean --noconfirm packaging/hls_recorder.spec
choco install innosetup -y
iscc packaging\windows\setup.iss
# -> packaging\windows\Output\HLS-Capture-Studio-Setup-1.0.0.exe
```

## Licensing note

The bundled ffmpeg binary carries its own license obligations once you
redistribute it — see [`NOTICE.md`](NOTICE.md) before shipping this
to anyone outside your own machine.
