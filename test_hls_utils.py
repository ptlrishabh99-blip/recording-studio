"""Quick sanity checks for the master-playlist parsing/selection logic.
Run with: python -m pytest test_hls_utils.py -q  (or just: python test_hls_utils.py)
"""
from hls_utils import parse_master_playlist, select_best_variant

SAMPLE_MASTER = """#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360,FRAME-RATE=25.0
360p/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1280x720,FRAME-RATE=25.0
720p/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080,FRAME-RATE=25.0
1080p/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=8000000,RESOLUTION=1920x1080,FRAME-RATE=50.0
1080p60/index.m3u8
"""

BASE_URL = "https://example.invalid/mumbai/master.m3u8"


def test_parse_variants_count_and_urls():
    variants = parse_master_playlist(SAMPLE_MASTER, BASE_URL)
    assert len(variants) == 4
    assert variants[0].resolution == (640, 360)
    assert variants[-1].url == "https://example.invalid/mumbai/1080p60/index.m3u8"


def test_select_exact_1080p_prefers_higher_bandwidth():
    variants = parse_master_playlist(SAMPLE_MASTER, BASE_URL)
    best = select_best_variant(variants, target_height=1080)
    assert best.resolution == (1920, 1080)
    assert best.bandwidth == 8000000  # higher-bitrate 1080p variant wins
    assert best.frame_rate == 50.0    # frame rate is preserved, not forced


def test_select_falls_back_to_highest_below_target():
    no_1080_master = SAMPLE_MASTER.replace(
        "#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080,FRAME-RATE=25.0\n1080p/index.m3u8\n",
        "",
    ).replace(
        "#EXT-X-STREAM-INF:BANDWIDTH=8000000,RESOLUTION=1920x1080,FRAME-RATE=50.0\n1080p60/index.m3u8\n",
        "",
    )
    variants = parse_master_playlist(no_1080_master, BASE_URL)
    best = select_best_variant(variants, target_height=1080)
    assert best.resolution == (1280, 720)


def test_media_playlist_has_no_variants():
    media_playlist = "#EXTM3U\n#EXTINF:6.0,\nseg1.ts\n#EXTINF:6.0,\nseg2.ts\n"
    variants = parse_master_playlist(media_playlist, BASE_URL)
    assert variants == []


if __name__ == "__main__":
    import sys
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL: {t.__name__}: {e}")
    sys.exit(1 if failures else 0)
