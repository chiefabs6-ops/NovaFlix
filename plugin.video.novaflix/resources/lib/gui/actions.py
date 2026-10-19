# plugin.video.novaflix/resources/lib/gui/actions.py
"""What selecting a card does. Playback always goes through the `watch` route (views/watch.py)."""

import time

import xbmc

from resources.lib import media, router
from resources.lib.gui import dialogs
from resources.lib.kodi import log, paths, ui
from resources.lib.metadata.library import Library
from resources.lib.storage.mylist import MyList
from resources.lib.storage.watching import WatchHistory


def play_url(url):
    xbmc.executebuiltin(f"PlayMedia({url})")


def watch(media_type, tmdb_id, season=None, episode=None, resume_s=0):
    from resources.lib.views.watch import watch_url
    if media_type == media.MOVIE:
        season = episode = None
    play_url(watch_url(media_type, tmdb_id, season, episode, resume_s))


def search_again(media_type, tmdb_id, season=None, episode=None):
    """Search the providers again (ignoring saved results), then the usual source list."""
    if media_type == media.MOVIE:
        season = episode = None
    play_url(router.build_url("watch", type=media_type, id=tmdb_id, s=season, e=episode, refresh=1))


def title_episode_choice(media_type, tmdb_id, season, episode):
    """Started, unwatched episode or film: ask Resume / From start; otherwise play."""
    state = WatchHistory(paths.profile_dir()).states(media_type, tmdb_id).get((season or 0, episode or 0))
    if state and state[0] > 0 and not state[2]:
        choice = dialogs.resume_choice(state[0])
        if choice is None:
            return
        watch(media_type, tmdb_id, season, episode, state[0] if choice else 0)
        return
    watch(media_type, tmdb_id, season, episode)


def play_title(title):
    """Home hero Play: a movie resumes or starts; a show continues where the owner is, else S1 E1."""
    history = WatchHistory(paths.profile_dir())
    if title.is_movie:
        state = history.states(title.media_type, title.tmdb_id).get((0, 0))
        resume = state[0] if state and not state[2] else 0
        watch(title.media_type, title.tmdb_id, resume_s=resume)
        return
    row = next((r for r in history.continue_watching() if (r["media_type"], r["tmdb_id"]) ==
                (title.media_type, title.tmdb_id)), None)
    if row and not row["watched"]:
        watch(title.media_type, title.tmdb_id, row["season"], row["episode"], row["position_s"])
        return
    library = Library()
    full = library.title(title.media_type, title.tmdb_id)
    if row:
        next_ref = library.next_episode(full, row["season"], row["episode"])
        if next_ref:
            watch(title.media_type, title.tmdb_id, *next_ref)
            return
    first = next((s.number for s in full.seasons if s.number > 0), 1)
    watch(title.media_type, title.tmdb_id, first, 1)


def toggle_my_list(title):
    """Add to / remove from My List; True when the title is on it now."""
    my = MyList(paths.profile_dir())
    if my.contains(title.media_type, title.tmdb_id):
        my.remove(title.media_type, title.tmdb_id)
        ui.notify("NovaFlix", ui.string(30437))
        return False
    my.add(title)
    ui.notify(title.title, ui.string(30436))
    return True


def mark_title(media_type, tmdb_id, watched):
    """Whole title watched (movie, or every aired episode of every season) or unwatched (after asking)."""
    history = WatchHistory(paths.profile_dir())
    if not watched:
        if ui.confirm("NovaFlix", ui.string(30438)):
            history.forget(media_type, tmdb_id)
        return
    if media_type == media.MOVIE:
        history.mark(media_type, tmdb_id, 0, 0, True)
        return
    library = Library()  # network: callers run this off the GUI thread (gui/app.py)
    title = library.title(media_type, tmdb_id)
    numbers = [(season, episode.number) for season in (s.number for s in title.seasons if s.number > 0)
               for episode in library.episodes(title, season)]
    history.mark_many(media_type, tmdb_id, numbers)


