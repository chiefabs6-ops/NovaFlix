"""Which playback service NovaFlix uses (DEC-054: TorBox replaces Real-Debrid for now).

Both clients share one interface (torrents, torrent_info, add_magnet,
select_files, unrestrict, delete_torrent), so the resolver, source list and
cleanup do not care which one is active.
"""

from resources.lib.kodi import paths, ui

TORBOX, REAL_DEBRID = "torbox", "realdebrid"


def active():
    return REAL_DEBRID if ui.addon().getSettingInt("playback_service") == 1 else TORBOX


def label():
    return "TorBox" if active() == TORBOX else "Real-Debrid"


def client(directory=None):
    """The active service's client, or None when it isn't set up."""
    if active() == TORBOX:
        from resources.lib.debrid.torbox import TorBox
        key = ui.setting("torbox_api_key")
        return TorBox(key) if key else None
    from resources.lib.debrid import auth
    from resources.lib.debrid.realdebrid import RealDebrid
    store = auth.TokenStore(directory or paths.profile_dir())
    return RealDebrid(store) if store.connected else None
