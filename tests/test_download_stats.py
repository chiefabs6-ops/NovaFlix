# tests/test_download_stats.py
"""Cinematic UI: the numbers under the download bar."""

from resources.lib.views import play


def test_download_stats_with_everything_known():
    stats = play.download_stats(42, 18.4e6, 312, 58.3e9)
    assert stats["speed"] == "18.4 MB/s" and stats["seeders"] == "312"
    assert stats["size"] == "24.49 GB of 58.30 GB"
    assert stats["left"] == "about 31 min left"


def test_download_left_needs_speed_and_size():
    assert "left" not in play.download_stats(42, 0, 5, 58.3e9)
    assert "left" not in play.download_stats(42, 18.4e6, 5, None)
    assert play.download_stats(42, None, None, None) == {}
    assert play.download_stats(99.99, 50e6, None, 1e9)["left"] == "less than a minute left"
