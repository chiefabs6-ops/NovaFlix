import os

import xbmcvfs

_PROFILE = "special://profile/addon_data/plugin.video.aniverse/"
_KODI_CA_FILE = "special://xbmc/system/certs/cacert.pem"


def profile_dir():
    """The add-on's private data folder, created if missing."""
    path = xbmcvfs.translatePath(_PROFILE)
    if not os.path.isdir(path):
        xbmcvfs.mkdirs(path)
    return path


def ca_file():
    """Kodi's bundled CA bundle, or None to use the system store.

    Android Python has no usable system store; Kodi ships one.
    """
    path = xbmcvfs.translatePath(_KODI_CA_FILE)
    return path if os.path.isfile(path) else None
