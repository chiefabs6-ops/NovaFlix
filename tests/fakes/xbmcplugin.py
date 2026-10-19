"""Minimal fake of Kodi's xbmcplugin module for tests."""

directory_items = []
end_calls = []
content = {}
sort_methods = []

SORT_METHOD_UNSORTED = 40


def addDirectoryItem(handle, url, listitem, isFolder=False, totalItems=0):
    directory_items.append((handle, url, listitem, isFolder))
    return True


def addDirectoryItems(handle, items, totalItems=0):
    for url, listitem, is_folder in items:
        directory_items.append((handle, url, listitem, is_folder))
    return True


def endOfDirectory(handle, succeeded=True, updateListing=False, cacheToDisc=True):
    end_calls.append((handle, succeeded, updateListing, cacheToDisc))


label_masks = []


def addSortMethod(handle, sortMethod, labelMask="", label2Mask=""):
    sort_methods.append((handle, sortMethod))
    label_masks.append(labelMask)


resolved = []


def setResolvedUrl(handle, succeeded, listitem):
    resolved.append((handle, succeeded, listitem))


def setContent(handle, value):
    content[handle] = value


def reset():
    directory_items.clear()
    end_calls.clear()
    content.clear()
    resolved.clear()
    sort_methods.clear()
    label_masks.clear()
