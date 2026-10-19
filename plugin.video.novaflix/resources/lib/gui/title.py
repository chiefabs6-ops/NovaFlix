# plugin.video.novaflix/resources/lib/gui/title.py
"""Title page window (Plan 4): backdrop hero, Play/Resume, My List, More like this, Season picker
(TV) and the episode row of the chosen season. A movie has one card: the film.
Availability (sources/availability.py, the same check as Continue Watching): the Play episode is checked
once per page and shown under the buttons; episodes with a saved result get a dot."""

import datetime

import xbmcgui

from resources.lib import media
from resources.lib.gui import actions, cards, dialogs, ids, items
from resources.lib.gui.loader import Loader, PlaybackWatch, Ticker, report
from resources.lib.kodi import paths, ui
from resources.lib.metadata.library import Library
from resources.lib.sources import availability
from resources.lib.storage.mylist import MyList
from resources.lib.storage.watching import WatchHistory


class TitleWindow(xbmcgui.WindowXML):
    page = None

    def onInit(self):
        self.page.on_init()

    def onAction(self, action):
        self.page.on_action(action)

    def onClick(self, control_id):
        self.page.on_click(control_id)


def season_choices(title):
    """[(number, label)]: seasons 1..N as TMDB lists them, specials last."""
    numbers = sorted({s.number for s in title.seasons})
    ordered = [n for n in numbers if n > 0] + [n for n in numbers if n == 0]
    return [(n, ui.string(30424) % n if n else ui.string(30425)) for n in ordered]


def opening_season(title, directory):
    """The season of the last episode watched or started, else the first season that has aired, else the
    first regular season, else specials (0); None when TMDB lists no seasons at all."""
    numbers = {s.number for s in title.seasons}
    last = WatchHistory(directory).last_watched(title.media_type, title.tmdb_id)
    if last and last[0] > 0 and last[0] in numbers:
        return last[0]
    today = datetime.date.today().isoformat()
    regular = [s for s in title.seasons if s.number > 0]
    aired = [s.number for s in regular if s.air_date and s.air_date <= today]
    if aired:
        return min(aired)
    if regular:
        return regular[0].number
    return 0 if 0 in numbers else None


