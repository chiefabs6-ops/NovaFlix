"""Starts NovaFlix in the background (RunPlugin), so Kodi opens no folder screen first."""

import xbmc

if __name__ == "__main__":
    xbmc.executebuiltin("RunPlugin(plugin://plugin.video.novaflix/launch)")
