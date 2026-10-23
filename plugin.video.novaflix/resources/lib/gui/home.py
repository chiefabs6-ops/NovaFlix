# plugin.video.novaflix/resources/lib/gui/home.py
"""Home view of the app window: rotating hero (Trending) + Continue Watching, Trending, Popular shows
and Popular movies rows. Rows load in the background, each on its own."""

import time

from resources.lib.gui import actions, cards, ids, items, lists
from resources.lib.kodi import log, ui

ROWS = (("continue", ids.HOME_ROWS[0]), ("trending", ids.HOME_ROWS[1]),
        ("popular_tv", ids.HOME_ROWS[2]), ("popular_movies", ids.HOME_ROWS[3]))
REMOTE_ROWS = {"trending", "popular_tv", "popular_movies"}
HERO_COUNT = 5
HERO_SECONDS = 10


class HomeView:
    def __init__(self, app):
        self.app = app
        self.pages = {}
        self.failed = set()
        self.featured = []
        self.hero_index = 0
        self.hero_since = 0.0
        self.continue_final = False
        self.logos = {}

    def load(self):
        w = self.app.window
        self.pages, self.failed = {}, set()
        self.continue_final = False
        self.app.checks.reset()
        w.setProperty("offline", "")
        w.setProperty("featured", ui.string(30234))
        w.setProperty("play_label", ui.string(30235))
        w.setProperty("info_label", ui.string(30236))
        for n, (key, control_id) in enumerate(ROWS):
            w.getControl(control_id).reset()
            w.setProperty(f"row{n}_title", ui.string(lists.TITLES[key]))
            w.setProperty(f"row{n}_status", "")
        jobs = {"continue:local": lambda: lists.home_row("continue:local")}  # saved cards at once
        jobs.update({key: (lambda key=key: lists.home_row(key)) for key, _ in ROWS})
        self.app.loader.start(jobs, self._deliver)

    def _deliver(self, key, page, error):
        if key == "continue:local":
            if error is None and not self.continue_final:
                self._fill_continue(page)
            return
        n, control_id = next((n, c) for n, (k, c) in enumerate(ROWS) if k == key)
        w = self.app.window
        if isinstance(error, lists.TmdbKeyMissing):
            w.setProperty(f"row{n}_status", ui.string(30423))
            self.app.report(error)  # asked once per window (App.report)
            return
        if error:
            log.warning(f"home row {key}: {type(error).__name__}: {error}")
            self.failed.add(key)
            w.setProperty(f"row{n}_status", ui.string(30241))
            if self.failed >= REMOTE_ROWS:
                w.setProperty("offline", ui.string(30242))
                w.setProperty("retry_label", ui.string(30243))
                w.setFocusId(ids.HOME_RETRY)
            return
        if key == "continue":
            self.continue_final = True
            self._fill_continue(page)
        else:
            self.pages[control_id] = page
            w.getControl(control_id).addItems(items.to_listitems(page.cards))
        if key == "trending" and page.titles:
            self.featured = page.titles[:HERO_COUNT]
            w.setProperty("hero_count", str(len(self.featured)))
            self.show_hero(0)
            featured = list(self.featured)
            self.app.loader.start({"hero_logos": lambda: lists.hero_logos(featured)}, self._logos)

    def show_hero(self, index, now=None):
        data = cards.title_hero(self.featured[index], ui.string)
        w = self.app.window
        for key in ("title", "alt", "plot", "meta", "art", "year", "rating", "genres", "kind"):
            w.setProperty(f"hero_{key}", data[key])
        w.setProperty("hero_dark", "true" if data["dark"] else "")
        w.setProperty("hero_logo", self.logos.get(self.featured[index].tmdb_id, ""))
        w.setProperty("hero_index", str(index))
        self.hero_index = index
        self.hero_since = time.monotonic() if now is None else now

    def tick(self, now=None):
        now = time.monotonic() if now is None else now
        if len(self.featured) < 2 or self.app.window.getFocusId() in (ids.HERO_PLAY, ids.HERO_INFO):
            return
        if now - self.hero_since >= HERO_SECONDS:
            self.show_hero((self.hero_index + 1) % len(self.featured), now)

    def selected(self, control_id):
        page = self.pages.get(control_id)
        if not page:
            return None
        position = self.app.window.getControl(control_id).getSelectedPosition()
        return page.cards[position] if 0 <= position < len(page.cards) else None

    def on_click(self, control_id):
        if control_id == ids.HERO_PLAY and self.featured:
            title = self.featured[self.hero_index]
            # A show may need TMDB (next episode): off the GUI thread, failures reported.
            self.app.loader.start({"hero_play": lambda: actions.play_title(title)}, self._played)
        elif control_id == ids.HERO_INFO and self.featured:
            title = self.featured[self.hero_index]
            self.app.run(("title", title.media_type, title.tmdb_id))
        else:
            card = self.selected(control_id)
            if card:
                self.app.run(card.action)

    def refresh_continue(self):
        """Saved data at once after playback or marks, then the full row (next episodes) in the background."""
        self.continue_final = False
        self._fill_continue(lists.home_row("continue:local"))
        self.app.loader.start({"continue": lambda: lists.home_row("continue")}, self._deliver)

    def _logos(self, name, logos, error):
        if error or not self.featured:
            return  # the hero keeps its text titles
        self.logos = logos
        self.app.window.setProperty("hero_logo", logos.get(self.featured[self.hero_index].tmdb_id, ""))

    def _played(self, name, result, error):
        if error:
            self.app.report(error)

    def _fill_continue(self, page):
        control_id = ROWS[0][1]
        self.pages[control_id] = page
        control = self.app.window.getControl(control_id)
        control.reset()
        control.addItems(items.to_listitems(page.cards))
        self.app.checks.watch(control_id, page.cards)  # next-episode availability, in the background
