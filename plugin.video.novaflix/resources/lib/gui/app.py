# plugin.video.novaflix/resources/lib/gui/app.py
"""NovaFlix app window (M12): sidebar + Home, Grid, My Anime List and Related (M14) views, the screen stack and Back.
Everything it shows comes from gui/lists.py; everything it does goes through gui/actions.py."""

import contextlib

import xbmcgui

from resources.lib import errors
from resources.lib.gui import actions, dialogs, ids, items, lists
from resources.lib.gui.checks import AvailabilityChecks
from resources.lib.gui.home import HomeView
from resources.lib.gui.malhub import MalHubView
from resources.lib.gui.related import RelatedView
from resources.lib.gui.loader import Loader, PlaybackWatch, Ticker, report
from resources.lib.kodi import log, paths, ui
from resources.lib.metadata import mal
from resources.lib.metadata.catalog import Catalog
from resources.lib.myanimelist import sync
from resources.lib.storage.favourites import Favourites
from resources.lib.storage.history import History

# Sidebar redesign: five main entries, then a collapsible Explore group. Settings is its own
# button (ids.SIDEBAR_SETTINGS) at the bottom; My TorBox moved into the Settings menu.
SIDEBAR = [
    (30244, "home", ("home",)),
    (30002, "search", ("grid", "search")),
    (30001, "play_circle", ("grid", "continue")),
    (30289, "star", ("grid", "mal")),
    (30004, "favorite", ("grid", "favourites")),
]
EXPLORE = (30290, "explore", ("explore",))
EXPLORE_ITEMS = [
    (30007, "trending_up", ("grid", "trending")),
    (30008, "local_fire_department", ("grid", "popular")),
    (30005, "schedule", ("grid", "airing")),
    (30291, "auto_awesome", ("grid", "upcoming")),
    (30010, "grid_view", ("grid", "genres")),
    (30292, "calendar_month", ("grid", "recent")),
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
        shown = {c.action for c in self.cards if c.action and c.action[0] == "show"}
        new = [c for c in page.cards if not (c.action and c.action[0] == "show" and c.action in shown)]
        self.cards.extend(new)  # AniList pages can overlap when the ranking moves between requests
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
        if self.key in ("continue", "favourites") or self.key.startswith("mal:"):
            self.load(self.key)


class App:
    def __init__(self, window, loader=None, show_id=None):
        self.window = window
        self.open_show = show_id  # started by End episode with no NovaFlix window open
        self.loader = loader or Loader()
        self.stack = []
        self.view = None
        self.home = HomeView(self)
        self.grid = GridView(self)
        self.related = RelatedView(self)
        self.malhub = MalHubView(self)
        self.checks = AvailabilityChecks(self)
        self.watch = PlaybackWatch()
        self.explore_open = False
        self._busy = 0  # > 0 while a key press or click is handled (and any dialog it opened)
        self.sidebar = []   # (label string, icon, target, kind) of the rows the sidebar list shows now
        self._started = False

    # -- lifecycle ---------------------------------------------------------------

    def on_init(self):
        if self._started:  # Kodi calls onInit again after the show page or fullscreen video
            if self.view == "grid":
                self.window.setFocusId(ids.GRID)
            elif self.view == "related":
                self.related.focus()
            elif self.view == "mal":
                self.malhub.focus()
            show_id = actions.take_open_show()  # End episode pressed during the video
            if show_id:
                self.run(("show", show_id))
            return
        self._started = True
        self.show_home()
        if self.open_show:
            show_id, self.open_show = self.open_show, None
            self.run(("show", show_id))

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
        explore_row = len(SIDEBAR)
        self.window.getControl(ids.SIDEBAR).selectItem(explore_row)  # focus stays on Explore

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
        if not self._busy:  # a dialog or the show page on top takes the phone's search itself
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
        if key == "mal":  # the status cards; "mal:<status>" is a grid
            self._set_view("mal", "mal")
            self.malhub.load()
        elif name == "related":
            self._set_view("related", "related")
            self.related.load(arg)
        else:
            self._set_view("grid", name)
            self.grid.load(key)

    def back(self):
        if self.view not in ("grid", "related", "mal"):
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
            self.checks.follow_grid(ids.GRID, self.grid.cards,
                                    self.window.getControl(ids.GRID).getSelectedPosition())
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
        elif control_id in ids.MAL_CARDS:
            self.malhub.on_click(control_id)
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
        elif kind == "related":
            self.open_grid(f"related:{action[1]}")
        elif kind == "settings":
            actions.open_settings()
        elif kind == "show":
            from resources.lib.gui import show
            result = show.open_show(action[1])
            if result:
                self.run(result)
            else:
                self._refresh()  # favourites or watched marks may have changed
        elif kind == "play":
            actions.play_episode(*action[1:])
        elif kind == "episode":
            actions.episode_choice(*action[1:])
        elif kind == "search":
            actions.search_episode(*action[1:])
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

    def settings_menu(self):
        """Settings: the add-on settings, plus My TorBox / My Real-Debrid (moved out of the sidebar)."""
        from resources.lib.debrid import service
        choice = dialogs.menu(ui.string(30012), [ui.string(30293), ui.string(30011) % service.label()])
        if choice == 0:
            self.run(("settings",))
        elif choice == 1:
            self.stack.clear()  # like a sidebar choice: Back from the cloud list returns Home
            self.run(("grid", "torbox"))

    def report(self, error):
        if isinstance(error, mal.MalSetupMissing):
            if ui.confirm(ui.string(30003), ui.string(30075)):
                ui.open_settings()
        elif isinstance(error, mal.MalUserUnavailable):
            ui.ok(ui.string(30003), ui.string(30076) % ui.setting("mal_username"))
        elif isinstance(error, mal.MalClientRejected):
            if ui.confirm(ui.string(30003), ui.string(30077)):
                ui.open_settings()
        elif isinstance(error, lists.ServiceMissing):
            from resources.lib.views import sources
            sources._setup_service(None)
        else:
            report(error, "NovaFlix window")

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
        # Show cards open the show; Continue Watching cards play or search (anilist_id comes second).
        if not card or not card.action or card.action[0] not in ("show", "play", "search"):
            return
        anilist_id = card.action[1]
        favs = Favourites(paths.profile_dir())
        try:
            favourite = anilist_id in favs.ids()
        finally:
            favs.close()
        options = [("favourite", ui.string(30061 if favourite else 30060)), ("watched", ui.string(30223)),
                   ("unwatched", ui.string(30224)), ("related", ui.string(30034))]
        mal_state = self._mal_state(anilist_id)
        if mal_state is not None:
            on_list = bool(mal_state[1] and mal_state[1].get("list_status"))
            options.append(("mal_remove", ui.string(30308)) if on_list else ("mal_add", ui.string(30307)))
        choice = dialogs.menu(card.label, [label for _, label in options])
        if not 0 <= choice < len(options):
            return
        key = options[choice][0]
        if key == "favourite":
            favs = Favourites(paths.profile_dir())
            try:
                if favourite:
                    favs.remove(anilist_id)
                    ui.notify("NovaFlix", ui.string(30064))
                else:
                    show = Catalog().show(anilist_id)
                    favs.add(show)
                    ui.notify(show.title, ui.string(30063))
            finally:
                favs.close()
        elif key == "watched":
            catalog = Catalog()
            show = catalog.show(anilist_id)
            numbers = [e.number for e in catalog.episodes(show)]
            History(paths.profile_dir()).mark_show(anilist_id, numbers, True)
            sync.queue_show(paths.profile_dir(), anilist_id, "show_watched", max(numbers, default=0),
                            mal_id=show.mal_id)
        elif key == "unwatched":
            if ui.confirm("NovaFlix", ui.string(30227)):
                History(paths.profile_dir()).mark_show(anilist_id, [], False)
                sync.queue_show(paths.profile_dir(), anilist_id, "show_unwatched")
        elif key == "related":
            self.run(("related", anilist_id))
            return
        elif key in ("mal_add", "mal_remove"):
            actions.mal_edit(key, anilist_id, *mal_state)
        self._refresh()

    def _mal_state(self, anilist_id):
        """(show, MAL entry) for the long-press menu; entry None = not logged in (the menu still
        offers Add, which explains the login). None = no MAL ID or MAL unreachable: no MAL option."""
        from resources.lib.myanimelist import auth, progress
        catalog = Catalog()
        try:
            show = catalog.cached_show(anilist_id) or catalog.show(anilist_id)
        except errors.NovaFlixError:
            return None
        if not show.mal_id:
            return None
        if not auth.MalStore(paths.profile_dir()).logged_in:
            return show, None
        entry = progress.show_entry(show.mal_id)
        return (show, entry) if entry is not None else None


def run(show_id=None):
    from resources.lib.playback.monitor import GUI_PROPERTY
    window = AppWindow("novaflix-app.xml", ui.addon().getAddonInfo("path"), "Default", "1080i")
    app = App(window, show_id=show_id)
    window.app = app
    ticker = Ticker(app.tick)
    ticker.start()
    ui.set_window_property(GUI_PROPERTY, "true")  # End episode: this window opens the show page
    actions.start_phone_keyboard()
    try:
        window.doModal()
    finally:
        from resources.lib.net import phone_keyboard
        phone_keyboard.stop()  # the phone's page works only while NovaFlix is open
        ui.clear_window_property(GUI_PROPERTY)
        ticker.stop()
        app.loader.cancel()
