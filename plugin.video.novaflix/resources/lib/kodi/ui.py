"""Thin wrappers over xbmcgui/xbmcplugin/xbmcaddon used by views."""

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin


def addon():
    return xbmcaddon.Addon()


def string(string_id):
    return addon().getLocalizedString(string_id)


def _default_art():
    return {"icon": addon().getAddonInfo("icon"), "fanart": addon().getAddonInfo("fanart")}


def setting(key):
    return addon().getSettingString(key).strip()


def _context(item, context):
    """context: [(label, url)] run in the background, or [(label, url, builtin)] with
    builtin "PlayMedia" (play/resolve the URL) or "Container.Update" (open it as a list)."""
    if context:
        item.addContextMenuItems([(entry[0], f"{entry[2] if len(entry) > 2 else 'RunPlugin'}({entry[1]})")
                                  for entry in context])


def add_item(handle, label, url, is_folder=True, art=None, context=None):
    item = xbmcgui.ListItem(label=label, offscreen=True)
    art = {k: v for k, v in (art or {}).items() if v}
    item.setArt(art or _default_art())
    _context(item, context)
    xbmcplugin.addDirectoryItem(handle, url, item, isFolder=is_folder)


def add_video_item(handle, url, label, info, art, is_folder, playable=False, context=None):
    """info maps an InfoTagVideo setter name (without "set") to a value; empty values are skipped."""
    item = xbmcgui.ListItem(label=label, offscreen=True)
    tag = item.getVideoInfoTag()
    for name, value in info.items():
        if value is None or value == [] or value == "":
            continue
        if name == "Rating":
            tag.setRating(float(value))
        elif name == "ResumePoint":
            tag.setResumePoint(*value)  # (position s, total s)
        else:
            getattr(tag, "set" + name)(value)
    art = {k: v for k, v in art.items() if v}
    item.setArt(art or _default_art())
    if not is_folder:
        item.setProperty("IsPlayable", "true" if playable else "false")
    _context(item, context)
    xbmcplugin.addDirectoryItem(handle, url, item, isFolder=is_folder)


def set_content(handle, content):
    xbmcplugin.setContent(handle, content)


def end_directory(handle, succeeded=True, cache=True):
    if succeeded:
        # Keep the order we built; Kodi labels it "Default" (SORT_METHOD_NONE would show "Date").
        # "%L" shows our label (with badges) instead of the info-tag title.
        xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_UNSORTED, labelMask="%L", label2Mask="%D")
    # Failed listings must not be cached, or Kodi keeps showing the error state.
    xbmcplugin.endOfDirectory(handle, succeeded=succeeded, updateListing=False, cacheToDisc=cache and succeeded)


def notify(heading, message, error=False):
    icon = xbmcgui.NOTIFICATION_ERROR if error else xbmcgui.NOTIFICATION_INFO
    xbmcgui.Dialog().notification(heading, message, icon)


def styled():
    """M12: NovaFlix's own screens and popups (setting "NovaFlix look")."""
    return addon().getSettingBool("novaflix_look")


def confirm(heading, message, yes=None, no=None, note=""):
    """yes / no: button labels (default Yes / No); note: a smaller line under the message."""
    if styled():
        from resources.lib.gui import dialogs
        return dialogs.confirm(heading, message, yes, no, note)
    text = f"{message}[CR][CR]{note}" if note else message
    return bool(xbmcgui.Dialog().yesno(heading, text, nolabel=no or "", yeslabel=yes or ""))


def ok(heading, message):
    if styled():
        from resources.lib.gui import dialogs
        dialogs.message(heading, message)
        return
    xbmcgui.Dialog().ok(heading, message)


def select(heading, options):
    """Index of the chosen option, or -1 if cancelled."""
    if styled():
        from resources.lib.gui import dialogs
        return dialogs.menu(heading, options)
    return xbmcgui.Dialog().select(heading, options)


def menu(heading, options):
    """One-line choice; NovaFlix's own popup with the NovaFlix look. Index of the choice, or -1."""
    if styled():
        from resources.lib.gui import dialogs
        return dialogs.menu(heading, options)
    return select(heading, options)


def select_details(heading, rows, focus=0):
    """Two-line select dialog (DEC-021). rows: [(line1, line2)]; focus: the row selected first.
    Returns index or -1."""
    if styled():
        from resources.lib.gui import dialogs
        return dialogs.pick_source(heading, rows, focus)
    items = []
    for line1, line2 in rows:
        item = xbmcgui.ListItem(label=line1, label2=line2, offscreen=True)
        items.append(item)
    return xbmcgui.Dialog().select(heading, items, preselect=focus, useDetails=True)


class _KodiProgress:
    """Cancellable progress dialog for slow work such as source discovery."""

    def __init__(self, heading, message):
        self._dialog = xbmcgui.DialogProgress()
        self._dialog.create(heading, message)
        self._monitor = xbmc.Monitor()

    def cancelled(self):
        return self._dialog.iscanceled()

    def update(self, percent, message, stats=None):
        if stats:
            message = " · ".join([message] + [stats[k] for k in ("speed", "seeders", "left") if stats.get(k)])
        self._dialog.update(max(0, min(int(percent), 100)), message)

    def wait(self, seconds):
        """Sleep in short steps; True if the owner cancelled or Kodi is closing."""
        for _ in range(int(seconds * 4)):
            if self._dialog.iscanceled() or self._monitor.waitForAbort(0.25):
                return True
        return self._dialog.iscanceled()

    def close(self):
        self._dialog.close()


def Progress(heading, message):  # noqa: N802 - keeps the old class-style call sites
    if styled():
        from resources.lib.gui import dialogs
        return dialogs.Progress(heading, message)
    return _KodiProgress(heading, message)


def keyboard(heading):
    return (xbmcgui.Dialog().input(heading) or "").strip()


def refresh():
    xbmc.executebuiltin("Container.Refresh")


def container_update(url):
    xbmc.executebuiltin(f"Container.Update({url})")


def resolve(handle, url, info, art):
    """Hand the stream to Kodi for a playable plugin item."""
    item = xbmcgui.ListItem(path=url, offscreen=True)
    tag = item.getVideoInfoTag()
    for name, value in info.items():
        if value not in (None, "", []):
            getattr(tag, "set" + name)(value)
    item.setArt({k: v for k, v in art.items() if v})
    xbmcplugin.setResolvedUrl(handle, True, item)


def resolve_failed(handle):
    if handle >= 0:
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem(offscreen=True))


def set_window_property(key, value):
    xbmcgui.Window(10000).setProperty(key, value)


def get_window_property(key):
    return xbmcgui.Window(10000).getProperty(key)


def clear_window_property(key):
    xbmcgui.Window(10000).clearProperty(key)


def open_settings():
    addon().openSettings()
