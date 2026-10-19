import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib import router

BASE = "plugin://plugin.video.novaflix/"

# DEC-033 order.
EXPECTED_LABELS = [
    "Continue Watching",
    "Search",
    "My MyAnimeList",
    "Favourites",
    "Airing This Season",
    "Recently Aired Episodes",
    "Trending Now",
    "Most Popular",
    "Upcoming Next Season",
    "Genres",
    "My TorBox",
    "Settings",
]


def test_home_lists_twelve_entries_in_order():
    router.dispatch([BASE, "1", ""])
    labels = [item.getLabel() for _, _, item, _ in xbmcplugin.directory_items]
    assert labels == EXPECTED_LABELS
    assert xbmcplugin.end_calls[-1][1] is True


def test_home_entries_have_distinct_urls_on_our_plugin():
    router.dispatch([BASE, "1", ""])
    urls = [url for _, url, _, _ in xbmcplugin.directory_items]
    assert len(set(urls)) == len(urls)
    assert all(url.startswith(BASE) for url in urls)


def test_home_entries_are_folders_except_settings():
    router.dispatch([BASE, "1", ""])
    folder_flags = {item.getLabel(): is_folder for _, _, item, is_folder in xbmcplugin.directory_items}
    assert folder_flags["Settings"] is False
    assert all(flag for label, flag in folder_flags.items() if label != "Settings")


def test_every_home_entry_has_a_real_route():
    from resources.lib.views.home import HOME_ENTRIES
    assert all(route in router.ROUTES for _, route in HOME_ENTRIES)
    assert "placeholder" not in router.ROUTES


def test_settings_entry_opens_addon_settings():
    router.dispatch([BASE + "settings", "-1", ""])
    assert xbmcaddon.opened_settings == [True]


def test_home_keeps_our_order():
    router.dispatch([BASE, "1", ""])
    assert xbmcplugin.sort_methods == [(1, xbmcplugin.SORT_METHOD_UNSORTED)]


def test_root_opens_app_window_when_look_is_on(monkeypatch):
    import xbmcaddon
    from resources.lib.gui import app
    opened = []
    monkeypatch.setattr(app, "run", lambda show_id=None: opened.append(True))
    xbmcaddon.settings["novaflix_look"] = True
    router.dispatch([BASE, "1", ""])
    assert opened == [True] and xbmcplugin.end_calls[-1][1] is False
