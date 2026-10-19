import xbmc
import xbmcaddon

from resources.lib import redact
from resources.lib.kodi import log


def messages():
    return [msg for _, msg in xbmc.log_records]


def test_debug_hidden_when_setting_off():
    xbmcaddon.settings["debug_logging"] = False
    log.debug("detail")
    assert messages() == []


def test_debug_written_at_info_level_when_setting_on():
    # Kodi only shows LOGDEBUG when Kodi's own debug mode is on, so our
    # toggle writes debug lines at LOGINFO.
    xbmcaddon.settings["debug_logging"] = True
    log.debug("detail")
    assert xbmc.log_records == [(xbmc.LOGINFO, "[plugin.video.aniverse] [debug] detail")]


def test_all_levels_are_redacted():
    redact.register_secret("SENTINELTOKEN0123456789")
    xbmcaddon.settings["debug_logging"] = True
    for write in (log.debug, log.info, log.warning, log.error):
        write("value SENTINELTOKEN0123456789 at https://x.example/a?code=1")
    for msg in messages():
        assert "SENTINELTOKEN0123456789" not in msg
        assert "code=1" not in msg


def test_exception_logs_redacted_traceback():
    redact.register_secret("SENTINELTOKEN0123456789")
    try:
        raise RuntimeError("bad token SENTINELTOKEN0123456789")
    except RuntimeError:
        log.exception("refresh failed")
    joined = "\n".join(messages())
    assert "refresh failed" in joined
    assert "RuntimeError" in joined
    assert "SENTINELTOKEN0123456789" not in joined


def test_debug_setting_reread_on_each_call():
    # reuselanguageinvoker keeps module state between calls (M9).
    import xbmcaddon
    from resources.lib import router
    xbmcaddon.settings["debug_logging"] = False
    router.setup()
    log.debug("hidden")
    xbmcaddon.settings["debug_logging"] = True
    router.setup()
    log.debug("shown")
    messages = [m for _, m in xbmc.log_records]
    assert not any("hidden" in m for m in messages) and any("shown" in m for m in messages)
