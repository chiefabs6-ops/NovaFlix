import xbmc

from resources.lib import service_main


def test_service_runs_until_abort_and_logs_lifecycle():
    xbmc.Monitor.waits_before_abort = 2
    service_main.run()
    messages = [msg for _, msg in xbmc.log_records]
    assert any("service started" in m for m in messages)
    assert any("service stopped" in m for m in messages)


def test_log_lines_are_prefixed_with_addon_id():
    xbmc.Monitor.waits_before_abort = 0
    service_main.run()
    assert all(msg.startswith("[plugin.video.novaflix]") for _, msg in xbmc.log_records)