class TitlePage:
    def __init__(self, window, media_type, tmdb_id, loader):
        self.window = window
        self.ident = (media_type, int(tmdb_id))
        self.loader = loader
        self.result = None
        self.data = None
        self.cards = []
        self.next = (1, 0)
        self.watch = PlaybackWatch()
        self._started = False
        self.avail = {}        # (season, episode) -> Availability: saved results and this page's checks
        self.checking = set()  # (season, episode) whose check is running (never started twice)

    @property
    def is_movie(self):
        return self.ident[0] == media.MOVIE

    def on_init(self):
        if self._started:  # Kodi calls onInit again when fullscreen video closes
            key = actions.take_open_show()  # End episode: this page, or another title's
            if key and key != self.ident:
                self.result = ("title",) + key
                self.window.close()
            return
        self._started = True
        self.window.setProperty("loading", "true")
        self.loader.start({"title": self._fetch}, self._deliver)

    def _fetch(self):
        library = Library()
        title = library.title(*self.ident)
        has_more = bool(title.collection) or bool(library.more_like_this(*self.ident))
        if title.is_movie:
            return {"title": title, "season": None, "episodes": [], "has_more": has_more,
                    "avail": self._saved(title, 0, [0])}
        season = opening_season(title, paths.profile_dir())
        episodes = library.episodes(title, season) if season is not None else []
        return {"title": title, "season": season, "episodes": episodes, "has_more": has_more,
                "avail": self._saved(title, season, [e.number for e in episodes])}

    def _saved(self, title, season, numbers):
        """{(season, episode): Availability} from saved data (loader thread)."""
        if season is None:
            return {}
        found = availability.cached_episodes(title.media_type, title.tmdb_id, season, numbers)
        return {(season, n): result for n, result in found.items()}

    def _deliver(self, name, data, error):
        self.window.setProperty("loading", "")
        if error:
            report(error, "title page")
            self.window.close()
            return
        self.data = data
        self.avail.update(data["avail"])
        self._fill_header()
        self.refresh()
        self.window.setFocusId(ids.SHOW_PLAY)

    def _fill_header(self):
        title, w = self.data["title"], self.window
        hero = cards.title_hero(title, ui.string)
        for key in ("title", "alt", "plot", "meta", "art"):
            w.setProperty(key, hero[key])
        w.setProperty("dark", "true" if hero["dark"] else "")
        w.setProperty("poster", title.poster or "")
        w.setProperty("genres", " · ".join(title.genres[:4]))
        foreign = title.original_language not in (None, "en")
        w.setProperty("dub", ui.string(30427) % media.language_name(title.original_language) if foreign else "")
        w.setProperty("has_related", "true" if self.data["has_more"] else "")
        w.setProperty("related_label", ui.string(30418))

    def _season_label(self):
        season = self.data["season"]
        if season is None:
            return ""
        return ui.string(30424) % season if season else ui.string(30425)

    def refresh(self):
        """Episodes, ticks, progress and button labels; re-run after playback, marks and season changes."""
        if not self.data:
            return
        title, season = self.data["title"], self.data["season"]
        states = WatchHistory(paths.profile_dir()).states(*self.ident)
        if self.is_movie:
            state = states.get((0, 0))
            self.cards = [cards.title_movie_card(title, state, ui.string)]
            position, duration, watched = state or (0.0, 0.0, False)
            resume = int(position) if position and not watched else 0
            self.next = (0, resume)
            label = ui.string(30422) % cards.clock(duration - position) if resume else ui.string(30235)
        else:
            in_season = {e: s for (sn, e), s in states.items() if sn == season}
            self.cards = [cards.title_episode_card(title, ep, in_season.get(ep.number), ui.string)
                          for ep in self.data["episodes"]]
            self.next = cards.next_episode([e.number for e in self.data["episodes"]], in_season)
            episode, resume = self.next
            if not self.cards:
                label = ui.string(30035)  # nothing to play in this season yet
            elif resume:
                duration = in_season[episode][1]
                label = ui.string(30420) % (season, episode, cards.clock(duration - resume))
            else:
                label = ui.string(30426) % (season, episode)
        for card in self.cards:
            _, _, card_season, number = card.action
            known = self.avail.get((card_season, number))
            card.avail = known.state if known else ""
        control = self.window.getControl(ids.SHOW_EPISODES)
        position = max(control.getSelectedPosition(), 0)
        control.reset()
        control.addItems(items.to_listitems(self.cards))
        if self.cards:
            control.selectItem(min(position, len(self.cards) - 1))
        self.window.setProperty("play_label", label)
        self.window.setProperty("season_label", self._season_label())
        self.window.setProperty("episodes_title", self._season_label())
        self.window.setProperty("no_episodes", "" if self.cards else ui.string(30035))
        if self.cards:
            self._show_availability((0, 0) if self.is_movie else (season, self.next[0]))
        else:
            self.window.setProperty("avail", "")
            self.window.setProperty("avail_line", "")
        on_list = MyList(paths.profile_dir()).contains(*self.ident)
        self.window.setProperty("favourite_label", ui.string(30433 if on_list else 30432))
        self.window.setProperty("favourited", "true" if on_list else "")

    def _show_availability(self, key):
        """Status line for the Play episode: saved result at once, else checking until the background
        check answers. A failed check reads "could not check", never "no streams"."""
        season, episode = key
        known = self.avail.get(key)
        if known is None:
            self.window.setProperty("avail", "checking")
            line = ui.string(30442) % key
            self.window.setProperty("avail_line", line.split(" · ", 1)[-1] if self.is_movie else line)
            if key not in self.checking:
                self.checking.add(key)
                self.loader.start({"%d:%d" % key: lambda: availability.check(*self.ident, season, episode)},
                                  self._deliver_availability)
            return
        self.window.setProperty("avail", known.state)
        self.window.setProperty("avail_line", cards.availability_text(known, season, episode, ui.string,
                                                                      title_page=True))

    def _deliver_availability(self, name, result, error):
        key = tuple(int(n) for n in name.split(":"))
        self.checking.discard(key)
        self.avail[key] = result if error is None else availability.Availability(availability.UNKNOWN)
        self.refresh()

    def _reload_availability(self):
        """After playback: the played episode's sources are saved now; read the saved results again."""
        title, season = self.data["title"], self.data["season"]
        numbers = [0] if self.is_movie else [e.number for e in self.data["episodes"]]
        self.loader.start({"avail": lambda: self._saved(title, 0 if self.is_movie else season, numbers)},
                          self._deliver_saved)

    def _deliver_saved(self, name, saved, error):
        if saved:
            self.avail.update(saved)
            self.refresh()

    def on_click(self, control_id):
        if not self.data:
            return
        media_type, tmdb_id = self.ident
        if control_id == ids.SHOW_PLAY and self.cards:
            if self.is_movie:
                actions.watch(media_type, tmdb_id, resume_s=self.next[1])
            else:
                actions.watch(media_type, tmdb_id, self.data["season"], *self.next)
        elif control_id == ids.SHOW_FAVOURITE:
            actions.toggle_my_list(self.data["title"])
            self.refresh()
        elif control_id == ids.SHOW_SEASON and not self.is_movie:
            self._choose_season()
        elif control_id == ids.SHOW_RELATED:
            self.result = ("more", media_type, tmdb_id)
            self.window.close()
        elif control_id == ids.SHOW_EPISODES:
            card = self._selected()
            if card:
                _, _, season, episode = card.action
                actions.title_episode_choice(media_type, tmdb_id, season, episode)

    def _choose_season(self):
        choices = season_choices(self.data["title"])
        choice = dialogs.menu(ui.string(30439), [label for _, label in choices])
        if not 0 <= choice < len(choices):
            return
        season = choices[choice][0]
        title = self.data["title"]
        self.window.setProperty("loading", "true")
        self.loader.start({str(season): lambda: self._season_data(title, season)}, self._deliver_season)

    def _season_data(self, title, season):
        episodes = Library().episodes(title, season)
        return episodes, self._saved(title, season, [e.number for e in episodes])

    def _deliver_season(self, name, data, error):
        self.window.setProperty("loading", "")
        if error:
            report(error, "season")
            return
        episodes, saved = data
        self.data["season"], self.data["episodes"] = int(name), episodes
        self.avail.update(saved)
        self.refresh()

    def on_action(self, action):
        if action.getId() in ids.ACTION_BACK:
            self.window.close()
        elif action.getId() in ids.ACTION_CONTEXT and self.window.getFocusId() == ids.SHOW_EPISODES:
            self._episode_menu()

    def _selected(self):
        position = self.window.getControl(ids.SHOW_EPISODES).getSelectedPosition()
        return self.cards[position] if 0 <= position < len(self.cards) else None

    def _episode_menu(self):
        card = self._selected()
        if not card:
            return
        _, _, season, episode = card.action
        choice = dialogs.menu(card.label, [ui.string(30222 if card.watched else 30221), ui.string(30230)])
        if choice == 0:
            WatchHistory(paths.profile_dir()).mark(*self.ident, season, episode, not card.watched)
            self.refresh()
        elif choice == 1:
            actions.search_again(*self.ident, season, episode)

    def tick(self):
        text = actions.phone_search()
        if text:  # the paired phone asked for a search: the results open in the NovaFlix window
            self.result = ("grid", f"search:{text}")
            self.window.close()
            return
        if self.watch.ended():
            self.refresh()
            if self.data:
                self._reload_availability()


def open_title(media_type, tmdb_id, loader=None, start_ticker=True):
    window = TitleWindow("novaflix-show.xml", ui.addon().getAddonInfo("path"), "Default", "1080i")
    page = TitlePage(window, media_type, tmdb_id, loader or Loader())
    window.page = page
    ticker = Ticker(page.tick)
    if start_ticker:
        ticker.start()
    try:
        window.doModal()
    finally:
        ticker.stop()
        page.loader.cancel()  # a late result must not report after the page is gone
    return page.result
