"""Utilities for inspecting an HLS (.m3u8) stream and picking the rendition
closest to a target resolution (default: 1080p) without forcing a fixed
frame rate.

Works with any HLS source you have the rights to record — your own OBS/
streaming setup, a licensed feed, a personal camera, etc. It does not target
or hardcode any particular platform.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib.parse import urljoin

import requests


@dataclass
class Variant:
    url: str
    resolution: Optional[Tuple[int, int]] = None  # (width, height)
    bandwidth: Optional[int] = None
    frame_rate: Optional[float] = None

    @property
    def height(self) -> Optional[int]:
        return self.resolution[1] if self.resolution else None

    def label(self) -> str:
        res = f"{self.resolution[0]}x{self.resolution[1]}" if self.resolution else "unknown res"
        fps = f"{self.frame_rate:g}fps" if self.frame_rate else "fps n/a"
        bw = f"{self.bandwidth // 1000}kbps" if self.bandwidth else ""
        return " / ".join(p for p in (res, fps, bw) if p)


class StreamProbeError(Exception):
    pass


def fetch_playlist(url: str, timeout: float = 10.0) -> str:
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise StreamProbeError(f"Could not fetch playlist: {exc}") from exc
    return resp.text


def parse_master_playlist(text: str, base_url: str) -> List[Variant]:
    """Parse a HLS *master* playlist. Returns [] if `text` looks like a
    plain media playlist (no #EXT-X-STREAM-INF entries) instead."""
    variants: List[Variant] = []
    lines = text.splitlines()
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line.startswith("#EXT-X-STREAM-INF"):
            continue
        attrs = line.split(":", 1)[1] if ":" in line else ""

        resolution = None
        m = re.search(r"RESOLUTION=(\d+)x(\d+)", attrs)
        if m:
            resolution = (int(m.group(1)), int(m.group(2)))

        bandwidth = None
        m = re.search(r"BANDWIDTH=(\d+)", attrs)
        if m:
            bandwidth = int(m.group(1))

        frame_rate = None
        m = re.search(r"FRAME-RATE=([\d.]+)", attrs)
        if m:
            frame_rate = float(m.group(1))

        # The variant URI is the next non-blank, non-comment line.
        for j in range(i + 1, len(lines)):
            nxt = lines[j].strip()
            if nxt and not nxt.startswith("#"):
                variants.append(Variant(urljoin(base_url, nxt), resolution, bandwidth, frame_rate))
                break

    return variants


def select_best_variant(variants: List[Variant], target_height: int = 1080) -> Optional[Variant]:
    """Pick the rendition matching target_height exactly when available;
    otherwise the highest one at or below it; otherwise the lowest one
    above it; otherwise whatever is there. Never forces a frame rate —
    each Variant simply carries whatever FRAME-RATE (if any) the source
    playlist advertised."""
    if not variants:
        return None

    with_res = [v for v in variants if v.resolution]
    if not with_res:
        return variants[0]

    exact = [v for v in with_res if v.height == target_height]
    if exact:
        return max(exact, key=lambda v: v.bandwidth or 0)

    below = [v for v in with_res if v.height < target_height]
    if below:
        return max(below, key=lambda v: v.height)

    above = [v for v in with_res if v.height > target_height]
    if above:
        return min(above, key=lambda v: v.height)

    return with_res[0]


def resolve_stream(url: str, target_height: int = 1080):
    """Given any HLS URL (master or media playlist), return
    (chosen_media_url, variant_or_None, all_variants).

    If `url` is already a media playlist (no variants to choose from),
    variant is None and all_variants is empty — the URL is used as-is.
    """
    text = fetch_playlist(url)
    if "#EXT-X-STREAM-INF" in text:
        variants = parse_master_playlist(text, url)
        best = select_best_variant(variants, target_height)
        if best is None:
            raise StreamProbeError("Master playlist had no usable renditions.")
        return best.url, best, variants
    return url, None, []
