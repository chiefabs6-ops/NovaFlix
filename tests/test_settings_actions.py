import os

import xbmcgui

from resources.lib import router
from resources.lib.kodi import paths
from resources.lib.storage import cache, db

BASE = "plugin://plugin.video.novaflix/"


def test_profile_dir_is_created_under_addon_data(kodi_profile):
    path = paths.profile_dir()
    assert os.path.isdir(path)
    assert path.startswith(str(kodi_profile))
    assert "plugin.video.novaflix" in path


def test_clear_cache_confirmed_clears_and_notifies():
    store = cache.Cache(paths.profile_dir())
    store.set("k", 1, ttl=60)
    xbmcgui.yesno_answers.append(True)
    router.dispatch([BASE + "clear_cache", "-1", ""])
    assert cache.Cache(paths.profile_dir()).get("k") is None
    assert len(xbmcgui.notifications) == 1


def test_clear_cache_declined_keeps_cache():
    store = cache.Cache(paths.profile_dir())
    store.set("k", 1, ttl=60)
    xbmcgui.yesno_answers.append(False)
    router.dispatch([BASE + "clear_cache", "-1", ""])
    assert cache.Cache(paths.profile_dir()).get("k") == 1
    assert xbmcgui.notifications == []


def test_clear_cache_prompt_mentions_history_is_safe():
    xbmcgui.yesno_answers.append(False)
    router.dispatch([BASE + "clear_cache", "-1", ""])
    assert "history" in xbmcgui.yesno_calls[0][1].lower()


def test_clear_cache_does_not_touch_user_db():
    conn = db.open_user_db(paths.profile_dir())
    conn.execute("INSERT INTO favourites (anilist_id, title, poster, added_at) VALUES (5, 'X', '', 0)")
    conn.commit()
    conn.close()
    router.dispatch([BASE + "clear_cache", "-1", ""])
    conn = db.open_user_db(paths.profile_dir())
    assert conn.execute("SELECT COUNT(*) FROM favourites").fetchone()[0] == 1
