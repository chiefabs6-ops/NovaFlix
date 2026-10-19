import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tests", "fakes"))
sys.path.insert(0, os.path.join(ROOT, "plugin.video.aniverse"))
sys.path.insert(0, ROOT)

import xbmc  # noqa: E402  (fake)
import xbmcaddon  # noqa: E402
import xbmcgui  # noqa: E402
import xbmcplugin  # noqa: E402
import xbmcvfs  # noqa: E402


@pytest.fixture(autouse=True)
def reset_fakes():
    for module in (xbmc, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs):
        module.reset()
    yield


@pytest.fixture(autouse=True)
def kodi_profile(reset_fakes, tmp_path):
    """special://profile/ and special://xbmc/ map to a per-test temp dir."""
    profile = tmp_path / "profile"
    profile.mkdir()
    xbmcvfs.special_roots["special://profile/"] = str(profile)
    xbmcvfs.special_roots["special://xbmc/"] = str(tmp_path / "xbmc")
    return profile


@pytest.fixture(autouse=True)
def isolate_module_state(monkeypatch):
    """Reset process-wide state kept by add-on modules between tests."""
    from resources.lib import redact
    from resources.lib.kodi import log
    from resources.lib.net import http

    redact.clear_secrets()
    log.reset_debug_flag()
    http.reset()
    http.set_transport(_no_network)
    monkeypatch.setattr(http, "_sleep", lambda seconds: None)  # no real backoff waits
    yield
    redact.clear_secrets()
    log.reset_debug_flag()
    http.reset()


def _no_network(method, url, headers, body, timeout, context):
    raise AssertionError(f"test tried to reach the network: {method} {url}")
