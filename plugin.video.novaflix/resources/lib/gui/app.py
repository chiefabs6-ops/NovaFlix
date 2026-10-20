# plugin.video.novaflix/resources/lib/gui/app.py
"""NovaFlix app window: sidebar + Home, Grid and More like this views, the screen stack and Back.
Everything it shows comes from gui/lists.py; everything it does goes through gui/actions.py."""

import contextlib

import xbmcgui

from resources.lib import errors, media
from resources.lib.gui import actions, dialogs, ids, items, lists
from resources.lib.gui.checks import AvailabilityChecks
from resources.lib.gui.home import HomeView
from resources.lib.gui.related import RelatedView
from resources.lib.gui.loader import Loader, PlaybackWatch, Ticker, report
from resources.lib.kodi import ui
from resources.lib.storage.mylist import MyList
from resources.lib.kodi import paths

# Four main entries, then a collapsible Explore group. Settings is its own button (ids.SIDEBAR_SETTINGS)
# at the bottom; My TorBox sits in the Settings menu.
SIDEBAR = [
    (30244, "home", ("home",)),
    (30002, "search", ("grid", "search")),
    (30001, "play_circle", ("grid", "continue")),
    (30415, "bookmark", ("grid", "mylist")),
]
EXPLORE = (30290, "explore", ("explore",))
EXPLORE_ITEMS = [
    (30007, "trending_up", ("grid", "trending")),
    (30410, "movie", ("grid", "popular_movies")),
    (30411, "local_fire_department", ("grid", "popular_tv")),
    (30412, "star", ("grid", "top_movies")),
    (30413, "auto_awesome", ("grid", "top_tv")),
    (30414, "calendar_month", ("grid", "airing_today")),
    (30010, "grid_view", ("grid", "genres")),
]
EXPLORE_KEYS = {target[1] for _, _, target in EXPLORE_ITEMS} | {"genre"}
GRID_MORE_MARGIN = 6  # within one grid row of the end -> load the next page


class AppWindow(xbmcgui.WindowXML):
    app = None

    def onInit(self):
        with self.app.busy():
            self.app.on_init()

    def onAction(self, action):
        with self.app.busy():
            self.app.on_action(action)

    def onClick(self, control_id):
        with self.app.busy():
            self.app.on_click(control_id)


class GridView:
    def __init__(self, app):
        self.app = app
        self.key = None
        self.cards = []
        self.page = 1
        self.more = False
        self.loading = False

    def load(self, key):
        self.key, self.cards, self.page, self.more = key, [], 1, False
        self.app.checks.reset()
        w = self.app.window
        w.getControl(ids.GRID).reset()
        w.setProperty("grid_title", "")
        w.setProperty("grid_empty", "")
        self._fetch(1)

    def _fetch(self, page_no):
        self.loading = True
        self.app.window.setProperty("loading", "true")
        key = self.key
        self.app.loader.start({f"{page_no}:{key}": lambda: lists.load(key, page_no)}, self._deliver)

    def _deliver(self, name, page, error):
        page_no, _, key = name.partition(":")
        if key != self.key or int(page_no) != self.page:
            return  # another list, or a page of this list from before it was reloaded
        self.loading = False
        self.app.window.setProperty("loading", "")
        if error:
            self.app.report(error)
            self.app.back()
            return
        first = not self.cards
        shown = {c.action for c in self.cards if c.action and c.action[0] == "title"}
        new = [c for c in page.cards if not (c.action and c.action[0] == "title" and c.action in shown)]
        self.cards.extend(new)  # TMDB pages can overlap when the ranking moves between requests
        self.more = page.more
        w = self.app.window
        w.setProperty("grid_title", page.title)
        control = w.getControl(ids.GRID)
        position = control.getSelectedPosition()
        if new:
            control.addItems(items.to_listitems(new))
            if not first and position > 0:
                # Kodi's addItems re-binds the whole container and selects the first card; the owner's
                # card is selected again in the same GUI pass, so the grid stays where it was.
                control.selectItem(position)
        position = control.getSelectedPosition()
        self.app.checks.follow_grid(ids.GRID, self.cards, max(position, 0))  # next-episode availability
        if first:
            w.setProperty("grid_empty", "" if page.cards else (page.empty or ui.string(30256)))
            if page.cards:
                w.setFocusId(ids.GRID)

    def maybe_more(self):
        if not self.more or self.loading:
            return
        position = self.app.window.getControl(ids.GRID).getSelectedPosition()
        if position >= len(self.cards) - GRID_MORE_MARGIN:
            self.page += 1
            self._fetch(self.page)

    def selected(self):
        position = self.app.window.getControl(ids.GRID).getSelectedPosition()
        return self.cards[position] if 0 <= position < len(self.cards) else None

    def refresh(self):
        if self.key in ("continue", "mylist"):
            self.load(self.key)


