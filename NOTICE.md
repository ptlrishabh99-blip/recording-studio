# Third-party notice: bundled ffmpeg

The macOS and Windows installers built from `.github/workflows/release.yml`
bundle a real `ffmpeg` binary (fetched at build time via Homebrew on macOS
and Chocolatey on Windows) so end users don't need to install it
separately.

ffmpeg is licensed under the LGPL, but the standard Homebrew and
Chocolatey builds are typically compiled with GPL-licensed components
(e.g. `libx264` for H.264 encoding) enabled, which makes the resulting
binary GPL-licensed as a whole. Redistributing it — which this installer
does — carries GPL obligations, most importantly:

- Include this notice and a copy of the GPL with anything you distribute.
- Make the corresponding ffmpeg source available to anyone you distribute
  the binary to (a link to https://ffmpeg.org/download.html plus the
  exact version/build flags in use is generally sufficient).

If you'd rather avoid GPL obligations entirely, swap in an LGPL-only
ffmpeg build (no libx264/libx265/etc.) before packaging — see
https://ffmpeg.org/legal.html for what that means in practice, and
https://www.gyan.dev/ffmpeg/builds/ (Windows) for prebuilt LGPL-only
Windows binaries. On macOS, `brew install ffmpeg --without-x264` (or a
custom formula) gets you the same for the Homebrew build.

This project itself (the HLS Capture Studio source code) is provided
as-is with no bundled license file; add one if you plan to distribute it
further.
