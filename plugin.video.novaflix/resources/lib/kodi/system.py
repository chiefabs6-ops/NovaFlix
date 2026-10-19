import xbmc


def monitor():
    """Return a Kodi monitor; its waitForAbort(seconds) returns True on shutdown."""
    return xbmc.Monitor()