class App:
    def __init__(self, window, loader=None, title_key=None):
        self.window = window
        self.open_title = title_key  # started by End episode with no NovaFlix window open
        self.loader = loader or Loader()
        self.stack = []
        self.view = None
        self.home = HomeView(self)
        self.grid = GridView(self)
        self.related = RelatedView(self)
        self.checks = AvailabilityChecks(self)
        self.watch = PlaybackWatch()
        self.explore_open = False
        self._busy = 0  # > 0 while a key press or click is handled (and any dialog it opened)
        self.key_asked = False  # the TMDB key question is asked once per window
        self.sidebar = []   # (label string, icon, target, kind) of the rows the sidebar list shows now
        self._started = False

    # -- lifecycle ---------------------------------------------------------------

    def on_init(self):
        if self._started:  # Kodi calls onInit again after the title page or fullscreen video
            if self.view == "grid":
                self.window.setFocusId(ids.GRID)
            elif self.view == "related":
                self.related.focus()
            key = actions.take_open_show()  # End episode pressed during the video
            if key:
                self.run(("title",) + key)
            return
        self._started = True
        self.show_home()
        if self.open_title:
            key, self.open_title = self.open_title, None
            self.run(("title",) + key)

    def _fill_sidebar(self):
        self.sidebar = [entry + ("main",) for entry in SIDEBAR] + [EXPLORE + ("explore",)]
        if self.explore_open:
            self.sidebar += [entry + ("sub",) for entry in EXPLORE_ITEMS]
        current = self.window.getProperty("current")
        entries = []
        for string_id, icon, target, kind in self.sidebar:
            key = target[1] if target[0] == "grid" else target[0]
            item = xbmcgui.ListItem(label=ui.string(string_id), offscreen=True)
            item.setProperty("icon", f"av-icon-{icon}.png")
            item.setProperty("target", key)
            item.setProperty("kind", kind)
            # Kodi conditions cannot compare two infolabels ($INFO inside a condition fails to parse),
            # so the entry for the screen shown now is marked here.
            item.setProperty("active", "true" if key == current else "")
            entries.append(item)
        self.window.setProperty("explore_open", "true" if self.explore_open else "")
        self.window.setProperty("settings_label", ui.string(30012))
        control = self.window.getControl(ids.SIDEBAR)
        position = control.getSelectedPosition()
        control.reset()
        control.addItems(entries)
        if 0 <= position < len(entries):
            control.selectItem(position)

    def toggle_explore(self):
        self.explore_open = not self.explore_open
        self._fill_sidebar()
        self.window.getControl(ids.SIDEBAR).selectItem(len(SIDEBAR))  # focus stays on Explore

    def close(self):
        self.loader.cancel()
        self.window.close()

    @contextlib.contextmanager
    def busy(self):
        self._busy += 1
        try:
            yield
        finally:
            self._busy -= 1

    def tick(self, now=None):
        if self.view == "home":
            self.home.tick(now)
        if self.watch.ended():
            self._refresh()
        if not self._busy:  # a dialog or the title page on top takes the phone's search itself
            text = actions.phone_search()
            if text:
                self.open_grid(f"search:{text}")

    # -- navigation ----------------------------------------------------------------

    def _set_view(self, view, current):
        self.loader.cancel()  # results for the screen being left must not land on the new one
        self.view = view
        self.window.setProperty("view", view)
        self.window.setProperty("current", current)
        self.window.setProperty("current_group", "explore" if current in EXPLORE_KEYS else "")
        self._fill_sidebar()  # moves the active mark

    def show_home(self):
        self.stack.clear()
        self._set_view("home", "home")
        self.window.setFocusId(ids.HERO_PLAY)  # before loading: an offline result moves focus to Retry
        self.home.load()

    def open_grid(self, key):
        self.stack.append(key)
        self._open(key)

    def _open(self, key):
        name, _, arg = key.partition(":")
        if name == "more":
            media_type, _, tmdb_id = arg.partition(":")
            self._set_view("related", "related")
            self.related.load(media_type, tmdb_id)
        else:
            self._set_view("grid", name)
            self.grid.load(key)

    def back(self):
        if self.view not in ("grid", "related"):
            self.close()
            return
        if self.stack:
            self.stack.pop()
        if self.stack:
            self._open(self.stack[-1])
        else:
            self.show_home()

    def _refresh(self):
        if self.view == "home":
            self.home.refresh_continue()
        elif self.view == "grid":
            self.grid.refresh()

    # -- input -----------------------------------------------------------------------

    def on_action(self, action):
        action_id = action.getId()
        if action_id in ids.ACTION_BACK:
            self.back()
        elif action_id in ids.ACTION_CONTEXT:
            self._context_menu()
        elif action_id in ids.ACTION_MOVES and self.window.getFocusId() == ids.GRID:
            self.checks.follow_grid(ids.GRID, self.grid.cards, self.window.getControl(ids.GRID).getSelectedPosition())
            if action_id in (ids.ACTION_MOVE_RIGHT, ids.ACTION_MOVE_DOWN):
                self.grid.maybe_more()

    def on_click(self, control_id):
        if control_id == ids.SIDEBAR:
            position = self.window.getControl(ids.SIDEBAR).getSelectedPosition()
            if 0 <= position < len(self.sidebar):
                target = self.sidebar[position][2]
                if target[0] == "explore":
                    self.toggle_explore()
                    return
                if target[0] == "grid":
                    self.stack.clear()  # a sidebar choice starts a new trail; Back returns Home
                self.run(target)
        elif control_id == ids.SIDEBAR_SETTINGS:
            self.settings_menu()
        elif control_id in (ids.HERO_PLAY, ids.HERO_INFO) or control_id in ids.HOME_ROWS:
            self.home.on_click(control_id)
        elif control_id in ids.RELATED_ROWS:
            self.related.on_click(control_id)
        elif control_id == ids.HOME_RETRY:
            self.home.load()
        elif control_id == ids.GRID:
            card = self.grid.selected()
            if card:
                self.run(card.action)

    def run(self, action):
        kind = action[0] if action else "noop"
        if kind == "home":
            self.show_home()
        elif kind == "grid":
            self.open_grid(action[1])
        elif kind == "more":
            self.open_grid(f"more:{action[1]}:{action[2]}")
        elif kind == "settings":
            actions.open_settings()
        elif kind == "title":
            from resources.lib.gui import title
            result = title.open_title(action[1], action[2])
            if result:
                self.run(result)
            else:
                self._refresh()  # My List or watched marks may have changed
        elif kind == "watch":
            actions.watch(*action[1:])
        elif kind == "search":  # next episode not available / not checked: search the providers again
            actions.search_again(*action[1:])
        elif kind == "search_new":
            text = actions.search_keyboard()
            if text:
                self.open_grid(f"search:{text}")
        elif kind == "search_phone":
            text = actions.search_phone()
            if text:
                self.open_grid(f"search:{text}")
            elif self.grid.key == "search":
                self.grid.load("search")  # the Unpair tile appears once a phone is paired
        elif kind == "phone_unpair":
            if actions.unpair_phone():
                self.grid.load(self.grid.key)
        elif kind == "magnet":
            actions.add_magnet()
            self.grid.load(self.grid.key)
        elif kind == "plugin_play":
            actions.play_url(action[1])
        elif kind == "filter":
            try:
                key = actions.choose_filter(action[1], action[2])
            except errors.NovaFlixError as exc:
                self.report(exc)
                return
            if key:
                # The same list with other choices: it replaces the list, so Back still leaves it.
                if self.stack:
                    self.stack[-1] = key
                self.grid.load(key)

    def settings_menu(self):
        """Settings: the add-on settings, plus My TorBox."""
        from resources.lib.debrid import service
        choice = dialogs.menu(ui.string(30012), [ui.string(30293), ui.string(30011) % service.label()])
        if choice == 0:
            self.run(("settings",))
        elif choice == 1:
            self.stack.clear()  # like a sidebar choice: Back from the cloud list returns Home
            self.run(("grid", "torbox"))

    def report(self, error):
        if isinstance(error, lists.TmdbKeyMissing):
            if self.key_asked:
                return
            self.key_asked = True
            if ui.confirm("TMDB", ui.string(30423)):
                ui.open_settings()
                from resources.lib.metadata.library import Library
                if Library().has_token:  # the key was added: browse at once
                    self.key_asked = False
                    self.show_home()
        elif isinstance(error, lists.ServiceMissing):
            from resources.lib.views import sources
            sources._setup_service(None)
        else:
            report(error, "NovaFlix window")

    def _marked(self, name, result, error):
        if error:
            self.report(error)
        self._refresh()

    def _focused_card(self):
        focus = self.window.getFocusId()
        if focus == ids.GRID:
            return self.grid.selected()
        if focus in ids.HOME_ROWS:
            return self.home.selected(focus)
        if focus in ids.RELATED_ROWS:
            return self.related.selected(focus)
        return None

    def _context_menu(self):
        card = self._focused_card()
        # Title cards open the title page; Continue Watching cards play (media_type, tmdb_id come next).
        if not card or not card.action or card.action[0] not in ("title", "watch", "search"):
            return
        media_type, tmdb_id = card.action[1], card.action[2]
        on_list = MyList(paths.profile_dir()).contains(media_type, tmdb_id)
        options = [("mylist", ui.string(30433 if on_list else 30432)), ("watched", ui.string(30434)),
                   ("unwatched", ui.string(30435)), ("more", ui.string(30418))]
        choice = dialogs.menu(card.label, [label for _, label in options])
        if not 0 <= choice < len(options):
            return
        key = options[choice][0]
        try:
            if key == "mylist":
                from resources.lib.metadata.library import Library
                title = Library().cached_title(media_type, tmdb_id) or media.Title(
                    media_type=media_type, tmdb_id=tmdb_id, title=card.label, poster=card.poster)
                actions.toggle_my_list(title)
            elif key == "watched":
                # A long show is one TMDB call per season: never on the GUI thread.
                self.loader.start({f"mark:{media_type}:{tmdb_id}": lambda: actions.mark_title(media_type, tmdb_id, True)},
                                  self._marked)
                return
            elif key == "unwatched":
                actions.mark_title(media_type, tmdb_id, False)
            elif key == "more":
                self.run(("more", media_type, tmdb_id))
                return
        except errors.NovaFlixError as exc:
            self.report(exc)
        self._refresh()


def run(title_key=None):
    """Open the NovaFlix window; title_key "tv:1396" (End episode, nothing open) opens that title page."""
    from resources.lib.playback.monitor import GUI_PROPERTY
    window = AppWindow("novaflix-app.xml", ui.addon().getAddonInfo("path"), "Default", "1080i")
    app = App(window, title_key=actions.parse_title_key(title_key) if title_key else None)
    window.app = app
    ticker = Ticker(app.tick)
    ticker.start()
    ui.set_window_property(GUI_PROPERTY, "true")  # End episode: this window opens the title page
    actions.start_phone_keyboard()
    try:
        window.doModal()
    finally:
        from resources.lib.net import phone_keyboard
        phone_keyboard.stop()  # the phone's page works only while NovaFlix is open
        ui.clear_window_property(GUI_PROPERTY)
        ticker.stop()
        app.loader.cancel()
