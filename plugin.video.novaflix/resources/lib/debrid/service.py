"""NovaFlix's playback service: TorBox only.

The TorBox client has the debrid interface (torrents, torrent_info,
add_magnet, select_files, unrestrict, delete_torrent) that the resolver, source
list and cleanup use.
"""

from resources.lib.kodi import ui

TORBOX = "torbox"


def label():
    return "TorBox"


def client(directory=None):
    """The TorBox client, or None when no API key is set."""
    from resources.lib.debrid.torbox import TorBox
    key = ui.setting("torbox_api_key")
    return TorBox(key) if key else None