def take_open_show():
    """End episode (playback/monitor.py): the title page to return to as (media_type, tmdb_id), read once;
    None if none."""
    from resources.lib.playback.monitor import OPEN_SHOW_PROPERTY
    value = ui.get_window_property(OPEN_SHOW_PROPERTY)
    if not value:
        return None
    ui.clear_window_property(OPEN_SHOW_PROPERTY)
    return parse_title_key(value)


def parse_title_key(value):
    """"tv:1396" -> ("tv", 1396); None when it is not a title key."""
    media_type, _, tmdb_id = (value or "").partition(":")
    if media_type in (media.MOVIE, media.TV) and tmdb_id.isdigit():
        return media_type, int(tmdb_id)
    return None


def search_keyboard():
    return ui.keyboard(ui.string(30032))


PHONE_IDLE_S = 300  # the phone screen closes after 5 minutes without input
_clock = time.monotonic


def search_phone():
    """Search typed on a phone over the home Wi-Fi (net/phone_keyboard.py): shows the QR code of the
    paired phone's page (pairing one the first time) and the text as it is typed. Returns the
    title the phone asked to search for, or None (Back/Cancel, 5 minutes, no home network).
    The server keeps running while NovaFlix is open, so the bookmarked page works without this screen."""
    from resources.lib.kodi.login_dialog import KodiLoginPresenter
    from resources.lib.net import lan, phone_keyboard
    host = lan.lan_address()
    if not host:
        ui.ok(ui.string(30319), ui.string(30270))
        return None
    try:
        keyboard = phone_keyboard.start(paths.profile_dir(), host, pair=True)
    except OSError as exc:
        log.warning(f"phone keyboard unavailable: {type(exc).__name__}: {exc}")
        ui.ok(ui.string(30319), ui.string(30270))
        return None
    keyboard.take_search()  # a search sent before this screen opened is not this one
    presenter = KodiLoginPresenter()
    opened = _clock()
    try:
        presenter.show({"heading": ui.string(30319), "text": ui.string(30320), "qr": keyboard.url,
                        "url": keyboard.url})
        while True:
            text = keyboard.take_search()
            if text:
                return text
            if keyboard.locked:
                ui.notify("NovaFlix", ui.string(30323), error=True)
                return None
            left = int(PHONE_IDLE_S - (_clock() - max(opened, keyboard.changed_at)))
            if left <= 0:
                return None
            seen = keyboard.changed_at >= opened  # the phone answered while this screen is open
            minutes, seconds = divmod(left, 60)
            presenter.set("code", keyboard.text if seen else "")
            presenter.set("status", ui.string(30322 if seen else 30321) % (minutes, seconds))
            if presenter.wait(0.25):
                return None
    finally:
        presenter.close()


def unpair_phone():
    """Forget the paired phone after asking; True when it was forgotten."""
    from resources.lib.net import phone_keyboard
    if not ui.confirm("NovaFlix", ui.string(30325)):
        return False
    phone_keyboard.unpair(paths.profile_dir())
    ui.notify("NovaFlix", ui.string(30326))
    return True


def start_phone_keyboard():
    """NovaFlix opened: run the paired phone's server (nothing when no phone is paired)."""
    from resources.lib.net import lan, phone_keyboard
    if phone_keyboard.load_pairing(paths.profile_dir()) is None:
        return
    host = lan.lan_address()
    if not host:
        return
    try:
        phone_keyboard.start(paths.profile_dir(), host)
    except OSError as exc:
        log.warning(f"phone keyboard unavailable: {type(exc).__name__}: {exc}")


def phone_search():
    """A search the paired phone sent while no NovaFlix screen was waiting for it; None if none.
    Never during video: it waits until playback ends."""
    from resources.lib.net import phone_keyboard
    keyboard = phone_keyboard.active()
    if keyboard is None or xbmc.getCondVisibility("Player.HasVideo"):
        return None
    return keyboard.take_search()


def add_magnet():
    from resources.lib.views import sources
    sources.add_magnet(router.Request(handle=-1, path="rd/add_magnet"))


def open_settings():
    ui.open_settings()

