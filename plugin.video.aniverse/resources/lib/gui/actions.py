# plugin.video.aniverse/resources/lib/gui/actions.py
"""What selecting a card does (M12). Playback always goes through the existing play route."""

import time

import xbmc

from resources.lib import errors, router
from resources.lib.gui import cards, dialogs
from resources.lib.kodi import log, paths, ui
from resources.lib.metadata.catalog import Catalog
from resources.lib.storage.history import History


def play_url(url):
    xbmc.executebuiltin(f"PlayMedia({url})")


def play_episode(anilist_id, episode, resume_s=0):
    play_url(router.build_url("play", id=anilist_id, ep=episode, resume=int(resume_s) if resume_s else None))


def search_episode(anilist_id, episode):
    """Search the providers again (ignoring saved results), then the usual source list."""
    play_url(router.build_url("play", id=anilist_id, ep=episode, refresh=1))


def play_next(show):
    from resources.lib.myanimelist import progress
    numbers = [e.number for e in Catalog().episodes(show)]
    states = progress.merge_states(History(paths.profile_dir()).states(show.anilist_id),
                                   progress.show_entry(show.mal_id, network=False))  # GUI thread: never wait on MAL
    episode, resume_s = cards.next_episode(numbers, states)
    play_episode(show.anilist_id, episode, resume_s)


def episode_choice(anilist_id, episode):
    """Started, unwatched episode: ask Resume / From start (spec §6); otherwise play."""
    state = History(paths.profile_dir()).states(anilist_id).get(episode)
    if state and state[0] > 0 and not state[2]:
        choice = dialogs.resume_choice(state[0])
        if choice is None:
            return
        play_episode(anilist_id, episode, state[0] if choice else 0)
        return
    play_episode(anilist_id, episode)


def take_open_show():
    """End episode (playback/monitor.py): the show page to return to, read once; None if none."""
    from resources.lib.playback.monitor import OPEN_SHOW_PROPERTY
    value = ui.get_window_property(OPEN_SHOW_PROPERTY)
    if not value:
        return None
    ui.clear_window_property(OPEN_SHOW_PROPERTY)
    try:
        return int(value)
    except ValueError:
        return None


def mal_edit(key, anilist_id, show, entry):
    """Add to ("mal_add") or remove from ("mal_remove") MyAnimeList: long-press menu and show page.
    entry None = not logged in (offers the settings). Returns the entry as it is on MAL now,
    or None when nothing changed (cancelled, failed, not logged in)."""
    from resources.lib.myanimelist import listedit
    from resources.lib.myanimelist.progress import STATUS_STRINGS
    heading = "MyAnimeList"
    if entry is None:  # not logged in
        if ui.confirm(heading, ui.string(30313)):
            ui.open_settings()
        return None
    try:
        if key == "mal_add":
            order = listedit.ADD_ORDER
            choice = dialogs.menu(ui.string(30307), [ui.string(STATUS_STRINGS[s]) for s in order])
            if not 0 <= choice < len(order):
                return None
            watched = listedit.add(paths.profile_dir(), show.mal_id, anilist_id, order[choice],
                                   show.episodes_total or 0)
            ui.notify(show.title, ui.string(30310) % ui.string(STATUS_STRINGS[order[choice]]))
            return dict(entry, list_status=order[choice], watched=watched)
        if not ui.confirm(heading, ui.string(30309) % show.title):
            return None
        listedit.remove(paths.profile_dir(), show.mal_id)
        ui.notify(show.title, ui.string(30311))
        return dict(entry, list_status=None, watched=0, score=0)
    except errors.AniVerseError as exc:
        log.warning(f"MyAnimeList list change failed: {type(exc).__name__}: {exc}")
        ui.notify(heading, ui.string(30312), error=True)
        return None


def search_keyboard():
    return ui.keyboard(ui.string(30032))


PHONE_IDLE_S = 300  # the phone screen closes after 5 minutes without input
_clock = time.monotonic


def search_phone():
    """Search typed on a phone over the home Wi-Fi (net/phone_keyboard.py): shows the QR code of the
    paired phone's page (pairing one the first time) and the text as it is typed. Returns the
    title the phone asked to search for, or None (Back/Cancel, 5 minutes, no home network).
    The server keeps running while AniVerse is open, so the bookmarked page works without this screen."""
    from resources.lib.kodi.login_dialog import KodiLoginPresenter
    from resources.lib.myanimelist import relay
    from resources.lib.net import phone_keyboard
    host = relay.lan_address()
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
                ui.notify("AniVerse", ui.string(30323), error=True)
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
    if not ui.confirm("AniVerse", ui.string(30325)):
        return False
    phone_keyboard.unpair(paths.profile_dir())
    ui.notify("AniVerse", ui.string(30326))
    return True


def start_phone_keyboard():
    """AniVerse opened: run the paired phone's server (nothing when no phone is paired)."""
    from resources.lib.myanimelist import relay
    from resources.lib.net import phone_keyboard
    if phone_keyboard.load_pairing(paths.profile_dir()) is None:
        return
    host = relay.lan_address()
    if not host:
        return
    try:
        phone_keyboard.start(paths.profile_dir(), host)
    except OSError as exc:
        log.warning(f"phone keyboard unavailable: {type(exc).__name__}: {exc}")


def phone_search():
    """A search the paired phone sent while no AniVerse screen was waiting for it; None if none.
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
